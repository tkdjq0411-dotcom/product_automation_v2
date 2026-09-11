from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.modules.auth.service import get_bearer_token, get_current_user_service, require_admin_service
from app.modules.plans.service import PLAN_LIMITS, usage_service, set_user_plan_service
router=APIRouter()
class PlanUpdate(BaseModel): plan:str
async def current(token:str=Depends(get_bearer_token)): return await get_current_user_service(token)
@router.get("/catalog",summary="요금제 목록")
async def catalog(user=Depends(current)): return {"ok":True,"plans":PLAN_LIMITS}
@router.get("/me",summary="내 요금제/사용량")
async def me(user=Depends(current)): return {"ok":True,**await usage_service(user["id"])}
@router.patch("/admin/users/{user_id}",summary="관리자 사용자 요금제 변경")
async def change(user_id:str,data:PlanUpdate,token:str=Depends(get_bearer_token)):
    await require_admin_service(token)
    return {"ok":True,"user":await set_user_plan_service(user_id,data.plan),"usage":await usage_service(user_id)}
