import random
import string
import os

from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db.session import AsyncSessionLocal
from app.models.referral import ReferralCode, ReferralParticipant

INTERNAL_API_KEY = os.getenv("YZAI_INTERNAL_API_KEY")

router = APIRouter()


async def verify_internal_api_key(x_yzai_key: str = Header(None)):
    if not x_yzai_key or x_yzai_key != INTERNAL_API_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


def generate_referral_code():
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=8))


# -------------------------------------------------
# GENERATE REFERRAL CODE
# -------------------------------------------------

@router.post("/generate")
async def generate_referral(
    admin_x_account: str,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_api_key)
):

    while True:
        code = generate_referral_code()

        result = await db.execute(
            select(ReferralCode).where(ReferralCode.code == code)
        )

        exists = result.scalar_one_or_none()

        if not exists:
            break

    referral = ReferralCode(
        code=code,
        owner_x_account=admin_x_account.lower()
    )

    db.add(referral)
    await db.commit()
    await db.refresh(referral)

    return {
        "referral_link": f"https://www.yzailabs.com/?referral={code}",
        "code": code,
        "owner": admin_x_account
    }


# -------------------------------------------------
# CHECK REFERRAL
# -------------------------------------------------

@router.post("/check/{code}")
async def check_referral(
    code: str,
    db: AsyncSession = Depends(get_db)
):

    result = await db.execute(
        select(ReferralCode).where(ReferralCode.code == code)
    )

    referral = result.scalar_one_or_none()

    if not referral:
        return {
            "valid": False
        }

    return {
        "valid": True,
        "owner_x_account": referral.owner_x_account
    }


# -------------------------------------------------
# REGISTER AGENT FROM REFERRAL
# -------------------------------------------------

@router.put("/agent")
async def register_referral_agent(
    referral_code: str,
    user_x_account: str,
    agent_id: str,
    agent_wallet_address: str,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_api_key)
):

    # check referral code
    result = await db.execute(
        select(ReferralCode).where(ReferralCode.code == referral_code)
    )

    referral = result.scalar_one_or_none()

    if not referral:
        raise HTTPException(
            status_code=404,
            detail="Referral code not found"
        )

    # prevent duplicate agent
    existing = await db.execute(
        select(ReferralParticipant).where(
            ReferralParticipant.agent_id == agent_id
        )
    )

    exists = existing.scalar_one_or_none()

    if exists:
        return {
            "status": "already_registered",
            "agent_id": agent_id
        }

    participant = ReferralParticipant(
        referral_code=referral_code,
        user_x_account=user_x_account.lower(),
        agent_id=agent_id,
        agent_wallet_address=agent_wallet_address
    )

    db.add(participant)

    await db.commit()
    await db.refresh(participant)

    return {
        "status": "registered",
        "referral_code": referral_code,
        "agent_id": agent_id
    }


# -------------------------------------------------
# MARK AGENT JOINED RAISING
# -------------------------------------------------

@router.put("/joined")
async def mark_joined_raising(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_api_key)
):

    result = await db.execute(
        select(ReferralParticipant).where(
            ReferralParticipant.agent_id == agent_id
        )
    )

    participant = result.scalar_one_or_none()

    if not participant:
        raise HTTPException(
            status_code=404,
            detail="Agent not found in referral system"
        )

    participant.joined_raising = True

    await db.commit()
    await db.refresh(participant)

    return {
        "status": "joined_raising",
        "agent_id": agent_id
    }


# -------------------------------------------------
# GET REFERRAL STATS FOR USER
# -------------------------------------------------

@router.get("/stats/{x_username}")
async def get_referral_stats(
    x_username: str,
    db: AsyncSession = Depends(get_db)
):

    username = x_username.lower()

    # find referral code owned by user
    result = await db.execute(
        select(ReferralCode).where(
            ReferralCode.owner_x_account == username
        )
    )

    referral = result.scalar_one_or_none()

    if not referral:
        return {
            "found": False
        }

    code = referral.code

    # get all participants
    participants_result = await db.execute(
        select(ReferralParticipant).where(
            ReferralParticipant.referral_code == code
        )
    )

    participants = participants_result.scalars().all()

    total = len(participants)

    joined = sum(1 for p in participants if p.joined_raising)

    pending = total - joined

    agents = []

    for p in participants:
        agents.append({
            "agent_id": p.agent_id,
            "user_x_account": p.user_x_account,
            "agent_wallet_address": p.agent_wallet_address,
            "joined_raising": p.joined_raising,
            "created_at": p.created_at
        })

    return {
        "found": True,
        "referral_code": code,
        "total_invited": total,
        "joined_raising": joined,
        "pending": pending,
        "agents": agents
    }