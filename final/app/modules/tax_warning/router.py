from fastapi import APIRouter, Depends

from app.modules.auth.service import get_current_user_id
from app.modules.tax_warning.schema import GeneralRecalculation, TaxWarningConfirm
from app.modules.tax_warning.service import (
    confirm_tax_warning_service,
    get_tax_warning_status_service,
    recalculate_general_service,
)

router = APIRouter()


@router.get("/status", summary="과세 경고 상태 조회")
async def get_tax_warning_status(user_id: str = Depends(get_current_user_id)):
    result = await get_tax_warning_status_service(user_id)
    return {"ok": True, "result": result}


@router.post("/confirm", summary="과세 경고 확인")
async def confirm_tax_warning(
    data: TaxWarningConfirm,
    user_id: str = Depends(get_current_user_id),
):
    result = await confirm_tax_warning_service(user_id, data.confirmed)
    return {"ok": True, "result": result}


@router.post("/recalculate-general", summary="일반과세 재계산")
async def recalculate_general(data: GeneralRecalculation, user_id: str = Depends(get_current_user_id)):
    payload = data.model_dump()
    payload["user_id"] = user_id
    result = await recalculate_general_service(payload)
    return {"ok": True, "result": result}
