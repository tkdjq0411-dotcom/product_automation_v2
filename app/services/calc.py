from app.db.supabase import sb_select_one

def _int(x, default=0):
    try:
        return int(x)
    except Exception:
        return default

def _float(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default

async def get_admin_settings():
    row = await sb_select_one("admin_settings", {"id": "eq.1"})
    if not row:
        # fallback
        return {"min_profit": 500, "safety_buffer_rate": 0.01}
    return row

async def resolve_fee_rule(market: str, category: str):
    # 1) exact
    row = await sb_select_one("fee_rules", {"market": f"eq.{market}", "category": f"eq.{category}"})
    if row:
        return row
    # 2) unknown category fallback
    row = await sb_select_one("fee_rules", {"market": f"eq.{market}", "category": "eq.unknown"})
    if row:
        return row
    # 3) full fallback
    return {"base_rate": 0.0, "category_rate": 0.0}

async def compute_decision(
    *,
    market: str,
    category: str,
    tax_type: str,
    buy_price: int,
    sell_price: int,
    shipping_fee: int,
):
    settings = await get_admin_settings()
    min_profit = _int(settings.get("min_profit", 500), 500)
    safety_buffer_rate = _float(settings.get("safety_buffer_rate", 0.01), 0.01)

    rule = await resolve_fee_rule(market, category)
    base_rate = _float(rule.get("base_rate", 0.0))
    category_rate = _float(rule.get("category_rate", 0.0))
    commission_rate = base_rate + category_rate

    commission_fee = int(round(sell_price * commission_rate))

    # VAT (매출 부가세 개념을 단순화)
    # - simple(간이): 0 처리(나중에 상세화)
    # - general(일반): 수수료/매출 VAT를 10%로 단순 적용(나중에 정확화)
    if tax_type == "general":
        vat_fee = int(round(sell_price * 0.1))
    else:
        vat_fee = 0

    total_cost = buy_price + shipping_fee + commission_fee + vat_fee
    profit = sell_price - total_cost
    margin_rate = (profit / sell_price) if sell_price > 0 else 0.0

    # 안전 버퍼 반영 (예: 1% 버퍼면 sell_price의 1%를 안전비용으로 추가)
    safety_cost = int(round(sell_price * safety_buffer_rate))
    profit_after_buffer = profit - safety_cost

    if profit_after_buffer >= min_profit:
        decision = "SELL"
        reason = f"profit_after_buffer({profit_after_buffer}) >= min_profit({min_profit})"
    else:
        decision = "STOP"
        reason = f"profit_after_buffer({profit_after_buffer}) < min_profit({min_profit})"

    return {
        "commission_rate": commission_rate,
        "commission_fee": commission_fee,
        "vat_fee": vat_fee,
        "total_cost": total_cost,
        "profit": profit,
        "margin_rate": margin_rate,
        "decision": decision,
        "reason": reason,
    }
