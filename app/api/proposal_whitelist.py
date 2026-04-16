from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.proposal_whitelist import ProposalWhitelist
from pydantic import BaseModel
from typing import Optional
import uuid
from app.models.agent import Agent
from app.models.proposal import Proposal
from app.models.agent_action import AgentAction

router = APIRouter()

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


class ProposalWhitelistCreate(BaseModel):
    agent_id: str
    agent_wallet: str
    proposal_id: str
    support: bool

@router.post("/")
async def create_whitelist(
    data: ProposalWhitelistCreate,
    db: AsyncSession = Depends(get_db)
):

    # prevent duplicate
    result = await db.execute(
        select(ProposalWhitelist).where(
            ProposalWhitelist.agent_id == data.agent_id,
            ProposalWhitelist.proposal_id == data.proposal_id
        )
    )

    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(status_code=400, detail="Whitelist already exists")

    # Validate agent
    agent_result = await db.execute(
        select(Agent).where(Agent.id == data.agent_id)
    )
    agent = agent_result.scalar_one_or_none()

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Validate proposal
    proposal_result = await db.execute(
        select(Proposal).where(Proposal.id == data.proposal_id)
    )
    proposal = proposal_result.scalar_one_or_none()

    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")

    whitelist = ProposalWhitelist(
        agent_id=data.agent_id,
        proposal_id=data.proposal_id,
        support=data.support,
        agent_wallet=data.agent_wallet
    )

    db.add(whitelist)

    # Log to AgentAction
    action_text = (
        f"{'Supported' if data.support else 'Opposed'} whitelist for "
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
    await db.refresh(whitelist)

    return {
        "id": str(whitelist.id),
        "agent_id": data.agent_id,
        "agent_wallet": data.agent_wallet,
        "proposal_id": data.proposal_id,
        "support": data.support
    }

@router.get("/")
async def get_whitelists(
    agent_id: Optional[str] = None,
    proposal_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):

    query = select(ProposalWhitelist)

    if agent_id:
        query = query.where(ProposalWhitelist.agent_id == agent_id)

    if proposal_id:
        query = query.where(ProposalWhitelist.proposal_id == proposal_id)

    result = await db.execute(query)
    whitelists = result.scalars().all()

    return [
        {
            "id": str(w.id),
            "agent_id": str(w.agent_id),
            "agent_wallet": str(w.agent_wallet),
            "proposal_id": str(w.proposal_id),
            "support": w.support
        }
        for w in whitelists
    ]