from pydantic import BaseModel
class TrackerUpdate(BaseModel):
    competitor_price:float|None=None
    tracking_enabled:bool|None=None
