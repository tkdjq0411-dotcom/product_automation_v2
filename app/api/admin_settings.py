from fastapi import APIRouter, Request
from app.core.deps import admin_guard
from app.core.constants import DEFAULT_MIN_PROFIT, DEFAULT_BUFFER_RATE

router = APIRouter()

# 틀용 더미 설정
_FAKE_SETTINGS = {"min_profit": DEFAULT_MIN_PROFIT, "safety_buffer_rate": DEFAULT_BUFFER_RATE}

@router.get("/api/admin/settings")
async def get_settings(request: Request):
    admin_guard(request)
    return _FAKE_SETTINGS

@router.post("/api/admin/settings")
async def update_settings(request: Request):
    admin_guard(request)
    body = await request.json()
    if "min_profit" in body:
        _FAKE_SETTINGS["min_profit"] = int(body["min_profit"])
    if "safety_buffer_rate" in body:
        _FAKE_SETTINGS["safety_buffer_rate"] = float(body["safety_buffer_rate"])
    return {"ok": True, "settings": _FAKE_SETTINGS}
