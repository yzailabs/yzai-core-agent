from sqlalchemy import Column, String, Numeric
import uuid
from app.db.base import Base

class TokenHolding(Base):

    __tablename__ = "token_holdings"

    id = Column(String, primary_key=True)

    agent_id = Column(String)

    wallet = Column(String)

    token = Column(String)

    balance = Column(Numeric)

    avg_price = Column(Numeric)

    value = Column(Numeric)