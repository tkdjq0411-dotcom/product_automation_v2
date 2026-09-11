from app.db.supabase import select
from app.modules.activity_logs.service import list_activity_logs_service
from app.modules.products.service import product_analysis_dashboard_service


def _number(value) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _status_count(rows, *statuses: str) -> int:
    allowed = {s.upper() for s in statuses}
    return sum(1 for row in rows if str(row.get("status") or "").upper() in allowed)


async def dashboard_overview_service(user_id: str):
    """무재고 판매 운영용 실제 데이터 대시보드.

    레거시 자체 재고(IN/OUT/LOW) 데이터는 사용하지 않습니다.
    주문·발주·배송·가격추적·상품 DB의 실제 저장값만 집계합니다.
    """
    product_data = await product_analysis_dashboard_service(user_id)
    orders = await select("orders", {"user_id": f"eq.{user_id}", "order": "created_at.desc"})
    purchases = await select("purchase_orders", {"user_id": f"eq.{user_id}", "order": "created_at.desc"})
    shipments = await select("shipments", {"user_id": f"eq.{user_id}", "order": "created_at.desc"})
    trackers = await select("price_trackers", {"user_id": f"eq.{user_id}"})
    sourcing = await select("sourcing_items", {"user_id": f"eq.{user_id}", "order": "created_at.desc"})
    activity_logs = await list_activity_logs_service(user_id, limit=10)

    summary = product_data["summary"]
    items = product_data["items"]
    total = int(summary.get("total_products") or 0)
    sell_count = int(summary.get("sell_count") or 0)
    stop_count = int(summary.get("stop_count") or 0)

    shipment_order_ids = {row.get("order_id") for row in shipments}
    awaiting_shipment = sum(
        1 for order in orders
        if str(order.get("status") or "").upper() == "ORDERED" and order.get("id") not in shipment_order_ids
    )

    status_ratios = {
        "sell": round((sell_count / total * 100), 2) if total else 0.0,
        "stop": round((stop_count / total * 100), 2) if total else 0.0,
    }
    top_profit = sorted(items, key=lambda x: _number(x.get("net_profit")), reverse=True)[:5]
    top_margin = sorted(items, key=lambda x: _number(x.get("margin_rate")), reverse=True)[:5]

    return {
        "summary": {
            **summary,
            "status_ratios": status_ratios,
            "orders_total": len(orders),
            "new_orders": _status_count(orders, "NEW"),
            "purchase_waiting": _status_count(purchases, "READY", "READY_TO_PAY", "BLOCKED"),
            "shipping_active": _status_count(shipments, "READY", "IN_TRANSIT", "OUT_FOR_DELIVERY"),
            "shipping_completed": _status_count(shipments, "DELIVERED"),
            "awaiting_shipment": awaiting_shipment,
            "price_tracking_count": sum(1 for row in trackers if int(row.get("tracking_enabled") or 0) == 1),
            "supplier_out_of_stock": sum(1 for row in sourcing if str(row.get("availability") or "").upper() == "OUT_OF_STOCK"),
        },
        "top_profit_products": top_profit,
        "top_margin_products": top_margin,
        "recent_orders": orders[:10],
        "recent_purchases": purchases[:10],
        "recent_shipments": shipments[:10],
        "recent_price_checks": sorted(trackers, key=lambda x: x.get("last_checked_at") or "", reverse=True)[:10],
        "supplier_unavailable_items": [
            row for row in sourcing if str(row.get("availability") or "").upper() != "AVAILABLE"
        ][:10],
        "recent_activity_logs": activity_logs,
    }
