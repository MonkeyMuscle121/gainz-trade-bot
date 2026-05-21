import os
import asyncio
import discord
from dotenv import load_dotenv
from web3 import Web3
import logging

load_dotenv()

# ================== CONFIG ==================
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
CHANNEL_ID = int(os.getenv('CHANNEL_ID'))

BUYBACK_WALLET = "0x030D98AE8B40A306c786df56707b90610B281955".lower()

RPC_URL = "https://cronos-evm-rpc.publicnode.com"
TOKEN_ADDRESS = "0xF7b1095D2af6C81c2d88f0ab44c7c2341BFfc411"
PAIR_ADDRESS = "0x3a26c936973635dff0a89ca93e4e62f70514c210"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

w3 = Web3(Web3.HTTPProvider(RPC_URL, request_kwargs={'timeout': 60}))

if not w3.is_connected():
    logger.error("❌ Cannot connect to RPC")
    exit(1)

logger.info("✅ Connected to Cronos RPC")
logger.info(f"🔥 Buyback Wallet: {BUYBACK_WALLET[:8]}...{BUYBACK_WALLET[-6:]}")

TOKEN_ADDRESS = w3.to_checksum_address(TOKEN_ADDRESS)
PAIR_ADDRESS = w3.to_checksum_address(PAIR_ADDRESS)

# ABIs
ERC20_ABI = [{"constant": True, "inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "type": "function"}]

PAIR_ABI = [
    {"constant": True, "inputs": [], "name": "token0", "outputs": [{"name": "", "type": "address"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "token1", "outputs": [{"name": "", "type": "address"}], "type": "function"},
    {"anonymous": False, "inputs": [
        {"indexed": True, "name": "sender", "type": "address"},
        {"indexed": False, "name": "amount0In", "type": "uint256"},
        {"indexed": False, "name": "amount1In", "type": "uint256"},
        {"indexed": False, "name": "amount0Out", "type": "uint256"},
        {"indexed": False, "name": "amount1Out", "type": "uint256"},
        {"indexed": True, "name": "to", "type": "address"}
    ], "name": "Swap", "type": "event"}
]

pair_contract = w3.eth.contract(address=PAIR_ADDRESS, abi=PAIR_ABI)
token_contract = w3.eth.contract(address=TOKEN_ADDRESS, abi=ERC20_ABI)

token0 = pair_contract.functions.token0().call().lower()
gainz_is_token0 = token0 == TOKEN_ADDRESS.lower()
gainz_decimals = token_contract.functions.decimals().call()

seen_tx = set()

intents = discord.Intents.default()
client = discord.Client(intents=intents)
channel = None
bot_started = False   # Prevent repeated online messages

@client.event
async def on_ready():
    global channel, bot_started
    logger.info(f"✅ Logged in as {client.user}")
    channel = client.get_channel(CHANNEL_ID)
    
    if channel and not bot_started:
        await channel.send("🚀 **GAINZ Buy Bot ONLINE** + Buyback Tracker Active")
        bot_started = True
    asyncio.create_task(monitor_trades())

async def monitor_trades():
    global channel
    logger.info("📡 Monitor started...")

    last_block = w3.eth.block_number - 10
    cleanup_counter = 0

    while True:
        try:
            current_block = w3.eth.block_number
            if current_block > last_block:
                for block_num in range(last_block + 1, current_block + 1):
                    events = pair_contract.events.Swap.get_logs(fromBlock=block_num, toBlock=block_num)
                    for event in events:
                        tx_hash = event.transactionHash.hex()
                        if tx_hash in seen_tx:
                            continue
                        seen_tx.add(tx_hash)
                        await process_swap(event, tx_hash)

                last_block = current_block
                cleanup_counter += 1

                # Clean memory every 100 blocks
                if cleanup_counter >= 100:
                    if len(seen_tx) > 5000:
                        seen_tx.clear()
                    cleanup_counter = 0

            await asyncio.sleep(4)

        except Exception as e:
            logger.error(f"Monitor crashed: {e}", exc_info=True)
            await asyncio.sleep(15)   # Longer wait on error

async def process_swap(event, tx_hash):
    global channel
    if not channel:
        return

    try:
        args = event.args
        sender = args.get('sender', '').lower()
        to_addr = args.get('to', '').lower()

        # Detect BUY
        if gainz_is_token0:
            is_buy = args.get('amount1In', 0) > 0 and args.get('amount0Out', 0) > 0
            gainz_amount = args['amount0Out'] / (10 ** gainz_decimals) if is_buy else 0
            cro_amount = args['amount1In'] / 1e18 if is_buy else 0
        else:
            is_buy = args.get('amount0In', 0) > 0 and args.get('amount1Out', 0) > 0
            gainz_amount = args['amount1Out'] / (10 ** gainz_decimals) if is_buy else 0
            cro_amount = args['amount0In'] / 1e18 if is_buy else 0

        if not is_buy or gainz_amount < 100:
            return

        # Improved Buyback Detection
        is_buyback = False
        try:
            tx = w3.eth.get_transaction(tx_hash)
            if tx['from'].lower() == BUYBACK_WALLET:
                is_buyback = True
        except:
            if sender == BUYBACK_WALLET or to_addr == BUYBACK_WALLET:
                is_buyback = True

        if is_buyback:
            title = "🔥 **GAINZ BUYBACK TOKENS** 🔥"
            color = 0xff8800
            footer = "Official Team Buyback • 0x030D...1955"
        else:
            title = "🟢 **BUY** $GAINZ"
            color = 0x00ff00
            footer = "VVS Finance • BUY alerts only"

        embed = discord.Embed(title=title, description=f"**{gainz_amount:,.2f} GAINZ** for **{cro_amount:,.4f} WCRO**", color=color)
        embed.add_field(name="Links", value=f"[📊 DexScreener](https://dexscreener.com/cronos/0xF7b1095D2af6C81c2d88f0ab44c7c2341BFfc411)\n[🔗 Tx](https://explorer.cronos.org/tx/0x{tx_hash})", inline=False)
        embed.set_footer(text=footer)

        await channel.send(embed=embed)
        logger.info(f"{'🔥 BUYBACK' if is_buyback else '🟢 BUY'} → {gainz_amount:,.0f} GAINZ")

    except Exception as e:
        logger.error(f"Process error: {e}")

client.run(DISCORD_TOKEN)
