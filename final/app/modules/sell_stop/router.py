from fastapi import APIRouter, Depends

from app.modules.auth.service import get_current_user_id
from app.modules.sell_stop.schema import SellStopCreate
from app.modules.sell_stop.service import (
    create_sell_stop_result_service,
    get_sell_stop_result_service,
    list_sell_stop_results_service,
)

router = APIRouter()


@router.get("/", summary="판매판단 목록 조회")
async def list_sell_stop_results(user_id: str = Depends(get_current_user_id)):
    return await list_sell_stop_results_service(user_id)


@router.get("/{result_id}", summary="판매판단 상세 조회")
async def get_sell_stop_result(result_id: str, user_id: str = Depends(get_current_user_id)):
    return await get_sell_stop_result_service(user_id, result_id)


@router.post("/", summary="판매판단 등록")
async def create_sell_stop_result(data: SellStopCreate, user_id: str = Depends(get_current_user_id)):
    result = await create_sell_stop_result_service(user_id, data.model_dump())
    return {"ok": True, "result": result}
