from fastapi import APIRouter, Request
from app.core.deps import admin_guard

router = APIRouter()

@router.get("/api/admin/fees")
async def list_fees(request: Request):
    admin_guard(request)
    return []

@router.post("/api/admin/fees")
async def upsert_fee(request: Request):
    admin_guard(request)
    # TODO: fee_rules insert/update
    return {"ok": True}
