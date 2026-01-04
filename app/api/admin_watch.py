from fastapi import APIRouter, Request
from app.core.deps import admin_guard

router = APIRouter()

@router.post("/api/admin/recheck/{item_id}")
async def recheck_one(item_id: int, request: Request):
    admin_guard(request)
    # TODO: re-calc one
    return {"ok": True, "item_id": item_id}

@router.post("/api/admin/recheck/all")
async def recheck_all(request: Request):
    admin_guard(request)
    # TODO: re-calc all
    return {"ok": True}
