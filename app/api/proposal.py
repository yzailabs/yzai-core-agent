from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, desc, asc
from app.db.session import AsyncSessionLocal
from app.models.proposal import Proposal
from pydantic import BaseModel
from typing import Optional, List
import os
from fastapi import Header
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


# ---------------------------
# Schema
# ---------------------------

class ProposalCreate(BaseModel):
    name: str
    ticker: str
    logo: Optional[str] = None
    description: str
    raise_amount: float
    meta: Optional[str] = None

    beneficiary_address: Optional[str] = None
    buyback: float
    burn: float
    treasury: float
    liquidity: float

    website: Optional[str] = None
    telegram: Optional[str] = None
    twitter: Optional[str] = None
    discord: Optional[str] = None
    github: Optional[str] = None

    additional_links: Optional[List[dict]] = None

    owner: str

# ---------------------------
# Update Schema
# ---------------------------

class ProposalUpdate(BaseModel):
    name: Optional[str] = None
    ticker: Optional[str] = None
    logo: Optional[str] = None
    description: Optional[str] = None
    raise_amount: Optional[float] = None
    meta: Optional[str] = None

    beneficiary_address: Optional[str] = None
    buyback: Optional[float] = None
    burn: Optional[float] = None
    treasury: Optional[float] = None
    liquidity: Optional[float] = None

    website: Optional[str] = None
    telegram: Optional[str] = None
    twitter: Optional[str] = None
    discord: Optional[str] = None
    github: Optional[str] = None

    additional_links: Optional[List[dict]] = None
    status: Optional[str] = None

# ---------------------------
# Create Proposal
# ---------------------------

@router.post("/create")
async def create_proposal(
    data: ProposalCreate,
    _: None = Depends(verify_internal_api_key),
    db: AsyncSession = Depends(get_db)
):

    # validate allocation = 100%
    total = data.buyback + data.burn + data.treasury + data.liquidity
    if total != 100:
        raise HTTPException(status_code=400, detail="Allocation must equal 100%")

    # Validate Agent (owner)
    agent_result = await db.execute(
        select(Agent).where(Agent.id == data.owner)
    )
    agent = agent_result.scalar_one_or_none()

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    proposal = Proposal(**data.dict())

    db.add(proposal)
    await db.commit()
    await db.refresh(proposal)

    # Log Action
    action_text = (
        f"Created proposal {proposal.name} ({proposal.ticker})"
    )

    action = AgentAction(
        agent_id=agent.id,
        agent_name=agent.name,
        agent_address=agent.wallet_address,
        action=action_text
    )

    db.add(action)
    await db.commit()

    return {
        "id": str(proposal.id),
        "name": proposal.name,
        "owner": proposal.owner,
        "status": proposal.status
    }


# ---------------------------
# Get All + Filter
# ---------------------------

@router.get("/")
async def get_proposals(
    name: Optional[str] = None,
    ticker: Optional[str] = None,
    sort_by: Optional[str] = Query(None, description="votes or created_at"),
    order: Optional[str] = Query("desc", description="asc or desc"),
    db: AsyncSession = Depends(get_db)
):

    query = select(Proposal)

    # Filter by name/ticker
    if name:
        query = query.where(Proposal.name.ilike(f"%{name}%"))

    if ticker:
        query = query.where(Proposal.ticker.ilike(f"%{ticker}%"))

    # Sorting
    if sort_by == "votes":
        if order == "asc":
            query = query.order_by(asc(Proposal.agent_votes))
        else:
            query = query.order_by(desc(Proposal.agent_votes))

    elif sort_by == "created_at":
        if order == "asc":
            query = query.order_by(asc(Proposal.created_at))
        else:
            query = query.order_by(desc(Proposal.created_at))

    result = await db.execute(query)
    proposals = result.scalars().all()

    return proposals

# ---------------------------
# Update Proposal
# ---------------------------

@router.put("/{proposal_id}")
async def update_proposal(
    proposal_id: str,
    data: ProposalUpdate,
    _: None = Depends(verify_internal_api_key),
    db: AsyncSession = Depends(get_db)
):

    result = await db.execute(
        select(Proposal).where(Proposal.id == proposal_id)
    )
    proposal = result.scalar_one_or_none()

    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")

    update_data = data.dict(exclude_unset=True)

    # Validate allocation if updated
    if any(k in update_data for k in ["buyback", "burn", "treasury", "liquidity"]):
        buyback = update_data.get("buyback", proposal.buyback)
        burn = update_data.get("burn", proposal.burn)
        treasury = update_data.get("treasury", proposal.treasury)
        liquidity = update_data.get("liquidity", proposal.liquidity)

        total = buyback + burn + treasury + liquidity

        if total != 100:
            raise HTTPException(status_code=400, detail="Allocation must equal 100%")

    # Apply updates
    for key, value in update_data.items():
        setattr(proposal, key, value)

    await db.commit()
    await db.refresh(proposal)

    return {
        "id": str(proposal.id),
        "name": proposal.name,
        "status": proposal.status,
        "updated": True
    }