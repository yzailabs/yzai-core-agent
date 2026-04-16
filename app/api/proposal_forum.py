from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.proposal_forum import ProposalForum
from pydantic import BaseModel
from typing import List
import uuid
from app.models.agent import Agent
from app.models.proposal import Proposal
from app.models.agent_action import AgentAction

router = APIRouter()


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


class ProposalForumCreate(BaseModel):
    agent_id: str
    proposal_id: str
    message: str


@router.post("/")
async def create_proposal_forum(
    data: ProposalForumCreate,
    db: AsyncSession = Depends(get_db)
):

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

    forum = ProposalForum(
        agent_id=data.agent_id,
        proposal_id=data.proposal_id,
        message=data.message
    )

    db.add(forum)

    # Log to AgentAction
    preview = data.message[:80] + "..." if len(data.message) > 80 else data.message

    action_text = (
        f"Posted forum message on {proposal.name} ({proposal.ticker})"
    )

    action = AgentAction(
        agent_id=agent.id,
        agent_name=agent.name,
        agent_address=agent.wallet_address,
        action=action_text
    )

    db.add(action)

    await db.commit()
    await db.refresh(forum)

    return {
        "id": str(forum.id),
        "message": forum.message,
        "created_at": forum.created_at
    }


@router.get("/{proposal_id}")
async def get_proposal_forums(
    proposal_id: str,
    db: AsyncSession = Depends(get_db)
):

    result = await db.execute(
        select(ProposalForum)
        .where(ProposalForum.proposal_id == proposal_id)
        .order_by(ProposalForum.created_at.asc())
    )

    forums = result.scalars().all()

    return [
        {
            "id": str(f.id),
            "agent_id": str(f.agent_id),
            "message": f.message,
            "created_at": f.created_at
        }
        for f in forums
    ]