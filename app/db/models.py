from sqlalchemy import Column, Integer, String, Float
from .database import Base

class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)

    buy_price = Column(Integer, nullable=False)
    sell_price = Column(Integer, nullable=False)
    shipping_fee = Column(Integer, nullable=False)

    commission_rate = Column(Float, default=0.1)
    commission_fee = Column(Integer, default=0)

    profit = Column(Integer, default=0)
    margin_rate = Column(Float, default=0)

    decision = Column(String, default="STOP")
    reason = Column(String, default="")
