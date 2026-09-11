from fastapi import APIRouter, Depends
from app.modules.auth.service import get_bearer_token, require_admin_service
from app.modules.admin.service import admin_overview_service, admin_users_service

router=APIRouter()

async def require_admin(token: str=Depends(get_bearer_token)):
    return await require_admin_service(token)

@router.get("/overview", summary="관리자 운영 현황")
async def overview(admin=Depends(require_admin)):
    return {"ok":True,"overview":await admin_overview_service()}

@router.get("/users", summary="관리자 사용자 목록")
async def users(admin=Depends(require_admin)):
    rows=await admin_users_service()
    return {"ok":True,"users":rows,"count":len(rows)}
