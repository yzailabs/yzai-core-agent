from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.db.session import AsyncSessionLocal

from app.models.agent import Agent
from app.models.portfolio_snapshot import PortfolioSnapshot

router = APIRouter()


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


@router.get("/leaderboard")
async def leaderboard(limit: int = 50, db: AsyncSession = Depends(get_db)):

    latest_snapshot = (
        select(
            PortfolioSnapshot.agent_id,
            func.max(PortfolioSnapshot.created_at).label("latest")
        )
        .group_by(PortfolioSnapshot.agent_id)
        .subquery()
    )

    result = await db.execute(
        select(
            Agent.id,
            Agent.name,
            Agent.wallet_address,
            PortfolioSnapshot.total_value,
            PortfolioSnapshot.total_pnl,
            PortfolioSnapshot.realized_pnl,
            PortfolioSnapshot.unrealized_pnl,
            PortfolioSnapshot.pnl_percent
        )
        .join(
            latest_snapshot,
            latest_snapshot.c.agent_id == Agent.id
        )
        .join(
            PortfolioSnapshot,
            (PortfolioSnapshot.agent_id == latest_snapshot.c.agent_id) &
            (PortfolioSnapshot.created_at == latest_snapshot.c.latest)
        )
        .order_by(PortfolioSnapshot.total_value.desc())
        .limit(limit)
    )

    rows = result.all()

    leaderboard = []

    rank = 1

    for r in rows:

        leaderboard.append({
            "rank": rank,
            "agent_id": r.id,
            "name": r.name,
            "wallet_address": r.wallet_address,

            "portfolio_value": float(r.total_value),
            "total_pnl": float(r.total_pnl),
            "realized": float(r.realized_pnl),
            "unrealized": float(r.unrealized_pnl),
            "pnl_percent": float(r.pnl_percent)
        })

        rank += 1

    return leaderboard