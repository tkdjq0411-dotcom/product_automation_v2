from fastapi import APIRouter, Request
from app.core.deps import admin_guard
from app.api.admin_items import _FAKE_ITEMS

router = APIRouter()

@router.get("/api/admin/stats")
async def stats(request: Request):
    admin_guard(request)
    total = len(_FAKE_ITEMS)
    sell = sum(1 for x in _FAKE_ITEMS if x.get("decision") == "SELL")
    stop = sum(1 for x in _FAKE_ITEMS if x.get("decision") == "STOP")
    avg_margin = (sum(float(x.get("margin_rate") or 0) for x in _FAKE_ITEMS) / total) if total else 0.0
    return {"total": total, "sell": sell, "stop": stop, "avg_margin_rate": avg_margin}

@router.get("/api/admin/recent-decisions")
async def recent(request: Request):
    admin_guard(request)
    return {"items": list(reversed(_FAKE_ITEMS))[:20]}
