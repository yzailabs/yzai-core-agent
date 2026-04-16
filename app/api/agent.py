from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import AsyncSessionLocal
from app.models.agent import Agent
from eth_account import Account
from app.core.wallet_crypto import encrypt_private_key
from sqlalchemy import select
from fastapi import HTTPException
from typing import Optional
from sqlalchemy import asc, desc
from pydantic import BaseModel
import re
import httpx
import os
from fastapi import Header

INTERNAL_API_KEY = os.getenv("YZAI_INTERNAL_API_KEY")
X_API_KEY = os.getenv("X_API_KEY")

router = APIRouter()

async def verify_internal_api_key(x_yzai_key: str = Header(None)):
    if not x_yzai_key or x_yzai_key != INTERNAL_API_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")

VERIFY_TEXT = "I verifying my venture capital agent on @yzailabs_bsc"

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

class ClaimRequest(BaseModel):
    agent_id: str
    post_url: str

@router.post("/create")
async def create_agent(
    name: str,
    avatar: str,
    trading_style: str,
    owner_id: str,
    owner_x_account: str,
    db: AsyncSession = Depends(get_db)
):

    # Check X account uniqueness
    result = await db.execute(
        select(Agent).where(Agent.owner_x_account == owner_x_account)
    )
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(status_code=400, detail="This X account already has an agent")

    account = Account.create()
    private_key = account.key.hex()
    wallet_address = account.address

    encrypted_key = encrypt_private_key(private_key)

    agent = Agent(
        name=name,
        avatar=avatar,
        trading_style=trading_style,
        wallet_address=wallet_address,
        private_key_encrypted=encrypted_key,
        owner_id=owner_id,
        owner_x_account=owner_x_account
    )

    db.add(agent)
    await db.commit()
    await db.refresh(agent)

    return {
        "agent_id": str(agent.id),
        "wallet_address": agent.wallet_address,
        "trading_style": agent.trading_style
    }

@router.get("/")
async def get_agents(
    name: Optional[str] = None,
    trading_style: Optional[str] = None,
    owner_x_account: Optional[str] = None,
    sort_by: Optional[str] = None,
    order: Optional[str] = "desc",
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_api_key)
):
    query = select(Agent)

    if name:
        query = query.where(Agent.name.ilike(f"%{name}%"))

    if trading_style:
        query = query.where(Agent.trading_style == trading_style)

    if owner_x_account:
        query = query.where(Agent.owner_x_account == owner_x_account)

    if sort_by == "created_at":
        if order == "asc":
            query = query.order_by(asc(Agent.created_at))
        else:
            query = query.order_by(desc(Agent.created_at))

    result = await db.execute(query)
    agents = result.scalars().all()

    # SAFE RESPONSE (no private key exposed)
    return [
        {
            "agent_id": a.id,
            "name": a.name,
            "avatar": a.avatar,
            "trading_style": a.trading_style,
            "wallet_address": a.wallet_address,
            "claim": a.claim,
            "owner": a.owner_x_account
        }
        for a in agents
    ]

@router.post("/claim")
async def claim_agent(
    data: ClaimRequest,
    db: AsyncSession = Depends(get_db)
):

    # Extract tweet ID
    match = re.search(r"status/(\d+)", data.post_url)
    if not match:
        raise HTTPException(status_code=400, detail="Invalid X post URL")

    tweet_id = match.group(1)

    # Find agent
    result = await db.execute(
        select(Agent).where(Agent.id == data.agent_id)
    )
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    ownerX = agent.owner_x_account

    # Call Twitter API
    url = f"https://api.twitterapi.io/twitter/tweets?tweet_ids={tweet_id}"

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            url,
            headers={
                "X-API-Key": X_API_KEY
            }
        )

    if resp.status_code != 200:
        raise HTTPException(status_code=400, detail="Twitter API error")

    data_json = resp.json()

    tweets = data_json.get("tweets", [])

    if not tweets:
        raise HTTPException(status_code=400, detail="Tweet not found")

    tweet = tweets[0]

    tweet_text = tweet.get("text", "").strip()
    tweet_author = tweet.get("author", {}).get("userName", "").lower()

    # Validate verification text
    if VERIFY_TEXT.lower() not in tweet_text.lower():
        raise HTTPException(
            status_code=400,
            detail="Verification text not found in tweet"
        )

    # Validate owner
    # if tweet_author != ownerX.lower():
    #     raise HTTPException(
    #         status_code=400,
    #         detail="Tweet author does not match agent owner"
    #     )

    # Claim success
    agent.claim = True
    await db.commit()

    return {
        "status": "success",
        "agent_id": str(agent.id),
        "owner": ownerX,
        "tweet_id": tweet_id
    }