import math
from uuid import uuid4
from datetime import datetime
from urllib.parse import urlparse

from fastapi import HTTPException

from app.modules.activity_logs.service import create_activity_log
from app.modules.plans.service import ensure_usage_available
from app.db.supabase import delete, insert, select, update
from app.modules.calculations.engine import calculate_profit, calculate_pricing_targets
from app.modules.products.sell_stop import DEFAULT_SELL_STOP_POLICY, judge_sell_stop, policy_dict
from app.modules.products.risk import analyze_product_risk


def sanitize_product_payload(data: dict) -> dict:
    payload = {key: value for key, value in data.items() if value is not None}
    if "sku" in payload and isinstance(payload["sku"], str):
        payload["sku"] = payload["sku"].strip() or None
    # status는 수동 입력하지 않고 자동 SELL/STOP 엔진에서만 결정합니다.
    payload.pop("status", None)
    payload.pop("status_reason", None)
    return payload


def _normalize_sku(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _to_float(value, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


PRODUCT_NUMBER_FIELDS = {
    "supply_price", "sale_price", "shipping_fee", "market_fee_rate",
    "purchase_price", "international_shipping", "domestic_shipping",
    "selling_price", "fee_rate", "vat_rate",
}


def _validate_product_payload(payload: dict, *, creating: bool = False) -> dict:
    if creating or "name" in payload:
        name = str(payload.get("name") or "").strip()
        if not name:
            raise HTTPException(status_code=422, detail="product name is required")
        if len(name) > 200:
            raise HTTPException(status_code=422, detail="product name is too long")
        payload["name"] = name

    for field in PRODUCT_NUMBER_FIELDS:
        if field not in payload or payload[field] is None:
            continue
        try:
            value = float(payload[field])
        except (TypeError, ValueError):
            raise HTTPException(status_code=422, detail=f"{field} must be a number")
        if not math.isfinite(value):
            raise HTTPException(status_code=422, detail=f"{field} must be finite")
        if value < 0:
            raise HTTPException(status_code=422, detail=f"{field} cannot be negative")
        if value > 1_000_000_000_000:
            raise HTTPException(status_code=422, detail=f"{field} is too large")
        payload[field] = value

    for field in ("fee_rate", "market_fee_rate", "vat_rate"):
        if field in payload and payload[field] is not None and float(payload[field]) > 1:
            raise HTTPException(status_code=422, detail=f"{field} must be between 0 and 1")

    if "sku" in payload and payload["sku"] is not None and len(str(payload["sku"])) > 100:
        raise HTTPException(status_code=422, detail="sku is too long")

    for field in ("main_image_url", "detail_image_url"):
        if field not in payload:
            continue
        value = payload[field]
        if value in (None, ""):
            payload[field] = None
            continue
        value = str(value).strip()
        if len(value) > 2048:
            raise HTTPException(status_code=422, detail=f"{field} is too long")
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise HTTPException(status_code=422, detail=f"{field} must be a valid http/https URL")
        payload[field] = value

    return payload


def _generate_sku() -> str:
    return f"SKU-{uuid4().hex[:10].upper()}"


def calculate_product_profit_fields(data: dict) -> dict:
    """계산엔진 V1 단일 계산식. total_cost에는 원가+배송비+수수료+VAT가 모두 포함됩니다."""
    result = calculate_profit(
        purchase_price=data.get("purchase_price"),
        international_shipping=data.get("international_shipping"),
        domestic_shipping=data.get("domestic_shipping"),
        selling_price=data.get("selling_price"),
        fee_rate=data.get("fee_rate"),
        vat_rate=data.get("vat_rate"),
    )
    data.update({
        "purchase_price": result["purchase_price"],
        "international_shipping": result["international_shipping"],
        "domestic_shipping": result["domestic_shipping"],
        "selling_price": result["selling_price"],
        "fee_rate": result["fee_rate"],
        "vat_rate": result["vat_rate"],
        "total_cost": result["total_cost"],
        "fee_amount": result["fee_amount"],
        "vat_amount": result["vat_amount"],
        "net_profit": result["net_profit"],
        "margin_rate": result["margin_rate"],
    })
    return data



def apply_auto_sell_stop_fields(data: dict) -> dict:
    """V2 자동 SELL/STOP 판정. 기준은 sell_stop.py 한 곳에서 관리합니다."""
    net_profit = _to_float(data.get("net_profit"))
    selling_price = _to_float(data.get("selling_price"))
    margin_rate = _to_float(data.get("margin_rate"))

    decision = judge_sell_stop(
        net_profit=net_profit,
        margin_rate=margin_rate,
        selling_price=selling_price,
    )
    data.update(decision)
    return data




def _utc_now_text() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _recalculation_history_payload(user_id: str, before: dict, after: dict) -> dict:
    return {
        "id": str(uuid4()),
        "user_id": user_id,
        "product_id": after.get("id") or before.get("id"),
        "old_status": before.get("status"),
        "new_status": after.get("status") or "STOP",
        "net_profit": _to_float(after.get("net_profit")),
        "margin_rate": _to_float(after.get("margin_rate")),
        "reason": after.get("status_reason") or "순이익 부족",
    }


def _product_recalculation_result(product: dict, old_status: str | None) -> dict:
    return {
        "product_id": product.get("id"),
        "name": product.get("name"),
        "sku": product.get("sku"),
        "old_status": old_status,
        "new_status": product.get("status"),
        "status_changed": old_status != product.get("status"),
        "net_profit": product.get("net_profit"),
        "margin_rate": product.get("margin_rate"),
        "reason": product.get("status_reason"),
        "last_recalculated_at": product.get("last_recalculated_at"),
    }

def apply_legacy_price_defaults(payload: dict) -> dict:
    """기존 화면/테스트의 supply_price 계열 입력을 계산엔진 필드 기본값으로 호환합니다."""
    if payload.get("purchase_price") is None and payload.get("supply_price") is not None:
        payload["purchase_price"] = payload.get("supply_price")
    if payload.get("selling_price") is None and payload.get("sale_price") is not None:
        payload["selling_price"] = payload.get("sale_price")
    if payload.get("domestic_shipping") is None and payload.get("shipping_fee") is not None:
        payload["domestic_shipping"] = payload.get("shipping_fee")
    if payload.get("fee_rate") is None and payload.get("market_fee_rate") is not None:
        payload["fee_rate"] = payload.get("market_fee_rate")
    return payload


async def _get_product_by_sku(user_id: str, sku: str | None):
    sku = _normalize_sku(sku)
    if not sku:
        return None

    rows = await select(
        "products",
        {
            "user_id": f"eq.{user_id}",
            "sku": f"eq.{sku}",
            "limit": "1",
        },
    )
    return rows[0] if rows else None


async def _ensure_unique_sku(user_id: str, sku: str | None, exclude_product_id: str | None = None) -> None:
    existing = await _get_product_by_sku(user_id, sku)
    if existing and existing.get("id") != exclude_product_id:
        raise HTTPException(status_code=400, detail="sku already exists")


async def _ensure_supplier_owned(user_id: str, supplier_id: str | None) -> None:
    if not supplier_id:
        return
    rows = await select(
        "suppliers",
        {"id": f"eq.{supplier_id}", "user_id": f"eq.{user_id}", "limit": "1"},
    )
    if not rows:
        raise HTTPException(status_code=400, detail="supplier not found for current user")


async def list_products_service(
    user_id: str,
    sku: str | None = None,
    q: str | None = None,
    status: str | None = None,
    supplier_id: str | None = None,
    min_selling_price: float | None = None,
    max_selling_price: float | None = None,
    min_net_profit: float | None = None,
    max_net_profit: float | None = None,
    min_margin_rate: float | None = None,
    max_margin_rate: float | None = None,
    sort_by: str = "created",
    sort_dir: str = "desc",
):
    products = await select("products", {"user_id": f"eq.{user_id}", "order": "id.desc"})

    # 과거 3단계 정책에서 저장된 HOLD 데이터도 새 2단계 정책으로 즉시 해석합니다.
    for product in products:
        if str(product.get("status") or "").upper() == "HOLD":
            decision = judge_sell_stop(
                net_profit=_to_float(product.get("net_profit")),
                margin_rate=_to_float(product.get("margin_rate")),
                selling_price=_to_float(product.get("selling_price")),
            )
            product.update(decision)

    sku = _normalize_sku(sku)
    q = str(q or "").strip().lower()
    if sku and len(sku) > 100:
        raise HTTPException(status_code=422, detail="sku query is too long")
    if len(q) > 200:
        raise HTTPException(status_code=422, detail="search query is too long")
    if supplier_id and len(str(supplier_id)) > 100:
        raise HTTPException(status_code=422, detail="supplier_id is too long")
    if sku:
        products = [p for p in products if sku.lower() in str(p.get("sku") or "").lower()]
    if q:
        products = [p for p in products if q in str(p.get("sku") or "").lower() or q in str(p.get("name") or "").lower()]

    if status:
        normalized_status = str(status).upper()
        if normalized_status not in {"SELL", "STOP"}:
            raise HTTPException(status_code=422, detail="status must be SELL or STOP")
        products = [p for p in products if str(p.get("status") or "").upper() == normalized_status]

    if supplier_id:
        products = [p for p in products if str(p.get("supplier_id") or "") == str(supplier_id)]

    ranges = [
        ("selling_price", min_selling_price, max_selling_price),
        ("net_profit", min_net_profit, max_net_profit),
        ("margin_rate", min_margin_rate, max_margin_rate),
    ]
    for field, minimum, maximum in ranges:
        if minimum is not None and maximum is not None and minimum > maximum:
            raise HTTPException(status_code=422, detail=f"minimum {field} cannot exceed maximum {field}")
        if minimum is not None:
            products = [p for p in products if _to_float(p.get(field)) >= minimum]
        if maximum is not None:
            products = [p for p in products if _to_float(p.get(field)) <= maximum]

    sort_fields = {
        "created": "id", "name": "name", "sku": "sku", "selling_price": "selling_price",
        "net_profit": "net_profit", "margin_rate": "margin_rate",
    }
    if sort_by not in sort_fields:
        raise HTTPException(status_code=422, detail="invalid sort_by")
    if sort_dir not in {"asc", "desc"}:
        raise HTTPException(status_code=422, detail="sort_dir must be asc or desc")
    field = sort_fields[sort_by]
    numeric = field in {"selling_price", "net_profit", "margin_rate"}
    def key(product):
        value = product.get(field)
        return _to_float(value) if numeric else str(value or "").lower()
    products = sorted(products, key=key, reverse=sort_dir == "desc")
    return products


async def get_product_service(user_id: str, product_id: str):
    rows = await select(
        "products",
        {
            "id": f"eq.{product_id}",
            "user_id": f"eq.{user_id}",
            "limit": "1",
        },
    )

    if not rows:
        raise HTTPException(status_code=404, detail="product not found")

    return rows[0]


async def create_product_service(user_id: str, data: dict):
    await ensure_usage_available(user_id, "products")
    payload = sanitize_product_payload(data)
    payload = _validate_product_payload(payload, creating=True)
    if not payload.get("sku"):
        payload["sku"] = _generate_sku()
    payload = apply_legacy_price_defaults(payload)
    payload = calculate_product_profit_fields(payload)
    payload = apply_auto_sell_stop_fields(payload)
    payload["last_recalculated_at"] = _utc_now_text()
    await _ensure_unique_sku(user_id, payload.get("sku"))
    await _ensure_supplier_owned(user_id, payload.get("supplier_id"))

    payload = {
        "id": str(uuid4()),
        **payload,
        "user_id": user_id,
    }

    created = await insert("products", payload)

    if not created:
        raise HTTPException(status_code=400, detail="product create failed")

    product = created[0]
    await insert(
        "product_recalculation_history",
        _recalculation_history_payload(user_id, {"id": product.get("id"), "status": None}, product),
    )
    await create_activity_log(user_id, "PRODUCT", "CREATE", "product", product.get("id"), product.get("name"),
                              f"상품 등록 · {product.get('status')}")
    return product


async def update_product_service(user_id: str, product_id: str, data: dict):
    existing_product = await get_product_service(user_id, product_id)
    supplier_was_provided = "supplier_id" in data
    requested_supplier_id = data.get("supplier_id")
    payload = sanitize_product_payload(data)
    payload = _validate_product_payload(payload, creating=False)
    if supplier_was_provided:
        payload["supplier_id"] = str(requested_supplier_id).strip() if requested_supplier_id else None

    if not payload:
        raise HTTPException(status_code=400, detail="no product fields to update")

    merged_for_calculation = {**existing_product, **payload}
    merged_for_calculation = apply_legacy_price_defaults(merged_for_calculation)
    calculated_fields = calculate_product_profit_fields(merged_for_calculation)
    calculated_fields = apply_auto_sell_stop_fields(calculated_fields)
    for key in ["total_cost", "fee_amount", "vat_amount", "net_profit", "margin_rate", "status", "status_reason"]:
        payload[key] = calculated_fields[key]
    payload["last_recalculated_at"] = _utc_now_text()

    if "sku" in payload:
        await _ensure_unique_sku(user_id, payload.get("sku"), exclude_product_id=product_id)
    if "supplier_id" in payload:
        await _ensure_supplier_owned(user_id, payload.get("supplier_id"))

    updated = await update(
        "products",
        {
            "id": f"eq.{product_id}",
            "user_id": f"eq.{user_id}",
        },
        payload,
    )

    if not updated:
        raise HTTPException(status_code=400, detail="product update failed")

    product = updated[0]
    if existing_product.get("status") != product.get("status"):
        await insert(
            "product_recalculation_history",
            _recalculation_history_payload(user_id, existing_product, product),
        )
    changed_fields = sorted(key for key in payload.keys() if key not in {"last_recalculated_at"})
    await create_activity_log(user_id, "PRODUCT", "UPDATE", "product", product.get("id"), product.get("name"),
                              "상품 수정 · " + ", ".join(changed_fields))
    return product


async def delete_product_service(user_id: str, product_id: str):
    existing_product = await get_product_service(user_id, product_id)

    deleted = await delete(
        "products",
        {
            "id": f"eq.{product_id}",
            "user_id": f"eq.{user_id}",
        },
    )

    if not deleted:
        raise HTTPException(status_code=400, detail="product delete failed")

    await create_activity_log(user_id, "PRODUCT", "DELETE", "product", product_id, existing_product.get("name"), "상품 삭제")
    return deleted[0]


def _status_reason_key(product: dict) -> str:
    status = str(product.get("status") or "STOP")
    if status == "SELL":
        return "sellable_count"
    return "stop_reason_count"




def _pricing_analysis(product: dict) -> dict:
    targets = calculate_pricing_targets(
        purchase_price=product.get("purchase_price"),
        international_shipping=product.get("international_shipping"),
        domestic_shipping=product.get("domestic_shipping"),
        fee_rate=product.get("fee_rate"),
        vat_rate=product.get("vat_rate"),
        min_net_profit=0,
        min_margin_rate=0,
    )
    current_price = _to_float(product.get("selling_price"))
    floor_price = _to_float(targets.get("break_even_price"))
    return {
        "base_cost": targets.get("base_cost"),
        "variable_rate": targets.get("variable_rate"),
        "break_even_price": targets.get("break_even_price"),
        "minimum_sellable_price": targets.get("break_even_price"),
        "current_selling_price": current_price,
        "price_gap_to_floor": round(max(0.0, floor_price - current_price), 2),
        "above_floor": current_price >= floor_price,
    }


async def product_pricing_analysis_service(user_id: str, product_id: str):
    product = await get_product_service(user_id, product_id)
    return {"product": product, "pricing": _pricing_analysis(product)}


async def all_product_pricing_analysis_service(user_id: str):
    products = await list_products_service(user_id)
    rows = []
    for product in products:
        rows.append({
            "product_id": product.get("id"),
            "name": product.get("name"),
            "sku": product.get("sku"),
            "status": product.get("status"),
            **_pricing_analysis(product),
        })
    return rows


def _risk_analysis(product: dict, inventory: dict) -> dict:
    pricing = _pricing_analysis(product)
    return analyze_product_risk(
        net_profit=_to_float(product.get("net_profit")),
        margin_rate=_to_float(product.get("margin_rate")),
        selling_price=_to_float(product.get("selling_price")),
        recommended_price=0,
        quantity=int(inventory.get("quantity") or 0),
        minimum_quantity=int(inventory.get("minimum_quantity") or 0),
    )

def sell_stop_policy_service() -> dict:
    return policy_dict(DEFAULT_SELL_STOP_POLICY)


async def product_analysis_dashboard_service(user_id: str):
    """상품 분석 대시보드 V1: 현재 사용자 상품의 수익성/SELL STOP 요약."""
    products = await list_products_service(user_id)

    total_products = len(products)
    sell_count = sum(1 for p in products if p.get("status") == "SELL")
    stop_count = sum(1 for p in products if p.get("status") == "STOP")
    total_expected_net_profit = round(sum(_to_float(p.get("net_profit")) for p in products), 2)
    average_margin_rate = round(
        sum(_to_float(p.get("margin_rate")) for p in products) / total_products,
        2,
    ) if total_products else 0.0

    counts = {
        "stop_reason_count": 0,
        "sellable_count": 0,
    }
    for product in products:
        counts[_status_reason_key(product)] += 1

    items = [
        {
            "product_id": product.get("id"),
            "name": product.get("name"),
            "sku": product.get("sku"),
            "selling_price": _to_float(product.get("selling_price") or product.get("sale_price")),
            "total_cost": _to_float(product.get("total_cost")),
            "net_profit": _to_float(product.get("net_profit")),
            "margin_rate": _to_float(product.get("margin_rate")),
            "status": product.get("status") or "STOP",
            "status_reason": product.get("status_reason") or "순이익 부족",
            "last_recalculated_at": product.get("last_recalculated_at"),
        }
        for product in products
    ]

    return {
        "summary": {
            "total_products": total_products,
            "sell_count": sell_count,
            "stop_count": stop_count,
            "total_expected_net_profit": total_expected_net_profit,
            "average_margin_rate": average_margin_rate,
            **counts,
        },
        "items": items,
    }


async def recalculate_product_service(user_id: str, product_id: str):
    """가격 재검사 V1: 저장된 상품 입력값 기준으로 계산값과 자동 상태를 재계산합니다."""
    existing_product = await get_product_service(user_id, product_id)
    old_status = existing_product.get("status")

    calculated = calculate_product_profit_fields(dict(existing_product))
    calculated = apply_auto_sell_stop_fields(calculated)
    now_text = _utc_now_text()

    payload = {
        "total_cost": calculated["total_cost"],
        "fee_amount": calculated["fee_amount"],
        "vat_amount": calculated["vat_amount"],
        "net_profit": calculated["net_profit"],
        "margin_rate": calculated["margin_rate"],
        "status": calculated["status"],
        "status_reason": calculated["status_reason"],
        "last_recalculated_at": now_text,
    }

    updated = await update(
        "products",
        {"id": f"eq.{product_id}", "user_id": f"eq.{user_id}"},
        payload,
    )
    if not updated:
        raise HTTPException(status_code=400, detail="product recalculate failed")

    product = updated[0]
    await insert("product_recalculation_history", _recalculation_history_payload(user_id, existing_product, product))
    return _product_recalculation_result(product, old_status)


async def recalculate_all_products_service(user_id: str):
    products = await list_products_service(user_id)
    results = []
    changed_count = 0

    for product in products:
        result = await recalculate_product_service(user_id, product["id"])
        results.append(result)
        if result.get("status_changed"):
            changed_count += 1

    return {
        "total_count": len(products),
        "changed_count": changed_count,
        "results": results,
    }


async def product_recalculation_history_service(user_id: str):
    rows = await select(
        "product_recalculation_history",
        {
            "user_id": f"eq.{user_id}",
            "order": "created_at.desc",
        },
    )
    products = await list_products_service(user_id)
    product_map = {product.get("id"): product for product in products}

    return [
        {
            "id": row.get("id"),
            "product_id": row.get("product_id"),
            "product_name": (product_map.get(row.get("product_id")) or {}).get("name") or "삭제된 상품",
            "old_status": row.get("old_status"),
            "new_status": row.get("new_status"),
            "net_profit": row.get("net_profit"),
            "margin_rate": row.get("margin_rate"),
            "reason": row.get("reason"),
            "created_at": row.get("created_at"),
        }
        for row in rows
    ]
