from pydantic import BaseModel
class ConnectionUpdate(BaseModel):
    enabled: bool=False
    account_label: str|None=None
    note: str|None=None
