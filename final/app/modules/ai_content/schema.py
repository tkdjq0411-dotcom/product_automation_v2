from pydantic import BaseModel
class DraftCreate(BaseModel):
    product_id:str|None=None
    source_name:str
