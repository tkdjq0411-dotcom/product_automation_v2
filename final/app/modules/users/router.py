from fastapi import APIRouter, Depends

from app.modules.auth.service import get_bearer_token, get_current_user_id, get_current_user_service
from app.modules.users.schema import TaxTypeUpdate
from app.modules.users.service import get_user_me_service, update_tax_type_service

router = APIRouter()


@router.get("/me", summary="내 정보 조회")
async def get_me(token: str = Depends(get_bearer_token)):
    user = await get_current_user_service(token)
    return await get_user_me_service(user)


@router.patch("/tax-type", summary="과세 유형 변경")
async def update_tax_type(data: TaxTypeUpdate, user_id: str = Depends(get_current_user_id)):
    result = await update_tax_type_service(user_id, data.tax_type)
    return {"ok": True, "result": result}
