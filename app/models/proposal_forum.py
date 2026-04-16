from sqlalchemy import Column, Text, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.db.base import Base
import uuid


class ProposalForum(Base):
    __tablename__ = "proposal_forums"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False)
    proposal_id = Column(UUID(as_uuid=True), ForeignKey("proposals.id"), nullable=False)

    message = Column(Text, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)