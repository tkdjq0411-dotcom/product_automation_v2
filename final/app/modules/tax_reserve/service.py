from decimal import Decimal, ROUND_HALF_UP

from app.db.supabase import select, update


def _d(value) -> Decimal:
    return Decimal(str(value or 0))


def _money(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


async def reserve_summary(user_id: str) -> dict:
    users = await select("users", {"id": f"eq.{user_id}", "limit": "1"})
    user = users[0]
    orders = await select("orders", {"user_id": f"eq.{user_id}"})
    purchases = await select("purchase_orders", {"user_id": f"eq.{user_id}"})
    active = [o for o in orders if o.get("status") not in {"CANCELLED", "REFUNDED"}]
    total_sales = sum((_d(o.get("sale_price")) for o in active), Decimal("0"))
    total_profit = sum((_d(o.get("expected_profit")) for o in active), Decimal("0"))
    paid_purchase = sum((_d(p.get("amount")) for p in purchases if p.get("status") == "PAID"), Decimal("0"))
    output_vat = total_sales * Decimal("10") / Decimal("110")
    input_vat = paid_purchase * Decimal("10") / Decimal("110")
    estimated_vat_payable = max(Decimal("0"), output_vat - input_vat)
    profit_rate = _d(user.get("profit_tax_reserve_rate")) / Decimal("100")
    income_rate = _d(user.get("income_tax_reserve_rate")) / Decimal("100")
    profit_reserve = max(Decimal("0"), total_profit) * profit_rate
    income_reserve = max(Decimal("0"), total_profit) * income_rate
    return {
        "tax_type": user.get("tax_type") or "simple",
        "total_sales": _money(total_sales), "total_profit": _money(total_profit),
        "estimated_output_vat": _money(output_vat), "estimated_input_vat_credit": _money(input_vat),
        "estimated_vat_payable": _money(estimated_vat_payable),
        "profit_tax_reserve_rate": float(profit_rate * 100), "profit_tax_reserve": _money(profit_reserve),
        "income_tax_reserve_rate": float(income_rate * 100), "income_tax_reserve": _money(income_reserve),
        "total_reserved": _money(profit_reserve + income_reserve),
        "usable_profit": _money(total_profit - profit_reserve - income_reserve),
        "notice": "적립금은 자금관리용 예상치입니다. 실제 부가세는 매출세액에서 공제 가능한 매입세액을 차감해 신고합니다.",
    }


async def save_settings(user_id: str, data: dict) -> None:
    await update("users", {"id": f"eq.{user_id}"}, data)
