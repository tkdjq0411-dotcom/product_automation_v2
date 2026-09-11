from pydantic import BaseModel


class TaxWarningConfirm(BaseModel):
    confirmed: bool = True


class GeneralRecalculation(BaseModel):
    supply_price: float
    sale_price: float
    shipping_fee: float = 0
    market_fee_rate: float = 0
    vat_rate: float = 0.1