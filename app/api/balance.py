from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.db.session import AsyncSessionLocal
from app.models.agent import Agent
from app.models.portfolio_snapshot import PortfolioSnapshot
from app.models.token_holding import TokenHolding
from app.models.trade_history import TradeHistory
from decimal import Decimal
from app.core.onchain import get_treasury_balances

from app.core.balance import (
    get_portfolio,
    calculate_portfolio,
    save_portfolio_snapshot,
    update_token_holdings
)

router = APIRouter()

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

@router.get("/portfolio/{agent_id}")
async def portfolio(agent_id: str, db: AsyncSession = Depends(get_db)):

    result = await db.execute(
        select(Agent).where(Agent.id == agent_id)
    )

    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    wallet = agent.wallet_address

    portfolio = await get_portfolio(wallet, db)

    bnb_value = Decimal(portfolio["bnb_value_usd"])
    bnb_balance = Decimal(portfolio["bnb_balance"])
    bnb_price = Decimal(portfolio["bnb_price"])

    pnl = calculate_portfolio(
        portfolio["tokens"],
        bnb_balance,
        bnb_price
    )

    await update_token_holdings(
        db,
        agent_id,
        wallet,
        portfolio["tokens"]
    )

    await save_portfolio_snapshot(
        db,
        agent_id,
        wallet,
        portfolio,
        pnl
    )

    return {
        "agent_id": agent_id,
        "wallet_address": wallet,
        **portfolio,
        **pnl
    }

@router.get("/holdings/{agent_id}")
async def get_holdings(agent_id: str, db: AsyncSession = Depends(get_db)):

    result = await db.execute(
        select(TokenHolding).where(
            TokenHolding.agent_id == agent_id
        )
    )

    rows = result.scalars().all()

    holdings = []

    for h in rows:

        holdings.append({
            "token": h.token,
            "balance": float(h.balance),
            "avg_price": float(h.avg_price),
            "value": float(h.value)
        })

    return {
        "agent_id": agent_id,
        "total": len(holdings),
        "holdings": holdings
    }

@router.get("/trades/{agent_id}")
async def get_trades(agent_id: str, db: AsyncSession = Depends(get_db)):

    result = await db.execute(
        select(TradeHistory)
        .where(TradeHistory.agent_id == agent_id)
        .order_by(TradeHistory.created_at.desc())
    )

    rows = result.scalars().all()

    trades = []

    for t in rows:

        trades.append({
            "token": t.token,
            "type": t.trade_type,
            "amount_token": float(t.amount_token) if t.amount_token else 0,
            "amount_bnb": float(t.amount_bnb) if t.amount_bnb else 0,
            "price": float(t.price) if t.price else 0,
            "tx_hash": t.tx_hash,
            "time": t.created_at
        })

    return {
        "agent_id": agent_id,
        "total": len(trades),
        "trades": trades
    }

@router.get("/treasury")
async def treasury_balance():

    data = get_treasury_balances()

    return data