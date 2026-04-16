from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.vote import Vote
from app.models.proposal import Proposal
from pydantic import BaseModel
from typing import Optional
import uuid
from fastapi import Header
import os
from app.models.agent import Agent
from app.models.agent_action import AgentAction

INTERNAL_API_KEY = os.getenv("YZAI_INTERNAL_API_KEY")

router = APIRouter()

async def verify_internal_api_key(x_yzai_key: str = Header(None)):
    if not x_yzai_key or x_yzai_key != INTERNAL_API_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


class VoteCreate(BaseModel):
    agent_id: str
    proposal_id: str
    support: bool


# =========================
# POST /vote
# =========================
@router.post("/")
async def create_vote(
    data: VoteCreate,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_api_key)
):

    # Validate proposal exists
    result = await db.execute(
        select(Proposal).where(Proposal.id == data.proposal_id)
    )
    proposal = result.scalar_one_or_none()

    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")

    # Prevent double voting
    existing_vote = await db.execute(
        select(Vote).where(
            Vote.agent_id == data.agent_id,
            Vote.proposal_id == data.proposal_id
        )
    )

    if existing_vote.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Agent already voted on this proposal")

    # Validate agent exists
    agent_result = await db.execute(
        select(Agent).where(Agent.id == data.agent_id)
    )
    agent = agent_result.scalar_one_or_none()

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Create vote
    vote = Vote(
        agent_id=data.agent_id,
        proposal_id=data.proposal_id,
        support=data.support
    )

    db.add(vote)

    # Increment agent_votes if support == True
    if data.support:
        proposal.agent_votes += 1

    # 🔥 Log to AgentAction
    action_text = (
        f"Voted {'FOR' if data.support else 'AGAINST'} proposal "
        f"{proposal.name} ({proposal.ticker})"
    )

    action = AgentAction(
        agent_id=agent.id,
        agent_name=agent.name,
        agent_address=agent.wallet_address,
        action=action_text
    )

    db.add(action)

    await db.commit()
    await db.refresh(vote)

    return {
        "vote_id": str(vote.id),
        "agent_id": data.agent_id,
        "proposal_id": data.proposal_id,
        "support": data.support
    }


# =========================
# GET /vote
# =========================
@router.get("/")
async def get_votes(
    agent_id: Optional[str] = None,
    proposal_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):

    query = select(Vote)

    if agent_id:
        query = query.where(Vote.agent_id == agent_id)

    if proposal_id:
        query = query.where(Vote.proposal_id == proposal_id)

    result = await db.execute(query)
    votes = result.scalars().all()

    return [
        {
            "id": str(v.id),
            "agent_id": str(v.agent_id),
            "proposal_id": str(v.proposal_id),
            "support": v.support
        }
        for v in votes
    ]