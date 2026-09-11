from fastapi import HTTPException

from app.db.supabase import insert, select
from app.modules.calculations.engine import calculate_profit
from app.modules.plans.service import ensure_usage_available


async def list_calculations_service(user_id: str):
    return await select("margin_calculations", {"user_id": f"eq.{user_id}", "order": "created_at.desc"})


async def get_calculation_service(user_id: str, calculation_id: str):
    rows = await select(
        "margin_calculations",
        {"id": f"eq.{calculation_id}", "user_id": f"eq.{user_id}", "limit": "1"},
    )
    if not rows:
        raise HTTPException(status_code=404, detail="calculation not found")
    return rows[0]


async def _ensure_product_owned(user_id: str, product_id: str | None) -> None:
    if not product_id:
        return
    rows = await select("products", {"id": f"eq.{product_id}", "user_id": f"eq.{user_id}", "limit": "1"})
    if not rows:
        raise HTTPException(status_code=400, detail="product not found for current user")


async def create_calculation_service(user_id: str, data: dict):
    await ensure_usage_available(user_id, "calculations")
    if data.get("tax_type") not in ["simple", "general"]:
        raise HTTPException(status_code=400, detail="invalid tax type")
    await _ensure_product_owned(user_id, data.get("product_id"))

    purchase = data.get("purchase_price")
    if purchase is None:
        purchase = data.get("supply_price") or 0
    selling = data.get("selling_price")
    if selling is None:
        selling = data.get("sale_price") or 0
    domestic = data.get("domestic_shipping")
    if domestic is None:
        domestic = data.get("shipping_fee") or 0
    fee_rate = data.get("fee_rate")
    if fee_rate is None:
        fee_rate = data.get("market_fee_rate") or 0

    result = calculate_profit(
        purchase_price=purchase,
        international_shipping=data.get("international_shipping") or 0,
        domestic_shipping=domestic,
        selling_price=selling,
        fee_rate=fee_rate,
        vat_rate=data.get("vat_rate", 0.1),
    )

    # 기존 DB 컬럼을 유지해 기존 데이터/기능을 깨지 않으면서 동일 계산식을 저장합니다.
    payload = {
        "user_id": user_id,
        "product_id": data.get("product_id"),
        "supply_price": result["purchase_price"],
        "sale_price": result["selling_price"],
        "shipping_fee": result["international_shipping"] + result["domestic_shipping"],
        "market_fee_rate": result["fee_rate"],
        "vat_rate": result["vat_rate"],
        "tax_type": data.get("tax_type", "simple"),
        "market_fee": result["fee_amount"],
        "vat_amount": result["vat_amount"],
        "total_cost": result["total_cost"],
        "net_profit": result["net_profit"],
    }
    saved = await insert("margin_calculations", payload)
    if not saved:
        raise HTTPException(status_code=400, detail="calculation save failed")

    return {
        "calculation": saved[0],
        **result,
    }
