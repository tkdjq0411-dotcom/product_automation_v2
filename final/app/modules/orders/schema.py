from pydantic import BaseModel
class OrderCreate(BaseModel):
    app_order_id:str|None=None
    product_id:str|None=None
    customer_id:str|None=None
    payment_status:str="PAID"
    channel:str="MANUAL"
    order_no:str
    product_name:str
    option_text:str|None=None
    quantity:int=1
    sale_price:float=0
    buyer_name:str|None=None
    recipient:str|None=None
    phone:str|None=None
    address:str|None=None
    detail_address:str|None=None
    postal_code:str|None=None
    delivery_memo:str|None=None
    supplier_name:str|None=None
    source_url:str|None=None
    expected_profit:float=0
    status:str="NEW"
class OrderUpdate(BaseModel):
    channel:str|None=None; order_no:str|None=None; product_name:str|None=None; option_text:str|None=None; quantity:int|None=None; sale_price:float|None=None
    buyer_name:str|None=None; recipient:str|None=None; phone:str|None=None; address:str|None=None; detail_address:str|None=None; postal_code:str|None=None; delivery_memo:str|None=None
    supplier_name:str|None=None; source_url:str|None=None; expected_profit:float|None=None; status:str|None=None
    payment_status:str|None=None
