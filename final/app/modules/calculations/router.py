from fastapi import APIRouter, Depends

from app.modules.auth.service import get_current_user_id
from app.modules.calculations.schema import CalculationCreate
from app.modules.calculations.service import (
    create_calculation_service,
    get_calculation_service,
    list_calculations_service,
)

router = APIRouter()


@router.get("/", summary="계산 목록 조회")
async def list_calculations(user_id: str = Depends(get_current_user_id)):
    return await list_calculations_service(user_id)


@router.get("/{calculation_id}", summary="계산 상세 조회")
async def get_calculation(calculation_id: str, user_id: str = Depends(get_current_user_id)):
    return await get_calculation_service(user_id, calculation_id)


@router.post("/", summary="계산 등록")
async def create_calculation(data: CalculationCreate, user_id: str = Depends(get_current_user_id)):
    result = await create_calculation_service(user_id, data.model_dump())
    return {"ok": True, "result": result}
