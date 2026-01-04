from fastapi import APIRouter, Request
from app.core.deps import admin_guard

router = APIRouter()

@router.get("/api/admin/codes")
async def list_codes(request: Request):
    admin_guard(request)
    return []

@router.post("/api/admin/codes")
async def create_code(request: Request):
    admin_guard(request)
    # TODO: generate new code
    return {"ok": True}
