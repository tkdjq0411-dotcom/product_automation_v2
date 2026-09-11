from fastapi import APIRouter, Depends

from app.modules.auth.service import get_bearer_token, get_current_user_service
from app.modules.dashboard.service import dashboard_overview_service

router = APIRouter()


async def get_dashboard_user_id(token: str = Depends(get_bearer_token)) -> str:
    user = await get_current_user_service(token)
    return user.get("id")


@router.get("/overview", summary="V3 통합 운영 대시보드")
async def dashboard_overview(user_id: str = Depends(get_dashboard_user_id)):
    return {"ok": True, "dashboard": await dashboard_overview_service(user_id)}
