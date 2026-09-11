from fastapi import APIRouter, Depends

from app.modules.auth.service import get_bearer_token, get_current_user_service
from app.modules.inventory.schema import InventoryInCreate, InventoryMinimumUpdate, InventoryOutCreate
from app.modules.inventory.service import (
    decrease_inventory_service,
    get_inventory_service,
    increase_inventory_service,
    inventory_summary_service,
    list_inventory_history_service,
    list_inventory_service,
    low_inventory_service,
    update_minimum_inventory_service,
)

router = APIRouter()


async def get_inventory_user_id(token: str = Depends(get_bearer_token)) -> str:
    user = await get_current_user_service(token)
    return user.get("id")


@router.get("/", summary="현재 재고 조회")
async def list_inventory(user_id: str = Depends(get_inventory_user_id)):
    inventory = await list_inventory_service(user_id)
    return {"ok": True, "inventory": inventory}


@router.post("/in", summary="입고 등록")
async def inventory_in(data: InventoryInCreate, user_id: str = Depends(get_inventory_user_id)):
    inventory = await increase_inventory_service(user_id, data.product_id, data.quantity)
    return {"ok": True, "inventory": inventory}


@router.post("/out", summary="출고 등록")
async def inventory_out(data: InventoryOutCreate, user_id: str = Depends(get_inventory_user_id)):
    inventory = await decrease_inventory_service(user_id, data.product_id, data.quantity)
    return {"ok": True, "inventory": inventory}


@router.get("/history", summary="입출고 이력 조회")
async def inventory_history(user_id: str = Depends(get_inventory_user_id)):
    history = await list_inventory_history_service(user_id)
    return {"ok": True, "history": history}


@router.get("/summary", summary="재고 요약")
async def inventory_summary(user_id: str = Depends(get_inventory_user_id)):
    return {"ok": True, "summary": await inventory_summary_service(user_id)}


@router.get("/low-stock", summary="부족재고 조회")
async def low_inventory(user_id: str = Depends(get_inventory_user_id)):
    rows = await low_inventory_service(user_id)
    return {"ok": True, "inventory": rows, "count": len(rows)}


@router.get("/{product_id}", summary="상품별 재고 상세")
async def inventory_detail(product_id: str, user_id: str = Depends(get_inventory_user_id)):
    return {"ok": True, "inventory": await get_inventory_service(user_id, product_id)}


@router.patch("/{product_id}/minimum", summary="최소재고 설정")
async def inventory_minimum(product_id: str, data: InventoryMinimumUpdate, user_id: str = Depends(get_inventory_user_id)):
    inventory = await update_minimum_inventory_service(user_id, product_id, data.minimum_quantity)
    return {"ok": True, "inventory": inventory}
