from sqlalchemy import Column, String, Numeric, DateTime
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
from app.db.base import Base


class PortfolioSnapshot(Base):

    __tablename__ = "portfolio_snapshots"

    id = Column(String, primary_key=True)

    agent_id = Column(UUID(as_uuid=True))

    wallet = Column(String)

    bnb_balance = Column(Numeric)

    bnb_value_usd = Column(Numeric)

    token_value = Column(Numeric)

    total_value = Column(Numeric)

    realized_pnl = Column(Numeric)

    unrealized_pnl = Column(Numeric)

    total_pnl = Column(Numeric)

    pnl_percent = Column(Numeric)

    created_at = Column(DateTime, default=datetime.utcnow)