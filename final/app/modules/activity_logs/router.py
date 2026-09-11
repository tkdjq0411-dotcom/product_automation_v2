from fastapi import APIRouter, Depends, Query

from app.modules.activity_logs.service import list_activity_logs_service
from app.modules.auth.service import get_bearer_token, get_current_user_service

router = APIRouter()


async def get_log_user_id(token: str = Depends(get_bearer_token)) -> str:
    user = await get_current_user_service(token)
    return user.get("id")


@router.get("/", summary="운영 로그/히스토리 조회")
async def activity_logs(
    category: str | None = Query(default=None, max_length=30),
    limit: int = Query(default=100, ge=1, le=500),
    user_id: str = Depends(get_log_user_id),
):
    logs = await list_activity_logs_service(user_id, category=category, limit=limit)
    return {"ok": True, "logs": logs, "count": len(logs)}
