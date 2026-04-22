import os
import time
import discord
from dotenv import load_dotenv
from web3 import Web3

load_dotenv()

# ================== CONFIG ==================
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
CHANNEL_ID = int(os.getenv('CHANNEL_ID'))

# Cronos RPC
RPC_URL = "https://cronos-evm-rpc.publicnode.com"

# GAINZ Token
TOKEN_ADDRESS = "0xF7b1095D2af6C81c2d88f0ab44c7c2341BFfc411"

# Force checksum
w3 = Web3(Web3.HTTPProvider(RPC_URL))
TOKEN_ADDRESS = w3.to_checksum_address(TOKEN_ADDRESS)

# ABI for Transfer events + decimals
TOKEN_ABI = [
    {"constant": True, "inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "type": "function"},
    {"anonymous": False, "inputs": [
        {"indexed": True, "name": "from", "type": "address"},
        {"indexed": True, "name": "to", "type": "address"},
        {"indexed": False, "name": "value", "type": "uint256"}
    ], "name": "Transfer", "type": "event"}
]

print("✅ Loading GAINZ token contract...")

token_contract = w3.eth.contract(address=TOKEN_ADDRESS, abi=TOKEN_ABI)
gainz_decimals = token_contract.functions.decimals().call()

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
        await channel.send("🚀 **GAINZ Universal Trade Bot is now online!** Monitoring ALL trades involving $GAINZ (any pair/DEX)")
    await monitor_transfers(channel)

async def monitor_transfers(channel):
    transfer_filter = token_contract.events.Transfer.create_filter(from_block="latest")
    
    while True:
        try:
            for event in transfer_filter.get_new_entries():
                await process_transfer(event, channel)
            time.sleep(2)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)

async def process_transfer(event, channel):
    args = event.args
    from_addr = args['from']
    to_addr = args['to']
    value = args['value']
    
    amount = value / (10 ** gainz_decimals)
    
    # Skip very small transfers (noise filter - adjust if needed)
    if amount < 100:   # change 100 to smaller number if you want tiny trades too
        return
    
    # Simple heuristic: if "to" is a known router or pair, guess direction
    # For now we show direction as "Transferred" – we can improve later
    if from_addr.lower() in ["0x0000000000000000000000000000000000000000", "0xdeaddeaddeaddeaddeaddeaddeaddeaddeaddead"]:
        direction = "🟢 **MINT / ADD**"
        color = 0x00ff00
    else:
        direction = "🔴 **SELL / TRANSFER**" if amount > 1000 else "🔄 **TRANSFER**"
        color = 0xff0000 if "SELL" in direction else 0xaaaaaa
    
    tx_hash = event.transactionHash.hex()
    
    embed = discord.Embed(
        title=f"{direction} $GAINZ",
        description=f"**{amount:,.2f} GAINZ**",
        color=color
    )
    embed.add_field(name="From", value=f"`{from_addr[:8]}...{from_addr[-6:]}`", inline=True)
    embed.add_field(name="To", value=f"`{to_addr[:8]}...{to_addr[-6:]}`", inline=True)
    embed.add_field(name="Transaction", value=f"[View on Explorer](https://explorer.cronos.org/tx/0x{tx_hash})", inline=False)
    embed.set_footer(text="Monitoring ALL GAINZ transfers • WolfSwap + VVS + others • Monkey Muscle 🦧")
    
    await channel.send(embed=embed)

client.run(DISCORD_TOKEN)
