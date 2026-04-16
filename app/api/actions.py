from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
from typing import Optional

from app.db.session import AsyncSessionLocal
from app.models.agent import Agent
from app.models.agent_action import AgentAction
from pydantic import BaseModel
import os
from fastapi import Header
from typing import Optional, List

INTERNAL_API_KEY = os.getenv("YZAI_INTERNAL_API_KEY")

router = APIRouter()

async def verify_internal_api_key(x_yzai_key: str = Header(None)):
    if not x_yzai_key or x_yzai_key != INTERNAL_API_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")
    
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

class ActionCreate(BaseModel):
    agent_id: str
    action: str

class TransferActionCreate(BaseModel):
    agent_id: str
    to_address: str
    amount_bnb: float
    tx_hash: Optional[str] = None
    message: Optional[str] = None

@router.post("/")
async def create_action(
    data: ActionCreate,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_api_key)
):

    result = await db.execute(
        select(Agent).where(Agent.id == data.agent_id)
    )
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    action = AgentAction(
        agent_id=agent.id,
        agent_name=agent.name,
        agent_address=agent.wallet_address,
        action=data.action
    )

    db.add(action)
    await db.commit()

    return {"status": "logged"}

@router.post("/transfer")
async def create_transfer_action(
    data: TransferActionCreate,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_api_key)
):

    result = await db.execute(
        select(Agent).where(Agent.id == data.agent_id)
    )
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Base message
    action_message = f"Transferred {data.amount_bnb} BNB to {data.to_address}"

    if data.message:
        action_message += f" | {data.message}"

    if data.tx_hash:
        action_message += f" | TX: {data.tx_hash}"

    action = AgentAction(
        agent_id=agent.id,
        agent_name=agent.name,
        agent_address=agent.wallet_address,
        action=action_message
    )

    db.add(action)
    await db.commit()

    return {"status": "transfer logged"}

@router.get("/")
async def get_actions(
    agent_id: Optional[str] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):

    query = select(AgentAction).order_by(
        AgentAction.created_at.desc()
    ).limit(limit)

    if agent_id:
        query = query.where(AgentAction.agent_id == agent_id)

    result = await db.execute(query)
    actions = result.scalars().all()

    return [
        {
            "id": str(a.id),
            "agent_id": str(a.agent_id),
            "agent_name": a.agent_name,
            "agent_address": a.agent_address,
            "action": a.action,
            "created_at": a.created_at
        }
        for a in actions
    ]