import requests
from fastapi import APIRouter, Depends, HTTPException
from decimal import Decimal
from web3 import Web3
from dotenv import load_dotenv
from app.core.onchain import get_all_sales
from app.core.pnl import calculate_unrealized
import uuid
from datetime import datetime
from app.models.portfolio_snapshot import PortfolioSnapshot
from app.models.token_holding import TokenHolding
import os 
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import AsyncSessionLocal

load_dotenv()

DEX_API = "https://api.dexscreener.com/latest/dex/tokens"

RPC_URL = os.getenv("RPC_URL")
w3 = Web3(Web3.HTTPProvider(RPC_URL))

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

def get_bnb_balance(address: str):

    checksum = Web3.to_checksum_address(address)

    balance = w3.eth.get_balance(checksum)

    return Decimal(balance) / Decimal(10 ** 18)

def get_bnb_price():

    try:

        url = f"{DEX_API}/0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c"

        res = requests.get(url, timeout=10)

        data = res.json()

        pairs = data.get("pairs")

        if not pairs:
            return Decimal(0)

        return Decimal(pairs[0]["priceUsd"])

    except:
        return Decimal(0)
    
def clean_decimal(value):
    return float(value)

def get_token_price(token: str):

    try:

        url = f"{DEX_API}/{token}"

        res = requests.get(url, timeout=10)

        data = res.json()

        pairs = data.get("pairs")

        if not pairs:
            return Decimal(0)

        price = pairs[0]["priceUsd"]

        return Decimal(price)

    except:
        return Decimal(0)


async def get_token_holdings(address: str,db: AsyncSession = Depends(get_db)):

    tokens = await get_all_sales(db)

    results = []

    for token in tokens:

        try:

            token_data = w3.eth.contract(
                address=Web3.to_checksum_address(token),
                abi=[
                    {
                        "constant": True,
                        "inputs": [{"name": "_owner", "type": "address"}],
                        "name": "balanceOf",
                        "outputs": [{"name": "balance", "type": "uint256"}],
                        "type": "function"
                    },
                    {
                        "constant": True,
                        "inputs": [],
                        "name": "decimals",
                        "outputs": [{"name": "", "type": "uint8"}],
                        "type": "function"
                    }
                ]
            )

            raw = token_data.functions.balanceOf(address).call()

            decimals = token_data.functions.decimals().call()

            balance = Decimal(raw) / Decimal(10 ** decimals)

            if balance == 0:
                continue

            price = get_token_price(token)

            value = balance * price

            results.append({
                "token": token,
                "balance": str(balance),
                "price": str(price),
                "value": str(value)
            })

        except:
            continue

    return results


async def get_portfolio(address: str, db: AsyncSession = Depends(get_db)):

    bnb_balance = get_bnb_balance(address)

    bnb_price = get_bnb_price()

    bnb_usd = bnb_balance * bnb_price

    tokens = await get_token_holdings(address, db)

    token_value = sum(Decimal(t["value"]) for t in tokens)

    total = token_value + bnb_usd

    return {
        "bnb_balance": str(bnb_balance),
        "bnb_price": str(bnb_price),
        "bnb_value_usd": str(bnb_usd),

        "token_value": str(token_value),

        "total_value": str(total),

        "tokens": tokens
    }

def calculate_portfolio(tokens, bnb_balance, bnb_price):

    total_cost = Decimal(0)
    total_value = Decimal(0)
    unrealized = Decimal(0)

    for t in tokens:

        balance = Decimal(t["balance"])
        price = Decimal(t["price"])
        avg_price = Decimal(t.get("avg_price", price))

        value = balance * price
        cost = balance * avg_price

        total_cost += cost
        total_value += value

        unrealized += calculate_unrealized(balance, avg_price, price)

    # BNB section
    bnb_value = bnb_balance * bnb_price
    bnb_cost = bnb_balance * bnb_price

    total_cost += bnb_cost
    total_value += bnb_value

    total_pnl = total_value - total_cost

    percent = Decimal(0)

    if total_cost > 0:
        percent = (total_pnl / total_cost) * 100

    return {
        "total_value": str(total_value),
        "total_cost": str(total_cost),
        "unrealized_pnl": str(unrealized),
        "total_pnl": clean_decimal(total_pnl),
        "pnl_percent": str(percent)
    }

async def save_portfolio_snapshot(db, agent_id, wallet, portfolio, pnl):

    snapshot = PortfolioSnapshot(
        id=str(uuid.uuid4()),
        agent_id=agent_id,
        wallet=wallet,

        bnb_balance=portfolio["bnb_balance"],
        bnb_value_usd = portfolio["bnb_value_usd"],
        token_value=portfolio["token_value"],
        total_value=portfolio["total_value"],

        realized_pnl=0,
        unrealized_pnl=pnl["unrealized_pnl"],
        total_pnl=pnl["total_pnl"],
        pnl_percent=pnl["pnl_percent"],

        created_at=datetime.utcnow()
    )

    db.add(snapshot)

    await db.commit()

    return snapshot

async def update_token_holdings(db, agent_id, wallet, tokens):

    for t in tokens:

        result = await db.execute(
            select(TokenHolding).where(
                TokenHolding.agent_id == agent_id,
                TokenHolding.token == t["token"]
            )
        )

        existing = result.scalar_one_or_none()

        if existing:

            existing.balance = t["balance"]
            existing.value = t["value"]

        else:

            holding = TokenHolding(
                id=str(uuid.uuid4()),
                agent_id=agent_id,
                wallet=wallet,
                token=t["token"],
                balance=t["balance"],
                avg_price=0,
                value=t["value"]
            )

            db.add(holding)

    await db.commit()