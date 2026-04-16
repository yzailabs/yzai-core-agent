from sqlalchemy import Column, String, Text, Float, JSON, Integer, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.db.base import Base
import uuid


class Proposal(Base):
    __tablename__ = "proposals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Basic Info
    name = Column(String, nullable=False)
    ticker = Column(String, nullable=False)
    logo = Column(String, nullable=True)
    description = Column(Text, nullable=False)
    raise_amount = Column(Float, nullable=False)
    meta = Column(String, nullable=True)

    # Tax Allocation (from fixed 3%)
    beneficiary_address = Column(String, nullable=True)
    buyback = Column(Float, nullable=False)
    burn = Column(Float, nullable=False)
    treasury = Column(Float, nullable=False)
    liquidity = Column(Float, nullable=False)

    # Social Links
    website = Column(String, nullable=True)
    telegram = Column(String, nullable=True)
    twitter = Column(String, nullable=True)
    discord = Column(String, nullable=True)
    github = Column(String, nullable=True)

    additional_links = Column(JSON, nullable=True)

    # Governance Status
    status = Column(String, default="pending")
    agent_votes = Column(Integer, default=0)
    owner = Column(String, nullable=False)

    # Timestamp
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)