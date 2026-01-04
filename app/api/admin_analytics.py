from fastapi import APIRouter, Request
from app.core.deps import admin_guard

router = APIRouter()

@router.get("/api/admin/analytics")
async def analytics(request: Request):
    admin_guard(request)
    # TODO: real analytics
    return {"charts": []}
