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

logger.info(f"✅ GAINZ Setup | Token0: {gainz_is_token0}")

intents = discord.Intents.default()
client = discord.Client(intents=intents)
channel = None

@client.event
async def on_ready():
    global channel
    logger.info(f"✅ Logged in as {client.user}")
    channel = client.get_channel(CHANNEL_ID)
    
    if channel:
        await channel.send("🚀 **GAINZ Buy Bot ONLINE**")
    asyncio.create_task(monitor_trades())

async def monitor_trades():
    global channel
    logger.info("📡 Starting block polling monitor...")

    last_block = w3.eth.block_number - 10  # Start a bit behind

    while True:
        try:
            current_block = w3.eth.block_number
            if current_block > last_block:
                for block_num in range(last_block + 1, current_block + 1):
                    try:
                        events = pair_contract.events.Swap.get_logs(fromBlock=block_num, toBlock=block_num)
                        for event in events:
                            await process_buy(event)
                    except Exception as e:
                        logger.warning(f"Block {block_num} error: {e}")

                last_block = current_block
                logger.info(f"✅ Scanned up to block {current_block} | Last alert check done")

            await asyncio.sleep(4)  # Poll every ~4 seconds

        except Exception as e:
            logger.error(f"Monitor loop error: {e}", exc_info=True)
            await asyncio.sleep(10)

async def process_buy(event):
    global channel
    if not channel:
        return

    try:
        args = event.args
        tx_hash = event.transactionHash.hex()

        if gainz_is_token0:
            if args.get('amount1In', 0) > 0 and args.get('amount0Out', 0) > 0:
                gainz_amount = args['amount0Out'] / (10 ** gainz_decimals)
                cro_amount = args['amount1In'] / 1e18
            else:
                return
        else:
            if args.get('amount0In', 0) > 0 and args.get('amount1Out', 0) > 0:
                gainz_amount = args['amount1Out'] / (10 ** gainz_decimals)
                cro_amount = args['amount0In'] / 1e18
            else:
                return

        if gainz_amount < 100:
            return

        embed = discord.Embed(
            title="🟢 **BUY** $GAINZ",
            description=f"**{gainz_amount:,.2f} GAINZ** for **{cro_amount:,.4f} WCRO**",
            color=0x00ff00
        )
        embed.add_field(
            name="Links",
            value=f"[📊 DexScreener](https://dexscreener.com/cronos/0xF7b1095D2af6C81c2d88f0ab44c7c2341BFfc411)\n"
                  f"[🔗 Tx](https://explorer.cronos.org/tx/0x{tx_hash})",
            inline=False
        )
        embed.set_footer(text="VVS Finance • BUY alerts only")

        await channel.send(embed=embed)
        logger.info(f"🚀 BUY ALERT SENT → {gainz_amount:,.0f} GAINZ ({cro_amount:.4f} WCRO)")

    except Exception as e:
        logger.error(f"Process buy error: {e}")

client.run(DISCORD_TOKEN)
