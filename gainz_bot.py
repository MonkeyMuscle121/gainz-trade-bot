import os
import time
import discord
from dotenv import load_dotenv
from web3 import Web3

load_dotenv()

# ================== CONFIG ==================
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
CHANNEL_ID = int(os.getenv('CHANNEL_ID'))

# Cronos settings
RPC_URL = "https://cronos-evm-rpc.publicnode.com"

# Token & Pair (GAINZ on Cronos) - CORRECT CHECKSUMMED ADDRESSES
TOKEN_ADDRESS = "0xF7b1095D2af6C81c2d88f0ab44c7c2341BFfc411"
PAIR_ADDRESS  = "0x3a26c936973635dFF0a89ca93E4e62f70514c210"

# Minimal ABI
ERC20_ABI = [
    {"constant": True, "inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "symbol", "outputs": [{"name": "", "type": "string"}], "type": "function"}
]

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

# Connect to Cronos
w3 = Web3(Web3.HTTPProvider(RPC_URL))

# Load contracts
pair_contract = w3.eth.contract(address=PAIR_ADDRESS, abi=PAIR_ABI)
token0 = pair_contract.functions.token0().call().lower()
token1 = pair_contract.functions.token1().call().lower()

if token0 == TOKEN_ADDRESS.lower():
    gainz_is_token0 = True
    gainz_decimals = w3.eth.contract(address=TOKEN_ADDRESS, abi=ERC20_ABI).functions.decimals().call()
    wcro_decimals = 18
else:
    gainz_is_token0 = False
    gainz_decimals = w3.eth.contract(address=TOKEN_ADDRESS, abi=ERC20_ABI).functions.decimals().call()
    wcro_decimals = 18

print(f"✅ Bot ready! GAINZ decimals: {gainz_decimals}")

# Discord bot
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f"✅ Bot logged in as {client.user}")
    channel = client.get_channel(CHANNEL_ID)
    if channel:
        await channel.send("🚀 **GAINZ Trade Bot is now online and monitoring buys/sells on VVS!**")
    await monitor_trades(channel)

async def monitor_trades(channel):
    swap_filter = pair_contract.events.Swap.create_filter(fromBlock="latest")
    while True:
        try:
            for event in swap_filter.get_new_entries():
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
                        continue
                else:
                    if amount1In > 0 and amount0Out > 0:   # SELL
                        direction = "🔴 **SELL**"
                        gainz_amount = amount1In / (10 ** gainz_decimals)
                        cro_amount = amount0Out / (10 ** wcro_decimals)
                    elif amount0In > 0 and amount1Out > 0:  # BUY
                        direction = "🟢 **BUY**"
                        gainz_amount = amount1Out / (10 ** gainz_decimals)
                        cro_amount = amount0In / (10 ** wcro_decimals)
                    else:
                        continue

                embed = discord.Embed(
                    title=f"{direction} $GAINZ",
                    description=f"**{gainz_amount:,.2f} GAINZ** for **{cro_amount:,.4f} WCRO**",
                    color=0x00ff00 if "BUY" in direction else 0xff0000
                )
                embed.add_field(name="Transaction", value=f"[View on Cronos Explorer](https://explorer.cronos.org/tx/0x{tx_hash})", inline=False)
                embed.set_footer(text="VVS Finance • Monkey Muscle")
                await channel.send(embed=embed)
            
            time.sleep(2)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)

client.run(DISCORD_TOKEN)
