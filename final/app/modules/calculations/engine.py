from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, ROUND_CEILING
from fastapi import HTTPException

MONEY_QUANT = Decimal("0.01")
RATE_QUANT = Decimal("0.000001")


def _decimal(value, field: str) -> Decimal:
    try:
        number = Decimal(str(0 if value is None or value == "" else value))
    except (InvalidOperation, ValueError, TypeError):
        raise HTTPException(status_code=422, detail=f"{field} must be a number")
    if not number.is_finite():
        raise HTTPException(status_code=422, detail=f"{field} must be finite")
    return number


def _money(value: Decimal) -> float:
    return float(value.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP))


def calculate_profit(
    *,
    purchase_price=0,
    international_shipping=0,
    domestic_shipping=0,
    selling_price=0,
    fee_rate=0,
    vat_rate=0.1,
) -> dict:
    purchase = _decimal(purchase_price, "purchase_price")
    intl = _decimal(international_shipping, "international_shipping")
    domestic = _decimal(domestic_shipping, "domestic_shipping")
    selling = _decimal(selling_price, "selling_price")
    fee = _decimal(fee_rate, "fee_rate")
    vat = _decimal(vat_rate, "vat_rate")

    for field, value in (
        ("purchase_price", purchase),
        ("international_shipping", intl),
        ("domestic_shipping", domestic),
        ("selling_price", selling),
    ):
        if value < 0:
            raise HTTPException(status_code=422, detail=f"{field} cannot be negative")
    for field, value in (("fee_rate", fee), ("vat_rate", vat)):
        if value < 0 or value > 1:
            raise HTTPException(status_code=422, detail=f"{field} must be between 0 and 1")

    base_cost = purchase + intl + domestic
    fee_amount = selling * fee
    vat_amount = selling * vat
    total_cost = base_cost + fee_amount + vat_amount
    net_profit = selling - total_cost
    margin_rate = (net_profit / selling * Decimal("100")) if selling else Decimal("0")

    return {
        "purchase_price": _money(purchase),
        "international_shipping": _money(intl),
        "domestic_shipping": _money(domestic),
        "selling_price": _money(selling),
        "fee_rate": float(fee.quantize(RATE_QUANT, rounding=ROUND_HALF_UP)),
        "vat_rate": float(vat.quantize(RATE_QUANT, rounding=ROUND_HALF_UP)),
        "base_cost": _money(base_cost),
        "fee_amount": _money(fee_amount),
        "vat_amount": _money(vat_amount),
        "total_cost": _money(total_cost),
        "net_profit": _money(net_profit),
        "margin_rate": float(margin_rate.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
    }


def calculate_pricing_targets(
    *,
    purchase_price=0,
    international_shipping=0,
    domestic_shipping=0,
    fee_rate=0,
    vat_rate=0.1,
    min_net_profit=2000,
    min_margin_rate=5,
) -> dict:
    """판매가에 연동되는 수수료/VAT를 역산해 손익분기점과 SELL 권장판매가를 계산합니다."""
    purchase = _decimal(purchase_price, "purchase_price")
    intl = _decimal(international_shipping, "international_shipping")
    domestic = _decimal(domestic_shipping, "domestic_shipping")
    fee = _decimal(fee_rate, "fee_rate")
    vat = _decimal(vat_rate, "vat_rate")
    target_profit = _decimal(min_net_profit, "min_net_profit")
    target_margin_pct = _decimal(min_margin_rate, "min_margin_rate")

    for field, value in (
        ("purchase_price", purchase),
        ("international_shipping", intl),
        ("domestic_shipping", domestic),
        ("min_net_profit", target_profit),
        ("min_margin_rate", target_margin_pct),
    ):
        if value < 0:
            raise HTTPException(status_code=422, detail=f"{field} cannot be negative")
    for field, value in (("fee_rate", fee), ("vat_rate", vat)):
        if value < 0 or value > 1:
            raise HTTPException(status_code=422, detail=f"{field} must be between 0 and 1")

    base_cost = purchase + intl + domestic
    variable_rate = fee + vat
    profit_factor = Decimal("1") - variable_rate
    if profit_factor <= 0:
        raise HTTPException(status_code=422, detail="fee_rate + vat_rate must be less than 1")

    margin_fraction = target_margin_pct / Decimal("100")
    margin_factor = profit_factor - margin_fraction
    if margin_factor <= 0:
        raise HTTPException(status_code=422, detail="target margin cannot be achieved with current fee/vat rates")

    break_even = base_cost / profit_factor
    profit_target_price = (base_cost + target_profit) / profit_factor
    margin_target_price = (base_cost / margin_factor) if base_cost else Decimal("0")
    recommended = max(profit_target_price, margin_target_price)

    def ceil_money(value: Decimal) -> float:
        return float(value.quantize(MONEY_QUANT, rounding=ROUND_CEILING))

    return {
        "base_cost": _money(base_cost),
        "variable_rate": float(variable_rate.quantize(RATE_QUANT, rounding=ROUND_HALF_UP)),
        "break_even_price": ceil_money(break_even),
        "profit_target_price": ceil_money(profit_target_price),
        "margin_target_price": ceil_money(margin_target_price),
        "recommended_selling_price": ceil_money(recommended),
        "min_net_profit": _money(target_profit),
        "min_margin_rate": float(target_margin_pct.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
    }
