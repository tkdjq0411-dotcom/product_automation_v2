from pydantic import BaseModel, Field, field_validator

class SignupRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=256)
    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value=value.strip().lower()
        if not value or value.count("@") != 1 or " " in value:
            raise ValueError("invalid email")
        local,domain=value.rsplit("@",1)
        if not local or "." not in domain or domain.startswith(".") or domain.endswith("."):
            raise ValueError("invalid email")
        return value

class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)
    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()
