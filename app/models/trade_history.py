from sqlalchemy import Column, String, Numeric, DateTime
from datetime import datetime

from app.db.base import Base


class TradeHistory(Base):

    __tablename__ = "trade_history"

    id = Column(String, primary_key=True)

    agent_id = Column(String)

    wallet = Column(String)

    token = Column(String)

    trade_type = Column(String)  # BUY / SELL

    amount_token = Column(Numeric)

    amount_bnb = Column(Numeric)

    price = Column(Numeric)

    tx_hash = Column(String)

    created_at = Column(DateTime, default=datetime.utcnow)