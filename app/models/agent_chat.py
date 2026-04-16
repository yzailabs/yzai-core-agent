from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.db.base import Base
import uuid


class AgentChatHistory(Base):
    __tablename__ = "agent_chat_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False)

    x_account = Column(String, nullable=False)

    human_msg = Column(Text, nullable=False)
    agent_response = Column(Text, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)