from fastapi import APIRouter, Depends, HTTPException

from app.db.supabase import select
from app.modules.after_sales.schema import AfterSalesCreate, ChannelEvent
from app.modules.after_sales.service import process_request, request_by_id
from app.modules.operations_common import current_user_id

router = APIRouter()


@router.get("/", summary="취소·반품·교환 요청 목록")
async def list_requests(user_id: str = Depends(current_user_id)):
    rows = await select("after_sales_requests", {"user_id": f"eq.{user_id}", "order": "requested_at.desc"})
    return {"ok": True, "requests": rows}


@router.post("/", summary="취소·반품·교환 요청 처리")
async def create_request(data: AfterSalesCreate, user_id: str = Depends(current_user_id)):
    return {"ok": True, "request": await request_by_id(user_id, data.order_id, data.request_type, data.reason, data.refund_amount)}


@router.post("/channel-event", summary="판매채널 고객 요청 즉시 수신")
async def channel_event(data: ChannelEvent, user_id: str = Depends(current_user_id)):
    orders = await select("orders", {"user_id": f"eq.{user_id}", "channel": f"eq.{data.channel.upper()}", "order_no": f"eq.{data.order_no}", "limit": "1"})
    if not orders:
        raise HTTPException(404, "연결된 주문을 찾을 수 없습니다.")
    return {"ok": True, "request": await process_request(user_id, orders[0], data.request_type, data.reason, data.refund_amount)}
