from typing import Literal
from pydantic import BaseModel, Field
InventoryType = Literal["IN", "OUT"]
class InventoryInCreate(BaseModel):
    product_id: str = Field(min_length=1, max_length=100)
    quantity: int = Field(gt=0, le=1_000_000_000)
class InventoryOutCreate(BaseModel):
    product_id: str = Field(min_length=1, max_length=100)
    quantity: int = Field(gt=0, le=1_000_000_000)
class InventoryMinimumUpdate(BaseModel):
    minimum_quantity: int = Field(ge=0, le=1_000_000_000)
