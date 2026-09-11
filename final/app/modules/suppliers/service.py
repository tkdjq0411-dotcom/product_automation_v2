from fastapi import HTTPException

from app.modules.activity_logs.service import create_activity_log
from app.db.supabase import delete, insert, select, update


def _normalize_name(value: str) -> str:
    return str(value or "").strip()


async def list_suppliers_service(user_id: str):
    return await select("suppliers", {"user_id": f"eq.{user_id}", "order": "created_at.desc"})


async def get_supplier_service(user_id: str, supplier_id: str):
    rows = await select("suppliers", {"id": f"eq.{supplier_id}", "user_id": f"eq.{user_id}", "limit": "1"})
    if not rows:
        raise HTTPException(status_code=404, detail="supplier not found")
    return rows[0]


async def _ensure_unique_name(user_id: str, name: str, exclude_supplier_id: str | None = None) -> None:
    normalized = _normalize_name(name).casefold()
    suppliers = await list_suppliers_service(user_id)
    for supplier in suppliers:
        if supplier.get("id") == exclude_supplier_id:
            continue
        if _normalize_name(supplier.get("name")).casefold() == normalized:
            raise HTTPException(status_code=400, detail="supplier name already exists")


async def create_supplier_service(user_id: str, data: dict):
    name = _normalize_name(data.get("name"))
    await _ensure_unique_name(user_id, name)
    payload = {**data, "name": name, "user_id": user_id}
    created = await insert("suppliers", payload)
    if not created:
        raise HTTPException(status_code=400, detail="supplier create failed")
    supplier = created[0]
    await create_activity_log(user_id, "SUPPLIER", "CREATE", "supplier", supplier.get("id"), supplier.get("name"), "공급처 등록")
    return supplier


async def update_supplier_service(user_id: str, supplier_id: str, data: dict):
    await get_supplier_service(user_id, supplier_id)
    payload = {key: value for key, value in data.items() if value is not None}
    if not payload:
        raise HTTPException(status_code=400, detail="no supplier fields to update")
    if "name" in payload:
        payload["name"] = _normalize_name(payload["name"])
        await _ensure_unique_name(user_id, payload["name"], exclude_supplier_id=supplier_id)
    updated = await update("suppliers", {"id": f"eq.{supplier_id}", "user_id": f"eq.{user_id}"}, payload)
    if not updated:
        raise HTTPException(status_code=400, detail="supplier update failed")
    supplier = updated[0]
    await create_activity_log(user_id, "SUPPLIER", "UPDATE", "supplier", supplier.get("id"), supplier.get("name"), "공급처 수정")
    return supplier


async def delete_supplier_service(user_id: str, supplier_id: str):
    supplier = await get_supplier_service(user_id, supplier_id)
    linked_products = await select("products", {"user_id": f"eq.{user_id}", "supplier_id": f"eq.{supplier_id}", "limit": "1"})
    if linked_products:
        raise HTTPException(status_code=409, detail="supplier is linked to a product")
    deleted = await delete("suppliers", {"id": f"eq.{supplier_id}", "user_id": f"eq.{user_id}"})
    if not deleted:
        raise HTTPException(status_code=400, detail="supplier delete failed")
    await create_activity_log(user_id, "SUPPLIER", "DELETE", "supplier", supplier_id, supplier.get("name"), "공급처 삭제")
    return supplier
