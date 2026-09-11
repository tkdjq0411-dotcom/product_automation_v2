from datetime import datetime
from uuid import uuid4

from app.db.supabase import insert, select


async def create_activity_log(
    user_id: str,
    category: str,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    entity_name: str | None = None,
    detail: str | None = None,
):
    rows = await insert("activity_logs", {
        "id": str(uuid4()),
        "user_id": user_id,
        "category": category,
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "entity_name": entity_name,
        "detail": detail,
        "created_at": datetime.now().isoformat(timespec="microseconds"),
    })
    return rows[0] if rows else None


async def list_activity_logs_service(user_id: str, category: str | None = None, limit: int = 100):
    params = {"user_id": f"eq.{user_id}", "order": "created_at.desc", "limit": str(min(max(limit, 1), 500))}
    if category:
        params["category"] = f"eq.{category}"
    return await select("activity_logs", params)
