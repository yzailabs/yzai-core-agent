from web3 import Web3
from app.ai.config import BSC_RPC_URL

w3 = Web3(Web3.HTTPProvider(BSC_RPC_URL))

async def get_bnb_balance(address: str) -> float:
    balance_wei = w3.eth.get_balance(address)
    balance_bnb = w3.from_wei(balance_wei, "ether")
    return float(balance_bnb)