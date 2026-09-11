from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from fastapi import HTTPException

from app.db.supabase import select

MONEY = Decimal("0.01")


def _d(value) -> Decimal:
    try:
        number = Decimal(str(0 if value is None or value == "" else value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")
    return number if number.is_finite() else Decimal("0")


def _money(value: Decimal) -> float:
    return float(value.quantize(MONEY, rounding=ROUND_HALF_UP))


def _row_tax(row: dict) -> dict:
    sale = _d(row.get("sale_price"))
    vat_rate = _d(row.get("vat_rate"))
    vat = _d(row.get("vat_amount"))
    return {
        "calculation_id": row.get("id"),
        "product_id": row.get("product_id"),
        "tax_type": row.get("tax_type") or "simple",
        "sale_price": _money(sale),
        "vat_rate": float(vat_rate),
        "vat_amount": _money(vat),
        "net_profit": _money(_d(row.get("net_profit"))),
        "created_at": row.get("created_at"),
    }


async def tax_summary_service(user_id: str):
    rows = await select("margin_calculations", {"user_id": f"eq.{user_id}", "order": "created_at.desc"})
    items = [_row_tax(row) for row in rows]
    total_sales = sum((_d(x["sale_price"]) for x in items), Decimal("0"))
    total_vat = sum((_d(x["vat_amount"]) for x in items), Decimal("0"))
    total_profit = sum((_d(x["net_profit"]) for x in items), Decimal("0"))
    by_type = {"simple": 0, "general": 0}
    for item in items:
        if item["tax_type"] in by_type:
            by_type[item["tax_type"]] += 1
    return {
        "calculation_count": len(items),
        "total_sales": _money(total_sales),
        "total_vat_amount": _money(total_vat),
        "total_net_profit": _money(total_profit),
        "simple_count": by_type["simple"],
        "general_count": by_type["general"],
        "items": items,
        "notice": "부가세 예상치는 저장된 계산의 vat_rate를 적용한 참고값이며 실제 신고세액과 다를 수 있습니다.",
    }


async def product_tax_summary_service(user_id: str, product_id: str):
    products = await select("products", {"id": f"eq.{product_id}", "user_id": f"eq.{user_id}", "limit": "1"})
    if not products:
        raise HTTPException(status_code=404, detail="product not found")
    rows = await select("margin_calculations", {
        "user_id": f"eq.{user_id}", "product_id": f"eq.{product_id}", "order": "created_at.desc"
    })
    items = [_row_tax(row) for row in rows]
    return {
        "product_id": product_id,
        "calculation_count": len(items),
        "total_sales": _money(sum((_d(x["sale_price"]) for x in items), Decimal("0"))),
        "total_vat_amount": _money(sum((_d(x["vat_amount"]) for x in items), Decimal("0"))),
        "total_net_profit": _money(sum((_d(x["net_profit"]) for x in items), Decimal("0"))),
        "items": items,
    }
