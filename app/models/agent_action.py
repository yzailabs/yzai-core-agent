import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base


class AgentAction(Base):
    __tablename__ = "agent_actions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    agent_id = Column(UUID(as_uuid=True), nullable=False)
    agent_name = Column(String, nullable=False)
    agent_address = Column(String, nullable=False)

    action = Column(String, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)