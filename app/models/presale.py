from sqlalchemy import Column, DateTime, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.db.base import Base
import uuid


class Presale(Base):
    __tablename__ = "presales"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Time
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=False)

    # Limits
    min_buy_bnb = Column(Float, nullable=False)
    max_buy_bnb = Column(Float, nullable=False)

    # Onchain Data
    token_address = Column(String, nullable=True)
    sale_proxy_contract = Column(String, nullable=True)

    # Relation
    proposal_id = Column(UUID(as_uuid=True), ForeignKey("proposals.id"), nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)