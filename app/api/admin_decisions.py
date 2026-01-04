from fastapi import APIRouter, Request
from app.core.deps import admin_guard

router = APIRouter()

@router.get("/api/admin/decisions")
async def decision_logs(request: Request):
    admin_guard(request)
    return []
