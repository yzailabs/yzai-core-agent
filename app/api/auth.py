from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.core.security import create_access_token
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
import secrets
from eth_account.messages import encode_defunct
from eth_account import Account
from typing import Optional
import os
from fastapi import Header
from jose import jwt, JWTError
from app.core.config import JWT_SECRET, JWT_ALGORITHM

INTERNAL_API_KEY = os.getenv("YZAI_INTERNAL_API_KEY")

async def verify_internal_api_key(x_yzai_key: str = Header(None)):
    if not x_yzai_key or x_yzai_key != INTERNAL_API_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")

router = APIRouter()

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

async def get_current_user(
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    token = authorization.split(" ")[1]

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id: str = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user

class SignupRequest(BaseModel):
    wallet_address: str
    x_username: Optional[str] = None

class UpdateUserWalletRequest(BaseModel):
    x_username: str
    wallet_address: str

@router.post("/signup")
async def signup(data: SignupRequest, db: AsyncSession = Depends(get_db)):
    user = User(
        wallet_address=data.wallet_address,
        x_username=data.x_username
    )

    db.add(user)

    try:
        await db.commit()
        await db.refresh(user)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=400,
            detail="Wallet address or X username already registered"
        )

    return {
        "message": "User created successfully",
        "user_id": str(user.id),
        "wallet_address": user.wallet_address,
        "x_username": user.x_username
    }


@router.post("/login")
async def login(wallet_address: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User).where(User.wallet_address == wallet_address)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    token = create_access_token({"sub": str(user.id)})

    return {
        "access_token": token,
        "token_type": "bearer"
    }

@router.get("/nonce")
async def get_nonce(wallet_address: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User).where(User.wallet_address == wallet_address)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    nonce = secrets.token_hex(16)
    user.nonce = nonce
    await db.commit()

    return {
        "wallet_address": wallet_address,
        "nonce": nonce
    }

from pydantic import BaseModel

class VerifyRequest(BaseModel):
    wallet_address: str
    signature: str


@router.post("/verify")
async def verify_signature(data: VerifyRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User).where(User.wallet_address == data.wallet_address)
    )
    user = result.scalar_one_or_none()

    if not user or not user.nonce:
        raise HTTPException(status_code=400, detail="Invalid request")

    message = f"Sign this message to authenticate:\nNonce: {user.nonce}"
    encoded_message = encode_defunct(text=message)

    try:
        recovered_address = Account.recover_message(
            encoded_message,
            signature=data.signature
        )
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid signature")

    if recovered_address.lower() != user.wallet_address.lower():
        raise HTTPException(status_code=401, detail="Signature mismatch")

    # Reset nonce (prevent replay attack)
    user.nonce = None
    await db.commit()

    token = create_access_token({"sub": str(user.id)})

    return {
        "access_token": token,
        "token_type": "bearer"
    }

@router.get("/user-by-wallet")
async def get_user_by_wallet(
    wallet_address: str,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_api_key)
):
    result = await db.execute(
        select(User).where(User.wallet_address == wallet_address)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "user_id": str(user.id),
        "wallet_address": user.wallet_address,
        "x_username": user.x_username
    }

@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    return {
        "user_id": str(current_user.id),
        "wallet_address": current_user.wallet_address,
        "x_username": current_user.x_username
    }

@router.get("/user-by-x")
async def get_user_by_x(
    x_username: str,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_api_key)
):
    result = await db.execute(
        select(User).where(User.x_username == x_username)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "user_id": str(user.id),
        "wallet_address": user.wallet_address,
        "x_username": user.x_username
    }

@router.put("/user-by-x")
async def update_user_wallet_by_x(
    data: UpdateUserWalletRequest,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_api_key)
):
    result = await db.execute(
        select(User).where(User.x_username == data.x_username)
    )

    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.wallet_address = data.wallet_address

    try:
        await db.commit()
        await db.refresh(user)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=400,
            detail="Wallet address already used"
        )

    return {
        "message": "Wallet address updated",
        "user_id": str(user.id),
        "wallet_address": user.wallet_address,
        "x_username": user.x_username
    }