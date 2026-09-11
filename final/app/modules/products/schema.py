from typing import Literal

from pydantic import BaseModel


ProductStatus = Literal["SELL", "STOP"]


class ProductCreate(BaseModel):
    supplier_id: str | None = None
    sku: str | None = None
    name: str
    # 기존 V1 필드 유지
    supply_price: float = 0
    sale_price: float = 0
    shipping_fee: float = 0
    market_fee_rate: float = 0
    # 계산엔진 V1 필드
    purchase_price: float = 0
    international_shipping: float = 0
    domestic_shipping: float = 0
    selling_price: float = 0
    fee_rate: float = 0
    vat_rate: float = 0.1
    main_image_url: str | None = None
    detail_image_url: str | None = None
    # status는 자동 SELL/STOP 엔진이 판정하므로 입력값은 무시됩니다.
    status: ProductStatus | None = None


class ProductUpdate(BaseModel):
    supplier_id: str | None = None
    sku: str | None = None
    name: str | None = None
    # 기존 V1 필드 유지
    supply_price: float | None = None
    sale_price: float | None = None
    shipping_fee: float | None = None
    market_fee_rate: float | None = None
    # 계산엔진 V1 필드
    purchase_price: float | None = None
    international_shipping: float | None = None
    domestic_shipping: float | None = None
    selling_price: float | None = None
    fee_rate: float | None = None
    vat_rate: float | None = None
    main_image_url: str | None = None
    detail_image_url: str | None = None
    # status는 자동 SELL/STOP 엔진이 재판정하므로 입력값은 무시됩니다.
    status: ProductStatus | None = None
