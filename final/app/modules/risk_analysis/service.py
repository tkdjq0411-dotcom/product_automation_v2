from fastapi import HTTPException

from app.modules.inventory.service import list_inventory_service
from app.modules.products.risk import analyze_product_risk
from app.modules.products.service import _to_float


def _row(item: dict) -> dict:
    product = item["product"]
    risk = analyze_product_risk(
        net_profit=_to_float(product.get("net_profit")),
        margin_rate=_to_float(product.get("margin_rate")),
        selling_price=_to_float(product.get("selling_price")),
        recommended_price=0,
        quantity=int(item.get("quantity") or 0),
        minimum_quantity=int(item.get("minimum_quantity") or 0),
    )
    return {
        "product_id": product.get("id"),
        "name": product.get("name"),
        "sku": product.get("sku"),
        "status": product.get("status"),
        "net_profit": _to_float(product.get("net_profit")),
        "margin_rate": _to_float(product.get("margin_rate")),
        "selling_price": _to_float(product.get("selling_price")),
        "quantity": int(item.get("quantity") or 0),
        "minimum_quantity": int(item.get("minimum_quantity") or 0),
        **risk,
    }


async def list_risks_service(user_id: str):
    inventory = await list_inventory_service(user_id)
    rows = [_row(item) for item in inventory]
    rank = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    return sorted(rows, key=lambda x: (rank[x["risk_level"]], -x["risk_count"]))


async def product_risk_service(user_id: str, product_id: str):
    rows = await list_risks_service(user_id)
    for row in rows:
        if row["product_id"] == product_id:
            return row
    raise HTTPException(status_code=404, detail="product not found")


async def risk_summary_service(user_id: str):
    rows = await list_risks_service(user_id)
    return {
        "total_products": len(rows),
        "high_risk_count": sum(1 for x in rows if x["risk_level"] == "HIGH"),
        "medium_risk_count": sum(1 for x in rows if x["risk_level"] == "MEDIUM"),
        "low_risk_count": sum(1 for x in rows if x["risk_level"] == "LOW"),
        "total_risk_items": sum(x["risk_count"] for x in rows),
    }
