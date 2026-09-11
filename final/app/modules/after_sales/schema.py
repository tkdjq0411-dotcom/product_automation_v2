from typing import Literal

from pydantic import BaseModel, Field


RequestType = Literal["CANCEL", "RETURN", "EXCHANGE"]


class AfterSalesCreate(BaseModel):
    order_id: str
    request_type: RequestType
    reason: str | None = None
    refund_amount: float = Field(0, ge=0)


class ChannelEvent(BaseModel):
    channel: str
    order_no: str
    request_type: RequestType
    reason: str | None = None
    refund_amount: float = Field(0, ge=0)
