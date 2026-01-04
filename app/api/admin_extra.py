from fastapi import APIRouter, Request
from app.core.deps import admin_guard

router = APIRouter()

# ===== Items 확장 =====
@router.get("/api/admin/items/{item_id}")
async def get_item(item_id: int, request: Request):
    admin_guard(request)
    return {"item": None, "todo": "get item detail"}

@router.post("/api/admin/items/import")
async def import_items(request: Request):
    admin_guard(request)
    return {"ok": True, "todo": "bulk import"}

@router.post("/api/admin/items/validate")
async def validate_item(request: Request):
    admin_guard(request)
    return {"ok": True, "todo": "pre validation"}

# ===== Decision =====
@router.get("/api/admin/decision-logs/{item_id}")
async def decision_by_item(item_id: int, request: Request):
    admin_guard(request)
    return {"logs": []}

@router.get("/api/admin/decision-logs/export")
async def export_decisions(request: Request):
    admin_guard(request)
    return {"ok": True, "todo": "export excel"}

# ===== Stats =====
@router.get("/api/admin/stats/today")
async def stats_today(request: Request):
    admin_guard(request)
    return {"total": 0, "sell": 0, "stop": 0}

@router.get("/api/admin/stats/weekly")
async def stats_weekly(request: Request):
    admin_guard(request)
    return {"chart": []}

@router.get("/api/admin/stats/monthly")
async def stats_monthly(request: Request):
    admin_guard(request)
    return {"chart": []}

# ===== Settings =====
@router.post("/api/admin/settings/reset")
async def reset_settings(request: Request):
    admin_guard(request)
    return {"ok": True}

@router.get("/api/admin/settings/history")
async def settings_history(request: Request):
    admin_guard(request)
    return {"history": []}

# ===== Watch =====
@router.post("/api/admin/watch/add/{item_id}")
async def watch_add(item_id: int, request: Request):
    admin_guard(request)
    return {"ok": True}

@router.post("/api/admin/watch/remove/{item_id}")
async def watch_remove(item_id: int, request: Request):
    admin_guard(request)
    return {"ok": True}

@router.get("/api/admin/watch/list")
async def watch_list(request: Request):
    admin_guard(request)
    return {"items": []}
