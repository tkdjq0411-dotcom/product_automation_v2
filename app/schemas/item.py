from pydantic import BaseModel

class ItemIn(BaseModel):
    name: str
    buy_price: int
    sell_price: int
    shipping_fee: int
