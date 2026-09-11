from pydantic import BaseModel
class ShipmentCreate(BaseModel):
    order_id:str
    carrier:str|None=None
    tracking_no:str|None=None
    status:str="READY"
    expected_delivery:str|None=None
    note:str|None=None
class ShipmentUpdate(BaseModel):
    carrier:str|None=None; tracking_no:str|None=None; status:str|None=None; expected_delivery:str|None=None; note:str|None=None
