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

# Token & Pair (GAINZ on Cronos) - Raw addresses
TOKEN_ADDRESS = "0xF7b1095D2af6C81c2d88f0ab44c7c2341BFfc411"
PAIR_ADDRESS  = "0x3a26c936973635dff0a89ca93e4e62f70514c210"

# Convert to proper checksum addresses (this fixes the InvalidAddress error)
TOKEN_ADDRESS = Web3.to_checksum_address(TOKEN_ADDRESS)
PAIR_ADDRESS  = Web3.to_checksum_address(PAIR_ADDRESS)

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
    channel = client
