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
import smtplib
from email.mime.text import MIMEText
import requests
import resend

INTERNAL_API_KEY = os.getenv("YZAI_INTERNAL_API_KEY")
YZAI_EMAIL = os.getenv("YZAI_EMAIL")
YZAI_EMAIL_PASSWORD = os.getenv("YZAI_EMAIL_PASSWORD")
RESEND_API_KEY = os.getenv('RESEND_API_KEY')
resend.api_key = os.getenv("RESEND_API_KEY")

def send_email_code(to_email: str, code: str):

    params = {
        "from": "YZai <noreply@yzailabs.com>",
        "to": [to_email],
        "subject": "Your YZai Verification Code",
        "html": f"""
            <div style="font-family: Arial; padding: 20px;">
                <h2>YZai Verification Code</h2>
                <p>Your verification code is:</p>
                <h1 style="letter-spacing: 4px;">{code}</h1>
                <p>This code will expire in 5 minutes.</p>
            </div>
        """
    }

    resend.Emails.send(params)

async def verify_internal_api_key(x_yzai_key: str = Header(None)):
    if not x_yzai_key or x_yzai_key != INTERNAL_API_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")

router = APIRouter()

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

class VerifyCodeRequest(BaseModel):
    email: str
    code: str

class SendCodeRequest(BaseModel):
    email: str

@router.post("/send-code")
async def send_code(data: SendCodeRequest, db: AsyncSession = Depends(get_db)):

    code = str(secrets.randbelow(999999)).zfill(6)
    email = data.email.lower()

    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()

    if not user:
        user = User(email=data.email, email_code=code)
        db.add(user)
    else:
        user.email_code = code

    await db.commit()

    # TODO: send email here
    print(f"[DEBUG] code for {data.email}: {code}")
    send_email_code(email, code)

    return {"message": "Verification code sent"}

@router.post("/verify-code")
async def verify_code(data: VerifyCodeRequest, db: AsyncSession = Depends(get_db)):

    email = data.email.lower()

    result = await db.execute(
        select(User).where(User.email == email)
    )
    user = result.scalar_one_or_none()

    if not user or user.email_code != data.code:
        raise HTTPException(status_code=400, detail="Invalid code")

    user.email_verified = True
    user.email_code = None

    await db.commit()

    token = create_access_token({"sub": str(user.id)})

    return {
        "access_token": token,
        "token_type": "bearer",
        "is_new_user": user.wallet_address is None,
        "wallet_address": user.wallet_address,
        "x_username": user.x_username
    }

class CompleteProfileRequest(BaseModel):
    email: str
    wallet_address: str
    x_username: str

@router.post("/complete-profile")
async def complete_profile(
    data: CompleteProfileRequest,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_api_key)
):
    email = data.email.lower()
    wallet = data.wallet_address.lower()
    x_username = data.x_username.lower()

    result = await db.execute(
        select(User).where(User.email == email)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.wallet_address = wallet
    user.x_username = x_username

    try:
        await db.commit()
        await db.refresh(user)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=400,
            detail="Wallet or X already used"
        )

    return {
        "message": "Profile completed",
        "email": user.email,
        "wallet_address": user.wallet_address,
        "x_username": user.x_username
    }