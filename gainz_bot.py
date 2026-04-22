import os
import time
import discord
from dotenv import load_dotenv
from web3 import Web3
from collections import defaultdict

load_dotenv()

# ================== CONFIG ==================
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
CHANNEL_ID = int(os.getenv('CHANNEL_ID'))

RPC_URL = "https://cronos-evm-rpc.publicnode.com"

TOKEN_ADDRESS_RAW = "0xF7b1095D2af6C81c2d88f0ab44c7c2341BFfc411"
PAIR_ADDRESS_RAW  = "0x3a26c936973635dff0a89ca93e4e62f70514c210"   # VVS GAINZ/WCRO

# Rough WCRO price in USD (update this occasionally)
WCRO_USD_PRICE = 0.09

w3 = Web3(Web3.HTTPProvider(RPC_URL))
TOKEN_ADDRESS = w3.to_checksum_address(TOKEN_ADDRESS_RAW)
PAIR_ADDRESS  = w3.to_checksum_address(PAIR_ADDRESS_RAW)

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

TOKEN_ABI = [
    {"constant": True, "inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "type": "function"},
    {"anonymous": False, "inputs": [
        {"indexed": True, "name": "from", "type": "address"},
        {"indexed": True, "name": "to", "type": "address"},
        {"indexed": False, "name": "value", "type": "uint256"}
    ], "name": "Transfer", "type": "event"}
]

# Load contracts
pair_contract = w3.eth.contract(address=PAIR_ADDRESS, abi=PAIR_ABI)
token_contract = w3.eth.contract(address=TOKEN_ADDRESS, abi=TOKEN_ABI)

token0 = pair_contract.functions.token0().call().lower()
gainz_is_token0 = token0 == TOKEN_ADDRESS.lower()
gainz_decimals = token_contract.functions.decimals().call()
wcro_decimals = 18

print(f"✅ Bot ready! WCRO ≈ ${WCRO_USD_PRICE} | Monitoring VVS + Aggregator transfers")

seen_tx = defaultdict(float)

# Discord bot
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f"✅ Bot logged in as {client.user}")
    channel = client.get_channel(CHANNEL_ID)
    if channel:
        await channel.send("🚀 **GAINZ Trade Bot is online!** Monitoring direct VVS trades + aggregator transfers (with rough USD)")
    await monitor_all(channel)

async def monitor_all(channel):
    swap_filter = pair_contract.events.Swap.create_filter(from_block="latest")
    transfer_filter = token_contract.events.Transfer.create_filter(from_block="latest")

    while True:
        try:
            for event in swap_filter.get_new_entries():
                await process_swap(event, channel)
            for event in transfer_filter.get_new_entries():
                await process_transfer(event, channel)
            time.sleep(2)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)

async def process_swap(event, channel):
    args = event.args
    amount0In = args['amount0In']
    amount1In = args['amount1In']
    amount0Out = args['amount0Out']
    amount1Out = args['amount1Out']
    tx_hash = event.transactionHash.hex()

    if gainz_is_token0:
        if amount0In > 0 and amount1Out > 0:   # SELL
            direction = "🔴 **SELL**"
            gainz_amount = amount0In / (10 ** gainz_decimals)
            cro_amount = amount1Out / (10 ** wcro_decimals)
        elif amount1In > 0 and amount0Out > 0:  # BUY
            direction = "🟢 **BUY**"
            gainz_amount = amount0Out / (10 ** gainz_decimals)
            cro_amount = amount1In / (10 ** wcro_decimals)
        else:
            return
    else:
        return

    usd_value = gainz_amount * (cro_amount / gainz_amount) * WCRO_USD_PRICE if gainz_amount > 0 else 0

    embed = discord.Embed(title=f"{direction} $GAINZ (VVS Pair)", color=0x00ff00 if "BUY" in direction else 0xff0000)
    embed.description = f"**{gainz_amount:,.2f} GAINZ** for **{cro_amount:,.4f} WCRO**"
    embed.add_field(name="Value", value=f"≈ **${usd_value:,.2f}**", inline=True)
    embed.add_field(name="Links", value=f"[📊 DexScreener Chart](https://dexscreener.com/cronos/0xF7b1095D2af6C81c2d88f0ab44c7c2341BFfc411)\n[🔗 Tx](https://explorer.cronos.org/tx/0x{tx_hash})", inline=False)
    embed.set_footer(text="Direct VVS Trade • Rough USD • Monkey Muscle 🦧")

    await channel.send(embed=embed)

async def process_transfer(event, channel):
    tx_hash = event.transactionHash.hex()
    current_time = time.time()

    if tx_hash in seen_tx and current_time - seen_tx[tx_hash] < 30:
        return
    seen_tx[tx_hash] = current_time

    amount = event.args['value'] / (10 ** gainz_decimals)
    if amount < 300:   # Minimum amount for transfer alerts
        return

    from_addr = event.args['from']
    to_addr = event.args['to']

    usd_value = amount * 0.0005   # Very rough estimate (adjust if you know better price)

    direction = "🔄 **GAINZ Transfer (Aggregator Hop)**"
    color = 0xaaaaaa

    embed = discord.Embed(title=direction, description=f"**{amount:,.2f} GAINZ**", color=color)
    embed.add_field(name="Value", value=f"≈ **${usd_value:,.2f}**", inline=True)
    embed.add_field(name="From", value=f"`{from_addr[:10]}...`", inline=True)
    embed.add_field(name="To", value=f"`{to_addr[:10]}...`", inline=True)
    embed.add_field(name="Links", value=f"[📊 Chart](https://dexscreener.com/cronos/0xF7b1095D2af6C81c2d88f0ab44c7c2341BFfc411)\n[🔗 Tx](https://explorer.cronos.org/tx/0x{tx_hash})", inline=False)
    embed.set_footer(text="Detected via Transfer • Likely WolfSwap Aggregator • Rough USD • Monkey Muscle 🦧")

    await channel.send(embed=embed)

client.run(DISCORD_TOKEN)
