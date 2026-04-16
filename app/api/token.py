from app.core.onchain import get_token_v5, get_tokens_batch, transfer_bnb, swap_exact_input,swap_bnb_to_token, swap_token_to_bnb
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime
from typing import Optional
import uuid
from app.db.session import AsyncSessionLocal
from app.models.agent import Agent
from app.models.agent_action import AgentAction
from pydantic import BaseModel
import os
from fastapi import Header
from typing import Optional, List
from app.core.wallet_crypto import decrypt_private_key
from app.models.proposal import Proposal
from app.models.presale import Presale
from enum import Enum
from app.models.trade_history import TradeHistory
from decimal import Decimal

INTERNAL_API_KEY = os.getenv("YZAI_INTERNAL_API_KEY")

async def verify_internal_api_key(x_yzai_key: str = Header(None)):
    if not x_yzai_key or x_yzai_key != INTERNAL_API_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")
    
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

router = APIRouter()

class TradeType(str, Enum):
    BUY = "BUY"
    SELL = "SELL"

class PresaleBuyRequest(BaseModel):
    agent_id: str
    sale_proxy_contract: str
    amount_bnb: float

class BondingTradeRequest(BaseModel):
    agent_id: str
    token: str
    type: TradeType
    input_amount: int
    min_output_amount: int = 0

class DexTradeRequest(BaseModel):
    agent_id: str
    token: str
    amount: float
    min_output_amount: int = 0

@router.get("/")
async def get_token(token: str):

    data = get_token_v5(token)

    return data

@router.get("/list")
async def get_tokens(db: AsyncSession = Depends(get_db)):

    tokens = await get_tokens_batch(db)

    return {
        "total": len(tokens),
        "tokens": tokens
    }

@router.post("/presale/buy")
async def buy_presale(
    data: PresaleBuyRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_internal_api_key)
):

    result = await db.execute(
        select(Agent).where(Agent.id == data.agent_id)
    )

    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Validate presale exists
    resultPresale = await db.execute(
        select(Presale).where(
            func.lower(Presale.sale_proxy_contract) == data.sale_proxy_contract.lower()
        )
    )
    presale = resultPresale.scalar_one_or_none()

    if not presale:
        raise HTTPException(status_code=404, detail="Presale not found")

    # Validate proposal exists
    resultProposal = await db.execute(
        select(Proposal).where(Proposal.id == presale.proposal_id)
    )
    proposal = resultProposal.scalar_one_or_none()
    
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")

    try:

        agent_pk = decrypt_private_key(agent.private_key_encrypted)

        tx_hash = transfer_bnb(
            agent_pk,
            data.sale_proxy_contract,
            data.amount_bnb
        )

        trade = TradeHistory(
            id=str(uuid.uuid4()),
            agent_id=str(agent.id),
            wallet=agent.wallet_address,
            token=presale.token_address,
            trade_type="BUY Raising",
            amount_token=0,  
            amount_bnb=Decimal(str(data.amount_bnb)),
            price=0,  
            tx_hash=tx_hash
        )

        db.add(trade)

        action = AgentAction(
            agent_id=agent.id,
            agent_name=agent.name,
            agent_address=agent.wallet_address,
            action=f"Buy {proposal.ticker} Raising for {data.amount_bnb} BNB"
        )

        db.add(action)
        await db.commit()

        return {
            "status": "success",
            "agent": agent.id,
            "sale_proxy": data.sale_proxy_contract,
            "amount_bnb": data.amount_bnb,
            "tx_hash": tx_hash
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

@router.post("/bonding/trade")
async def bonding_trade(
    data: BondingTradeRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_internal_api_key)
):

    result = await db.execute(
        select(Agent).where(Agent.id == data.agent_id)
    )

    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    try:

        agent_pk = decrypt_private_key(agent.private_key_encrypted)

        tx_hash = swap_exact_input(
            agent_pk,
            data.token,
            data.type,
            data.input_amount,
            data.min_output_amount
        )

        action = AgentAction(
            agent_id=agent.id,
            agent_name=agent.name,
            agent_address=agent.wallet_address,
            action=f"{data.type} {data.token}"
        )

        db.add(action)
        await db.commit()

        return {
            "status": "success",
            "agent": agent.id,
            "type": data.type,
            "token": data.token,
            "tx_hash": tx_hash
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
    
@router.post("/dex/buy")
async def dex_buy(
    data: DexTradeRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_internal_api_key)
):

    result = await db.execute(
        select(Agent).where(Agent.id == data.agent_id)
    )

    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    try:

        agent_pk = decrypt_private_key(agent.private_key_encrypted)

        tx_hash = swap_bnb_to_token(
            agent_pk,
            data.token,
            data.amount,
            data.min_output_amount
        )

        price = data.amount

        trade = TradeHistory(
            id=str(uuid.uuid4()),
            agent_id=str(agent.id),
            wallet=agent.wallet_address,
            token=data.token,
            trade_type="BUY",
            amount_token=0,
            amount_bnb=data.amount,
            price=0,
            tx_hash=tx_hash
        )

        db.add(trade)

        action = AgentAction(
            agent_id=agent.id,
            agent_name=agent.name,
            agent_address=agent.wallet_address,
            action=f"BUY {data.token} for {data.amount} BNB"
        )

        db.add(action)
        await db.commit()

        return {
            "status": "success",
            "agent": agent.id,
            "token": data.token,
            "amount_bnb": data.amount,
            "tx_hash": tx_hash
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

@router.post("/dex/sell")
async def dex_sell(
    data: DexTradeRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_internal_api_key)
):

    result = await db.execute(
        select(Agent).where(Agent.id == data.agent_id)
    )

    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    try:

        agent_pk = decrypt_private_key(agent.private_key_encrypted)

        tx_hash = swap_token_to_bnb(
            agent_pk,
            data.token,
            int(data.amount),
            data.min_output_amount
        )

        trade = TradeHistory(
            id=str(uuid.uuid4()),
            agent_id=str(agent.id),
            wallet=agent.wallet_address,
            token=data.token,
            trade_type="SELL",
            amount_token=data.amount,
            amount_bnb=0,
            price=0,
            tx_hash=tx_hash
        )

        db.add(trade)

        action = AgentAction(
            agent_id=agent.id,
            agent_name=agent.name,
            agent_address=agent.wallet_address,
            action=f"SELL {data.token} for {data.amount}"
        )

        db.add(action)
        await db.commit()

        return {
            "status": "success",
            "agent": agent.id,
            "token": data.token,
            "amount_token": data.amount,
            "tx_hash": tx_hash
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))