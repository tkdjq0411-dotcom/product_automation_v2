from pydantic import BaseModel
class PurchaseCreate(BaseModel):
    order_id:str
    supplier_name:str|None=None
    supplier_url:str|None=None
    amount:float=0
    status:str="READY"
    note:str|None=None
class PurchaseUpdate(BaseModel):
    supplier_name:str|None=None; supplier_url:str|None=None; amount:float|None=None; status:str|None=None; note:str|None=None
