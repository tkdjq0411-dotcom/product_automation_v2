from pydantic import BaseModel, Field


class CalculationCreate(BaseModel):
    product_id: str | None = None

    # V1 계산엔진 표준 필드
    purchase_price: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    international_shipping: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    domestic_shipping: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    selling_price: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    fee_rate: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    vat_rate: float = Field(default=0.1, ge=0, le=1, allow_inf_nan=False)

    # 기존 API 호환 필드
    supply_price: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    sale_price: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    shipping_fee: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    market_fee_rate: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    tax_type: str = Field(default="simple", pattern="^(simple|general)$")
