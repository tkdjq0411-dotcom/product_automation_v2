from fastapi import APIRouter, Depends

from app.modules.operations_common import current_user_id
from app.modules.tax_reserve.schema import TaxReserveSettings
from app.modules.tax_reserve.service import reserve_summary, save_settings

router = APIRouter()


@router.get("/summary", summary="세금 적립금과 사용 가능 순이익")
async def summary(user_id: str = Depends(current_user_id)):
    return {"ok": True, "reserve": await reserve_summary(user_id)}


@router.patch("/settings", summary="세금 안전 적립률 설정")
async def settings(data: TaxReserveSettings, user_id: str = Depends(current_user_id)):
    await save_settings(user_id, data.model_dump())
    return {"ok": True, "reserve": await reserve_summary(user_id)}
