import os
import json
from web3 import Web3
from eth_account import Account
from dotenv import load_dotenv
import time
import secrets
from eth_utils import keccak, to_bytes
from typing import List
from decimal import Decimal
from app.models.presale import Presale
from sqlalchemy import select

# Load .env
load_dotenv()

RPC_URL = os.getenv("RPC_URL")
TRACE_RPC_URL = os.getenv("TRACE_RPC_URL")

PORTAL_ADDRESS = os.getenv("PORTAL")
TOKEN_IMPL_ADDRESS = os.getenv("TOKEN_IMPL")

if not RPC_URL:
    raise Exception("RPC_URL not set")
CONTROLLER_ADDRESS = os.getenv("YZAI_CONTROLLER_ADDRESS")
OWNER_PK = os.getenv("YZAI_OWNER_PRIVATE_KEY")

if not RPC_URL:
    raise Exception("RPC_URL not set")

if not CONTROLLER_ADDRESS:
    raise Exception("YZAI_CONTROLLER_ADDRESS not set")

w3 = Web3(Web3.HTTPProvider(RPC_URL))
trace_w3 = Web3(Web3.HTTPProvider(TRACE_RPC_URL))

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
ABI_PATH = os.path.join(BASE_DIR, "abi", "YZAIController.json")

with open(ABI_PATH) as f:
    CONTROLLER_ABI = json.load(f)

controller = w3.eth.contract(
    address=Web3.to_checksum_address(CONTROLLER_ADDRESS),
    abi=CONTROLLER_ABI
)

PORTAL = Web3.to_checksum_address(PORTAL_ADDRESS)
TOKEN_IMPL = Web3.to_checksum_address(TOKEN_IMPL_ADDRESS)

PORTAL_ABI_PATH = os.path.join(BASE_DIR, "abi", "portal.json")

with open(PORTAL_ABI_PATH) as f:
    PORTAL_ABI = json.load(f)

portal = w3.eth.contract(
    address=PORTAL,
    abi=PORTAL_ABI
)

PRESALE_ADDRESS = os.getenv("YZAI_PRESALE_ADDRESS")

if not PRESALE_ADDRESS:
    raise Exception("YZAI_PRESALE_ADDRESS not set")

PRESALE = Web3.to_checksum_address(PRESALE_ADDRESS)

PRESALE_ABI_PATH = os.path.join(BASE_DIR, "abi", "presale.json")

with open(PRESALE_ABI_PATH) as f:
    PRESALE_ABI = json.load(f)

presale = w3.eth.contract(
    address=PRESALE,
    abi=PRESALE_ABI
)

TOKEN_STATUS = {
    0: "Invalid",
    1: "Tradable",
    2: "InDuel",
    3: "Killed",
    4: "DEX",
    5: "Presale"
}

ERC20_ABI = [
    {
        "constant": False,
        "inputs": [
            {"name": "spender", "type": "address"},
            {"name": "amount", "type": "uint256"}
        ],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [
            {"name": "owner", "type": "address"},
            {"name": "spender", "type": "address"}
        ],
        "name": "allowance",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function"
    }
]

PANCAKE_ROUTER = Web3.to_checksum_address(
    "0x10ED43C718714eb63d5aA57B78B54704E256024E"
)

WBNB = Web3.to_checksum_address(
    "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"
)

SWAP_ABI_PATH = os.path.join(BASE_DIR, "abi", "swap.json")

with open(SWAP_ABI_PATH) as f:
    SWAP_ABI = json.load(f)

router = w3.eth.contract(
    address=PANCAKE_ROUTER,
    abi=SWAP_ABI
)

def predict_create2_address(salt: bytes) -> str:

    bytecode = (
        "0x3d602d80600a3d3981f3363d3d373d3d3d363d73"
        + TOKEN_IMPL[2:].lower()
        + "5af43d82803e903d91602b57fd5bf3"
    )

    bytecode_hash = keccak(hexstr=bytecode)

    packed = b'\xff' + to_bytes(hexstr=PORTAL) + salt + bytecode_hash
    address_bytes = keccak(packed)[12:]

    return Web3.to_checksum_address(address_bytes.hex())

def find_vanity_salt(suffix="7777"):

    iterations = 0

    seed = secrets.token_bytes(32)
    salt = keccak(seed)

    while True:
        predicted = predict_create2_address(salt)

        if predicted.lower().endswith(suffix):
            return {
                "salt": salt,
                "address": predicted,
                "iterations": iterations
            }

        salt = keccak(salt)
        iterations += 1

def build_sale_params(proposal, presale_data):

    vanity = find_vanity_salt("7777")

    sale_params = {
        "salt": vanity["salt"],
        "startTime": int(presale_data.start_time.timestamp()),
        "endTime": int(presale_data.end_time.timestamp()),
        "minBuy": Web3.to_wei(presale_data.min_buy_bnb, "ether"),
        "maxBuy": Web3.to_wei(presale_data.max_buy_bnb, "ether"),

        "dexId": 0,
        "raiseAmt": Web3.to_wei(proposal.raise_amount, "ether"),
        "taxRate": 300,
        "enableWhitelist": presale_data.enable_whitelist,

        "meta": proposal.meta or "",
        "name": proposal.name,
        "symbol": proposal.ticker,
        "beneficiary": Web3.to_checksum_address(proposal.beneficiary_address),

        "taxDuration": 3153600000,
        "antiFarmerDuration": 259200,

        "mktBps": int(proposal.treasury * 100),
        "deflationBps": int(proposal.burn * 100),
        "dividendBps": int(proposal.buyback * 100),
        "lpBps": int(proposal.liquidity * 100),

        "minimumShareBalance": 10000000000000000000000
    }

    return sale_params, vanity["address"]

def wait_and_extract_sale(tx_hash: str):

    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

    logs = controller.events.SaleCreated().process_receipt(receipt)

    if not logs:
        raise Exception("SaleCreated event not found")

    token_address = logs[0]["args"]["token"]
    agent_address = logs[0]["args"]["agent"]

    return token_address, agent_address

def extract_created_contracts(tx_hash: str):

    trace = trace_w3.provider.make_request(
        "debug_traceTransaction",
        [tx_hash, {"tracer": "callTracer", "timeout": "60s"}]
    )

    if "result" not in trace:
        raise Exception("debug_traceTransaction not supported")

    created_addresses = []

    def walk(call_obj):

        if call_obj.get("type") == "CREATE":
            address = call_obj.get("to")
            if address:
                created_addresses.append(
                    Web3.to_checksum_address(address)
                )

        for sub in call_obj.get("calls", []) or []:
            walk(sub)

    walk(trace["result"])

    return created_addresses

def get_sale_proxy_from_tx(tx_hash: str):

    created = extract_created_contracts(tx_hash)

    if not created:
        raise Exception("No CREATE found")

    return created[0]

def get_sale_info(token_address: str):
    token = Web3.to_checksum_address(token_address)
    return controller.functions.getSaleInfo(token).call()

# ================================
# Check Approved
# ================================
def is_agent_approved(agent_address: str) -> bool:
    agent = Web3.to_checksum_address(agent_address)
    return controller.functions.approvedAgents(agent).call()

# ================================
# Approve Agent (Owner Only)
# ================================
def approve_agent(agent_address: str):

    if not OWNER_PK:
        raise Exception("Owner private key not set")

    agent = Web3.to_checksum_address(agent_address)
    owner_account = Account.from_key(OWNER_PK)

    nonce = w3.eth.get_transaction_count(owner_account.address)

    tx = controller.functions.approveAgent(agent).build_transaction({
        "from": owner_account.address,
        "nonce": nonce,
        "gas": 200000,
        "gasPrice": w3.eth.gas_price,
        "chainId": w3.eth.chain_id
    })

    signed_tx = owner_account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

    return tx_hash.hex()


# ================================
# Create Sale (Owner Only)
# ================================
def create_sale(agent_private_key: str, sale_params: dict, value_eth: float):

    account = Account.from_key(agent_private_key)
    nonce = w3.eth.get_transaction_count(account.address)

    tx = controller.functions.createSale(sale_params).build_transaction({
        "from": account.address,
        "value": w3.to_wei(value_eth, "ether"),
        "nonce": nonce,
        "gas": 1500000,
        "gasPrice": w3.eth.gas_price,
        "chainId": w3.eth.chain_id
    })

    signed_tx = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

    return tx_hash.hex()

# ================================
# Emergency Cancel Presale
# ================================
def emergency_cancel(
    agent_private_key: str,
    token_address: str
):

    account = Account.from_key(agent_private_key)

    token = Web3.to_checksum_address(token_address)

    nonce = w3.eth.get_transaction_count(account.address)

    tx = controller.functions.emergencyCancel(token).build_transaction({
        "from": account.address,
        "nonce": nonce,
        "gas": 300000,
        "gasPrice": w3.eth.gas_price,
        "chainId": w3.eth.chain_id
    })

    signed_tx = account.sign_transaction(tx)

    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

    return tx_hash.hex()

# ================================
# Add To Whitelist (Owner Only)
# ================================
def add_to_whitelist(
    agent_private_key: str,
    token_address: str,
    users: List[str]
):

    account = Account.from_key(agent_private_key)
    token = Web3.to_checksum_address(token_address)
    checksum_users = [Web3.to_checksum_address(u) for u in users]

    nonce = w3.eth.get_transaction_count(account.address)

    tx = controller.functions.addToWhitelist(
        token,
        checksum_users
    ).build_transaction({
        "from": account.address,
        "nonce": nonce,
        "gas": 300000,
        "gasPrice": w3.eth.gas_price,
        "chainId": w3.eth.chain_id
    })

    signed_tx = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

    return tx_hash.hex()

# ================================
# Get Token Distribution Progress
# ================================
def get_token_distribution_progress(token_address: str):

    token = Web3.to_checksum_address(token_address)

    distributed, total = controller.functions.getTokenDistributionProgress(
        token
    ).call()

    return {
        "distributed": distributed,
        "total": total
    }

# ================================
# Claim Tokens (Agent Wallet)
# ================================
def claim_tokens(
    agent_private_key: str,
    token_address: str
):

    account = Account.from_key(agent_private_key)
    token = Web3.to_checksum_address(token_address)

    nonce = w3.eth.get_transaction_count(account.address)

    tx = controller.functions.claimTokens(
        token
    ).build_transaction({
        "from": account.address,
        "nonce": nonce,
        "gas": 300000,
        "gasPrice": w3.eth.gas_price,
        "chainId": w3.eth.chain_id
    })

    signed_tx = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

    return tx_hash.hex()


# ================================
# Get Refund (Agent Wallet)
# ================================
def get_refund(
    agent_private_key: str,
    token_address: str
):

    account = Account.from_key(agent_private_key)
    token = Web3.to_checksum_address(token_address)

    nonce = w3.eth.get_transaction_count(account.address)

    tx = controller.functions.getRefund(
        token
    ).build_transaction({
        "from": account.address,
        "nonce": nonce,
        "gas": 300000,
        "gasPrice": w3.eth.gas_price,
        "chainId": w3.eth.chain_id
    })

    signed_tx = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

    return tx_hash.hex()


# ================================
# Finalize Sale and Distribute (Owner Only)
# ================================
def finalize_sale_and_distribute(
    agent_private_key: str,
    token_address: str,
    limit: int
):

    account = Account.from_key(agent_private_key)
    token = Web3.to_checksum_address(token_address)

    nonce = w3.eth.get_transaction_count(account.address)

    tx = controller.functions.finalizeSaleAndDistribute(
        token,
        limit
    ).build_transaction({
        "from": account.address,
        "nonce": nonce,
        "gas": 600000,
        "gasPrice": w3.eth.gas_price,
        "chainId": w3.eth.chain_id
    })

    signed_tx = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

    return tx_hash.hex()


# ================================
# Remove From Whitelist (Agent Wallet)
# ================================
def remove_from_whitelist(
    agent_private_key: str,
    token_address: str,
    users: List[str]
):

    account = Account.from_key(agent_private_key)
    token = Web3.to_checksum_address(token_address)
    checksum_users = [Web3.to_checksum_address(u) for u in users]

    nonce = w3.eth.get_transaction_count(account.address)

    tx = controller.functions.removeFromWhitelist(
        token,
        checksum_users
    ).build_transaction({
        "from": account.address,
        "nonce": nonce,
        "gas": 300000,
        "gasPrice": w3.eth.gas_price,
        "chainId": w3.eth.chain_id
    })

    signed_tx = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

    return tx_hash.hex()

# ================================
# Get Participants (Paginated)
# ================================
def get_participants(token_address: str, offset: int, limit: int):

    token = Web3.to_checksum_address(token_address)

    participants, amounts, total = controller.functions.getParticipants(
        token,
        offset,
        limit
    ).call()

    return {
        "participants": participants,
        "amounts": amounts,
        "total": total
    }


# ================================
# Get Participant Count
# ================================
def get_participant_count(token_address: str):

    token = Web3.to_checksum_address(token_address)
    return controller.functions.getParticipantCount(token).call()

# ================================
# Transfer BNB (Agent Wallet)
# ================================
def transfer_bnb(
    agent_private_key: str,
    to_address: str,
    amount_bnb: float
):

    account = Account.from_key(agent_private_key)
    to_checksum = Web3.to_checksum_address(to_address)

    nonce = w3.eth.get_transaction_count(account.address)

    tx = {
        "to": to_checksum,
        "value": w3.to_wei(amount_bnb, "ether"),
        "nonce": nonce,
        "gas": 210000,
        "gasPrice": w3.eth.gas_price,
        "chainId": w3.eth.chain_id
    }

    signed_tx = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

    return tx_hash.hex()

# ================================
# Get All Sales
# ================================
async def get_all_sales(db=None):

    # =========================
    # 1. ONCHAIN SALES
    # =========================
    sales = controller.functions.getAllSales().call()

    controller_tokens = set([
        Web3.to_checksum_address(addr)
        for addr in sales
    ])

    all_tokens = set(controller_tokens)

    # =========================
    # 2. DB PRESALE TOKENS
    # =========================
    if db:

        result = await db.execute(
            select(Presale.token_address)
        )

        db_tokens = [
            row[0]
            for row in result.fetchall()
            if row[0] and row[0] != "TBA"
        ]

        for t in db_tokens:
            try:
                checksum = Web3.to_checksum_address(t)
                all_tokens.add(checksum)
            except:
                pass

    # =========================
    # 3. RETURN MERGED TOKENS
    # =========================
    return list(all_tokens)

# ================================
# GetToken Status
# ================================
def get_token_v5(token_address: str):

    token = Web3.to_checksum_address(token_address)

    data = portal.functions.getTokenV5(token).call()

    status = data[0]
    price_raw = data[3]

    price = Decimal(price_raw) / Decimal(10**18)

    price_str = format(price, "f")

    return {
        "token": token,
        "status": TOKEN_STATUS.get(status, "Unknown"),

        "reserve": data[1],
        "circulating_supply": data[2],
        "price_raw": str(price_raw),
        "price": price_str,

        "token_version": data[4],

        "curve": {
            "r": data[5],
            "h": data[6],
            "k": data[7]
        },

        "dex_supply_threshold": data[8],

        "quote_token": data[9],
        "native_to_quote_swap_enabled": data[10],

        "extension_id": data[11]
    }

async def get_tokens_batch(db=None):

    # =========================
    # 1. CONTROLLER TOKENS
    # =========================
    controller_sales = await get_all_sales(db)

    controller_tokens = set([
        Web3.to_checksum_address(t)
        for t in controller_sales
    ])

    all_tokens = set(controller_tokens)

    # =========================
    # 2. GET ALL TOKENS FROM DB
    # =========================
    result = await db.execute(
        select(Presale.token_address)
    )

    db_tokens = [
        row[0]
        for row in result.fetchall()
        if row[0] and row[0] != "TBA"
    ]

    # =========================
    # 3. IDENTIFY YZAI TOKENS
    # =========================
    yzai_tokens = []

    for t in db_tokens:
        try:
            checksum = Web3.to_checksum_address(t)

            if checksum not in controller_tokens:
                yzai_tokens.append(checksum)

            all_tokens.add(checksum)

        except:
            pass

    # =========================
    # 3. FETCH TOKEN DATA
    # =========================
    results = []

    for token in all_tokens:

        try:

            token_data = get_token_v5(token)

            results.append(token_data)

        except Exception as e:

            results.append({
                "token": token,
                "error": str(e)
            })

    return results

def approve_token_if_needed(
    agent_private_key: str,
    token_address: str,
    amount: int
):

    account = Account.from_key(agent_private_key)
    token = Web3.to_checksum_address(token_address)

    erc20 = w3.eth.contract(address=token, abi=ERC20_ABI)

    allowance = erc20.functions.allowance(
        account.address,
        PANCAKE_ROUTER
    ).call()

    if allowance >= amount:
        return None

    nonce = w3.eth.get_transaction_count(account.address)

    tx = erc20.functions.approve(
        PANCAKE_ROUTER,
        2**256 - 1
    ).build_transaction({
        "from": account.address,
        "nonce": nonce,
        "gas": 120000,
        "gasPrice": w3.eth.gas_price,
        "chainId": w3.eth.chain_id
    })

    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)

    return tx_hash.hex()

# ================================
# Swap Exact Input (Bonding Curve)
# ================================
def swap_exact_input(
    agent_private_key: str,
    token_address: str,
    trade_type: str,
    input_amount: int,
    min_output_amount: int = 0
):

    account = Account.from_key(agent_private_key)

    token = Web3.to_checksum_address(token_address)

    if trade_type == "BUY":

        input_token = "0x0000000000000000000000000000000000000000"
        output_token = token
        payable_amount = input_amount

    elif trade_type == "SELL":

        input_token = token
        output_token = "0x0000000000000000000000000000000000000000"
        payable_amount = 0

    else:
        raise Exception("Invalid trade type")
    
    # approve first
    approve_token_if_needed(
        agent_private_key,
        token,
        input_amount
    )

    time.sleep(5)

    nonce = w3.eth.get_transaction_count(account.address)

    params = (
        Web3.to_checksum_address(input_token),
        Web3.to_checksum_address(output_token),
        input_amount,
        min_output_amount,
        b""
    )

    tx = portal.functions.swapExactInput(params).build_transaction({
        "from": account.address,
        "value": payable_amount,
        "nonce": nonce,
        "gas": 600000,
        "gasPrice": w3.eth.gas_price,
        "chainId": w3.eth.chain_id
    })

    signed_tx = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

    return tx_hash.hex()

def swap_bnb_to_token(
    agent_private_key: str,
    token_address: str,
    amount_bnb: float,
    min_output_amount: int = 0
):

    account = Account.from_key(agent_private_key)

    token = Web3.to_checksum_address(token_address)

    nonce = w3.eth.get_transaction_count(account.address)

    path = [
        WBNB,
        token
    ]

    deadline = int(time.time()) + 300

    tx = router.functions.swapExactETHForTokensSupportingFeeOnTransferTokens(
        min_output_amount,
        path,
        account.address,
        deadline
    ).build_transaction({
        "from": account.address,
        "value": w3.to_wei(amount_bnb, "ether"),
        "nonce": nonce,
        "gas": 600000,
        "gasPrice": w3.eth.gas_price,
        "chainId": w3.eth.chain_id
    })

    signed_tx = account.sign_transaction(tx)

    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

    return tx_hash.hex()

def swap_token_to_bnb(
    agent_private_key: str,
    token_address: str,
    amount_token: int,
    min_output_amount: int = 0
):

    account = Account.from_key(agent_private_key)

    token = Web3.to_checksum_address(token_address)

    # approve first
    approve_token_if_needed(
        agent_private_key,
        token,
        amount_token
    )

    time.sleep(5)

    nonce = w3.eth.get_transaction_count(account.address)

    path = [
        token,
        WBNB
    ]

    deadline = int(time.time()) + 300

    tx = router.functions.swapExactTokensForETHSupportingFeeOnTransferTokens(
        amount_token,
        min_output_amount,
        path,
        account.address,
        deadline
    ).build_transaction({
        "from": account.address,
        "nonce": nonce,
        "gas": 600000,
        "gasPrice": w3.eth.gas_price,
        "chainId": w3.eth.chain_id
    })

    signed_tx = account.sign_transaction(tx)

    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

    return tx_hash.hex()


# ================================
# Treasury Balance
# ================================

TREASURY_VAULT = Web3.to_checksum_address(
    "0x1853811024bFe9612494b45aec66d60239B893aF"
)

TREASURY_WALLET = Web3.to_checksum_address(
    "0xb76E58875779E4aC63a6Ff68F6c5a3dea7c9dFa1"
)


def get_treasury_balances():

    from app.core.balance import get_bnb_balance, get_bnb_price

    vault_bnb = get_bnb_balance(TREASURY_VAULT)
    wallet_bnb = get_bnb_balance(TREASURY_WALLET)

    price = get_bnb_price()

    vault_usd = vault_bnb * price
    wallet_usd = wallet_bnb * price

    total_bnb = vault_bnb + wallet_bnb
    total_usd = vault_usd + wallet_usd

    return {
        "bnb_price": float(price),

        "treasury_vault": {
            "address": TREASURY_VAULT,
            "bnb": float(vault_bnb),
            "usd": float(vault_usd)
        },

        "actual_treasury_wallet": {
            "address": TREASURY_WALLET,
            "bnb": float(wallet_bnb),
            "usd": float(wallet_usd)
        },

        "total": {
            "bnb": float(total_bnb),
            "usd": float(total_usd)
        }
    }

# ================================
# YZAI
# ================================

def initiate_presale(
    start_time: int,
    end_time: int,
    min_buy_bnb: float,
    max_buy_bnb: float
):

    if not OWNER_PK:
        raise Exception("Owner private key not set")

    account = Account.from_key(OWNER_PK)

    nonce = w3.eth.get_transaction_count(account.address)

    tx = presale.functions.initiatePresale(
        start_time,
        end_time,
        w3.to_wei(min_buy_bnb, "ether"),
        w3.to_wei(max_buy_bnb, "ether")
    ).build_transaction({
        "from": account.address,
        "nonce": nonce,
        "gas": 300000,
        "gasPrice": w3.eth.gas_price,
        "chainId": w3.eth.chain_id
    })

    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)

    return tx_hash.hex()

def add_whitelist(users: list[str]):

    if not OWNER_PK:
        raise Exception("Owner private key not set")

    account = Account.from_key(OWNER_PK)

    checksum_users = [Web3.to_checksum_address(u) for u in users]

    nonce = w3.eth.get_transaction_count(account.address)

    tx = presale.functions.addWhitelist(
        checksum_users
    ).build_transaction({
        "from": account.address,
        "nonce": nonce,
        "gas": 500000,
        "gasPrice": w3.eth.gas_price,
        "chainId": w3.eth.chain_id
    })

    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)

    return tx_hash.hex()

def contribute(
    agent_private_key: str,
    amount_bnb: float
):

    account = Account.from_key(agent_private_key)

    nonce = w3.eth.get_transaction_count(account.address)

    tx = presale.functions.contribute().build_transaction({
        "from": account.address,
        "value": w3.to_wei(amount_bnb, "ether"),
        "nonce": nonce,
        "gas": 300000,
        "gasPrice": w3.eth.gas_price,
        "chainId": w3.eth.chain_id
    })

    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)

    return tx_hash.hex()

def get_presale_info():

    data = presale.functions.getPresaleInfo().call()

    return {
        "total_raised": data[0],
        "start_time": data[1],
        "end_time": data[2],
        "min_buy": data[3],
        "max_buy": data[4],
        "initialized": data[5],
        "started": data[6],
        "paused": data[7],
    }

def get_whitelist():

    addresses = presale.functions.getWhitelist().call()

    return [
        Web3.to_checksum_address(addr)
        for addr in addresses
    ]

def get_participants():

    participants, amounts = presale.functions.getParticipants().call()

    result = []

    for i in range(len(participants)):
        result.append({
            "address": Web3.to_checksum_address(participants[i]),
            "amount": amounts[i]
        })

    return result