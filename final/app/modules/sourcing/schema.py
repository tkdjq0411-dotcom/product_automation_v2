from pydantic import BaseModel, field_validator

class SourcingCreate(BaseModel):
    supplier_id: str | None = None
    supplier_name: str | None = None
    supplier_store_name: str | None = None
    supplier_store_url: str | None = None
    product_name: str
    source_url: str | None = None
    source_platform: str | None = None
    source_product_id: str | None = None
    source_currency: str | None = None
    import_status: str | None = None
    purchase_price: float = 0
    shipping_fee: float = 0
    options_text: str | None = None
    options_json: str | None = None
    image_url: str | None = None
    image_urls_json: str | None = None
    availability: str = "AVAILABLE"
    memo: str | None = None

class SourcingUpdate(BaseModel):
    supplier_id: str | None = None
    supplier_name: str | None = None
    supplier_store_name: str | None = None
    supplier_store_url: str | None = None
    product_name: str | None = None
    source_url: str | None = None
    source_platform: str | None = None
    source_product_id: str | None = None
    source_currency: str | None = None
    import_status: str | None = None
    purchase_price: float | None = None
    shipping_fee: float | None = None
    options_text: str | None = None
    options_json: str | None = None
    image_url: str | None = None
    image_urls_json: str | None = None
    availability: str | None = None
    memo: str | None = None

class URLImportRequest(BaseModel):
    url: str

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        value = value.strip()
        if not value.startswith(("http://", "https://")):
            raise ValueError("http:// 또는 https:// 상품 URL을 입력해주세요.")
        return value
