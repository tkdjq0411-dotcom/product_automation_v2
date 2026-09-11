from pydantic import BaseModel


class TaxTypeUpdate(BaseModel):
    tax_type: str