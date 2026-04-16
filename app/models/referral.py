from sqlalchemy import Column, String, DateTime, Boolean
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base
import uuid
from datetime import datetime

class ReferralCode(Base):
    __tablename__ = "referral_codes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String, unique=True, index=True)
    owner_x_account = Column(String, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class ReferralParticipant(Base):
    __tablename__ = "referral_participants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    referral_code = Column(String, index=True)
    user_x_account = Column(String, index=True)

    agent_id = Column(String, index=True)
    agent_wallet_address = Column(String)

    joined_raising = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)