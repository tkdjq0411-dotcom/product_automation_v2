from datetime import datetime
from uuid import uuid4

from fastapi import HTTPException

from app.modules.activity_logs.service import create_activity_log
from app.db.supabase import insert, select, update
from app.modules.products.service import get_product_service, list_products_service


def _status(quantity: int, minimum_quantity: int) -> str:
    return "LOW" if quantity <= minimum_quantity else "OK"


def _to_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


async def _get_inventory_row(user_id: str, product_id: str):
    rows = await select(
        "inventory",
        {
            "user_id": f"eq.{user_id}",
            "product_id": f"eq.{product_id}",
            "limit": "1",
        },
    )
    return rows[0] if rows else None


async def _ensure_inventory_row(user_id: str, product_id: str):
    await get_product_service(user_id, product_id)
    row = await _get_inventory_row(user_id, product_id)
    if row:
        return row

    created = await insert(
        "inventory",
        {
            "id": str(uuid4()),
            "user_id": user_id,
            "product_id": product_id,
            "quantity": 0,
            "minimum_quantity": 0,
        },
    )
    if not created:
        raise HTTPException(status_code=400, detail="inventory create failed")
    return created[0]


async def list_inventory_service(user_id: str):
    products = await list_products_service(user_id)
    rows = await select("inventory", {"user_id": f"eq.{user_id}", "order": "created_at.desc"})
    by_product = {row.get("product_id"): row for row in rows}

    result = []
    for product in products:
        product_id = product.get("id")
        row = by_product.get(product_id)
        quantity = _to_int(row.get("quantity") if row else 0)
        minimum_quantity = _to_int(row.get("minimum_quantity") if row else 0)
        result.append(
            {
                "product": product,
                "product_id": product_id,
                "quantity": quantity,
                "minimum_quantity": minimum_quantity,
                "status": _status(quantity, minimum_quantity),
            }
        )
    return result


async def _create_inventory_history(user_id: str, product_id: str, history_type: str, quantity: int):
    history = await insert(
        "inventory_history",
        {
            "id": str(uuid4()),
            "user_id": user_id,
            "product_id": product_id,
            "type": history_type,
            "quantity": quantity,
            "created_at": datetime.now().isoformat(timespec="microseconds"),
        },
    )
    if not history:
        raise HTTPException(status_code=400, detail="inventory history create failed")
    return history[0]


async def increase_inventory_service(user_id: str, product_id: str, quantity: int):
    if quantity <= 0:
        raise HTTPException(status_code=400, detail="quantity must be positive")

    row = await _ensure_inventory_row(user_id, product_id)
    next_quantity = _to_int(row.get("quantity")) + quantity

    updated = await update(
        "inventory",
        {"id": f"eq.{row['id']}", "user_id": f"eq.{user_id}"},
        {"quantity": next_quantity},
    )
    if not updated:
        raise HTTPException(status_code=400, detail="inventory update failed")
    await _create_inventory_history(user_id, product_id, "IN", quantity)
    product = await get_product_service(user_id, product_id)
    await create_activity_log(user_id, "INVENTORY", "IN", "product", product_id, product.get("name"),
                              f"입고 {quantity}개 · 현재재고 {next_quantity}개")
    return _format_inventory_row(updated[0])


async def decrease_inventory_service(user_id: str, product_id: str, quantity: int):
    if quantity <= 0:
        raise HTTPException(status_code=400, detail="quantity must be positive")

    row = await _ensure_inventory_row(user_id, product_id)
    current_quantity = _to_int(row.get("quantity"))
    next_quantity = current_quantity - quantity
    if next_quantity < 0:
        raise HTTPException(status_code=400, detail="inventory cannot be negative")

    updated = await update(
        "inventory",
        {"id": f"eq.{row['id']}", "user_id": f"eq.{user_id}"},
        {"quantity": next_quantity},
    )
    if not updated:
        raise HTTPException(status_code=400, detail="inventory update failed")
    await _create_inventory_history(user_id, product_id, "OUT", quantity)
    product = await get_product_service(user_id, product_id)
    await create_activity_log(user_id, "INVENTORY", "OUT", "product", product_id, product.get("name"),
                              f"출고 {quantity}개 · 현재재고 {next_quantity}개")
    return _format_inventory_row(updated[0])


async def update_minimum_inventory_service(user_id: str, product_id: str, minimum_quantity: int):
    if minimum_quantity < 0:
        raise HTTPException(status_code=400, detail="minimum_quantity must be zero or positive")

    row = await _ensure_inventory_row(user_id, product_id)
    updated = await update(
        "inventory",
        {"id": f"eq.{row['id']}", "user_id": f"eq.{user_id}"},
        {"minimum_quantity": minimum_quantity},
    )
    product = await get_product_service(user_id, product_id)
    await create_activity_log(user_id, "INVENTORY", "MINIMUM", "product", product_id, product.get("name"),
                              f"최소재고 {minimum_quantity}개 설정")
    return _format_inventory_row(updated[0])


async def list_inventory_history_service(user_id: str):
    histories = await select(
        "inventory_history",
        {"user_id": f"eq.{user_id}", "order": "created_at.desc"},
    )
    products = await list_products_service(user_id)
    products_by_id = {product.get("id"): product for product in products}

    result = []
    for item in histories:
        product = products_by_id.get(item.get("product_id"))
        result.append(
            {
                "product": product,
                "product_id": item.get("product_id"),
                "product_name": product.get("name") if product else None,
                "type": item.get("type"),
                "quantity": _to_int(item.get("quantity")),
                "created_at": item.get("created_at"),
            }
        )
    return result


def _format_inventory_row(row: dict):
    quantity = _to_int(row.get("quantity"))
    minimum_quantity = _to_int(row.get("minimum_quantity"))
    return {
        **row,
        "quantity": quantity,
        "minimum_quantity": minimum_quantity,
        "status": _status(quantity, minimum_quantity),
    }


async def get_inventory_service(user_id: str, product_id: str):
    product = await get_product_service(user_id, product_id)
    row = await _get_inventory_row(user_id, product_id)
    quantity = _to_int(row.get("quantity") if row else 0)
    minimum_quantity = _to_int(row.get("minimum_quantity") if row else 0)
    return {
        "product": product,
        "product_id": product_id,
        "quantity": quantity,
        "minimum_quantity": minimum_quantity,
        "status": _status(quantity, minimum_quantity),
    }


async def low_inventory_service(user_id: str):
    rows = await list_inventory_service(user_id)
    return [row for row in rows if row.get("status") == "LOW"]


async def inventory_summary_service(user_id: str):
    rows = await list_inventory_service(user_id)
    total_quantity = sum(_to_int(row.get("quantity")) for row in rows)
    low_rows = [row for row in rows if row.get("status") == "LOW"]
    out_of_stock = [row for row in rows if _to_int(row.get("quantity")) == 0]
    return {
        "total_products": len(rows),
        "total_quantity": total_quantity,
        "low_stock_count": len(low_rows),
        "out_of_stock_count": len(out_of_stock),
        "ok_stock_count": len(rows) - len(low_rows),
    }
