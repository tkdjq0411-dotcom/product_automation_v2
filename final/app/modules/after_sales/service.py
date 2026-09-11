from datetime import datetime

from fastapi import HTTPException

from app.db.supabase import insert, select, update
from app.modules.activity_logs.service import create_activity_log


async def process_request(user_id: str, order: dict, request_type: str, reason: str | None, refund_amount: float) -> dict:
    existing = await select("after_sales_requests", {"user_id": f"eq.{user_id}", "order_id": f'eq.{order["id"]}', "request_type": f"eq.{request_type}"})
    if existing and existing[0].get("status") not in {"FAILED", "COMPLETED"}:
        return existing[0]
    purchases = await select("purchase_orders", {"user_id": f"eq.{user_id}", "order_id": f'eq.{order["id"]}'})
    shipments = await select("shipments", {"user_id": f"eq.{user_id}", "order_id": f'eq.{order["id"]}'})
    purchase = purchases[0] if purchases else None
    shipment = shipments[0] if shipments else None
    shipped = bool(shipment and shipment.get("status") not in {"READY", None, ""})
    paid = bool(purchase and purchase.get("status") == "PAID")
    if request_type == "CANCEL" and not paid and not shipped:
        status, supplier_status, order_status = "COMPLETED", "CANCELLED", "CANCELLED"
        if purchase:
            await update("purchase_orders", {"id": f'eq.{purchase["id"]}'}, {"status": "CANCELLED", "updated_at": datetime.now().isoformat()})
    elif request_type == "CANCEL" and paid and not shipped:
        status, supplier_status, order_status = "SUPPLIER_CANCEL_REQUIRED", "MANUAL_REQUIRED", "CANCEL_REQUESTED"
    else:
        status, supplier_status = "RETURN_REQUIRED", "MANUAL_REQUIRED"
        order_status = "RETURN_REQUESTED" if request_type != "EXCHANGE" else "EXCHANGE_REQUESTED"
    now = datetime.now().isoformat()
    rows = await insert("after_sales_requests", {"user_id": user_id, "order_id": order["id"], "request_type": request_type,
        "reason": reason, "refund_amount": refund_amount, "status": status, "supplier_status": supplier_status,
        "channel_status": "RECEIVED", "completed_at": now if status == "COMPLETED" else None, "updated_at": now})
    await update("orders", {"id": f'eq.{order["id"]}', "user_id": f"eq.{user_id}"}, {"status": order_status, "updated_at": now})
    await create_activity_log(user_id, "after_sales", f"{request_type} 자동처리", "order", order["id"], order.get("order_no"), status)
    return rows[0]


async def request_by_id(user_id: str, order_id: str, request_type: str, reason: str | None, refund_amount: float) -> dict:
    orders = await select("orders", {"id": f"eq.{order_id}", "user_id": f"eq.{user_id}", "limit": "1"})
    if not orders:
        raise HTTPException(404, "주문을 찾을 수 없습니다.")
    return await process_request(user_id, orders[0], request_type, reason, refund_amount)
