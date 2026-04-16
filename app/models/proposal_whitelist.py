from sqlalchemy import Column, Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base
import uuid


class ProposalWhitelist(Base):
    __tablename__ = "proposal_whitelists"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False)
    agent_wallet = Column(String, nullable=True)
    proposal_id = Column(UUID(as_uuid=True), ForeignKey("proposals.id"), nullable=False)

    support = Column(Boolean, nullable=False)