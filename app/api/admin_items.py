from fastapi import APIRouter, Request
from app.core.deps import admin_guard

router = APIRouter()

# ✅ 틀용 더미 저장소 (서버 재시작하면 초기화됨)
_FAKE_ITEMS = []
_NEXT_ID = 1

@router.get("/api/admin/items")
async def list_items(request: Request):
    admin_guard(request)
    return {"items": list(reversed(_FAKE_ITEMS))}

@router.post("/api/admin/items")
async def create_item(request: Request):
    admin_guard(request)
    global _NEXT_ID

    body = await request.json()
    item = {
        "id": _NEXT_ID,
        "name": body.get("name", "unknown"),
        "market": body.get("market", "unknown"),
        "category": body.get("category", "unknown"),
        "tax_type": body.get("tax_type", "simple"),
        "buy_price": body.get("buy_price", 0),
        "sell_price": body.get("sell_price", 0),
        "shipping_fee": body.get("shipping_fee", 0),
        "decision": "STOP",
        "profit": 0,
        "margin_rate": 0.0,
        "reason": "TODO: calc + supabase insert",
        "execution_status": "NOT_LISTED",
    }
    _FAKE_ITEMS.append(item)
    _NEXT_ID += 1
    return {"item": item}

@router.patch("/api/admin/items/{item_id}")
async def patch_item(item_id: int, request: Request):
    admin_guard(request)
    body = await request.json()

    for it in _FAKE_ITEMS:
        if it["id"] == item_id:
            it.update({k: v for k, v in body.items() if v is not None})
            it["reason"] = "TODO: patch + recalc + supabase update"
            return {"item": it}
    return {"detail": "not found"}

@router.delete("/api/admin/items/{item_id}")
async def delete_item(item_id: int, request: Request):
    admin_guard(request)
    global _FAKE_ITEMS
    before = len(_FAKE_ITEMS)
    _FAKE_ITEMS = [x for x in _FAKE_ITEMS if x["id"] != item_id]
    return {"ok": len(_FAKE_ITEMS) != before}
