from pydantic import BaseModel, Field, field_validator


class SupplierCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    memo: str | None = Field(default=None, max_length=1000)
    source_platform: str | None = Field(default=None, max_length=50)
    store_name: str | None = Field(default=None, max_length=200)
    store_url: str | None = Field(default=None, max_length=1000)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("supplier name is required")
        return value

    @field_validator("memo")
    @classmethod
    def normalize_memo(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class SupplierUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    memo: str | None = Field(default=None, max_length=1000)
    source_platform: str | None = Field(default=None, max_length=50)
    store_name: str | None = Field(default=None, max_length=200)
    store_url: str | None = Field(default=None, max_length=1000)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("supplier name is required")
        return value

    @field_validator("memo")
    @classmethod
    def normalize_memo(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None
