from pydantic import BaseModel


class SellStopCreate(BaseModel):
    product_id: str | None = None
    margin_calculation_id: str | None = None
    net_profit: float