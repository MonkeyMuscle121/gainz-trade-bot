import os
import asyncio
import discord
from dotenv import load_dotenv
from web3 import Web3

load_dotenv()

# ================== CONFIG ==================
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
CHANNEL_ID = int(os.getenv('CHANNEL_ID'))

RPC_URL = "https://cronos-evm-rpc.publicnode.com"
TOKEN_ADDRESS = "0xF7b1095D2af6C81c2d88f0ab44c7c2341BFfc411"
PAIR_ADDRESS = "0x3a26c936973635dff0a89ca93e4e62f70514c210"

w3 = Web3(Web3.HTTPProvider(RPC_URL, request_kwargs={'timeout': 30}))
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

print("✅ GAINZ Buy Bot initialized")

intents = discord.Intents.default()
client = discord.Client(intents=intents)
channel = None

@client.event
async def on_ready():
    global channel
    print(f"✅ Logged in as {client.user}")
    channel = client.get_channel(CHANNEL_ID)
    
    if channel:
        await channel.send("🚀 **GAINZ Buy Bot is now online!** Only BUY alerts • Paid Render")
    
    asyncio.create_task(monitor_trades())

async def monitor_trades():
    global channel
    print("📡 Monitoring started...")

    while True:
        try:
            swap_filter = pair_contract.events.Swap.create_filter(from_block="latest")
            
            while True:
                for event in swap_filter.get_new_entries():
                    await process_buy(event)
                
                await asyncio.sleep(1.5)   # Faster polling on paid tier

        except Exception as e:
            print(f"🔴 Monitor error: {e}")
            await asyncio.sleep(15)

async def process_buy(event):
    global channel
    if not channel: 
        return

    args = event.args
    tx_hash = event.transactionHash.hex()

    if gainz_is_token0:
        if args['amount1In'] > 0 and args['amount0Out'] > 0:   # Buy GAINZ
            gainz_amount = args['amount0Out'] / (10 ** gainz_decimals)
            cro_amount = args['amount1In'] / 1e18
        else:
            return
    else:
        if args['amount0In'] > 0 and args['amount1Out'] > 0:
            gainz_amount = args['amount1Out'] / (10 ** gainz_decimals)
            cro_amount = args['amount0In'] / 1e18
        else:
            return

    if gainz_amount < 100:   # Minimum size filter
        return

    embed = discord.Embed(
        title="🟢 **BUY** $GAINZ",
        description=f"**{gainz_amount:,.2f} GAINZ** for **{cro_amount:,.4f} WCRO**",
        color=0x00ff00
    )
    embed.add_field(
        name="Links",
        value=f"[📊 DexScreener](https://dexscreener.com/cronos/0xF7b1095D2af6C81c2d88f0ab44c7c2341BFfc411)\n"
              f"[🔗 Tx Explorer](https://explorer.cronos.org/tx/0x{tx_hash})",
        inline=False
    )
    embed.set_footer(text="VVS Finance • BUY alerts only • Paid Render")

    try:
        await channel.send(embed=embed)
    except Exception as e:
        print(f"Discord send failed: {e}")

client.run(DISCORD_TOKEN)
