from pydantic import BaseModel, Field


class TaxReserveSettings(BaseModel):
    profit_tax_reserve_rate: float = Field(10, ge=0, le=100)
    income_tax_reserve_rate: float = Field(0, ge=0, le=100)
