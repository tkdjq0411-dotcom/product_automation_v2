from fastapi import APIRouter, Depends

from app.modules.auth.service import get_current_user_id
from app.modules.suppliers.schema import SupplierCreate, SupplierUpdate
from app.modules.suppliers.service import create_supplier_service, delete_supplier_service, get_supplier_service, list_suppliers_service, update_supplier_service

router = APIRouter()


@router.get("/", summary="공급처 목록 조회")
async def list_suppliers(user_id: str = Depends(get_current_user_id)):
    return {"ok": True, "suppliers": await list_suppliers_service(user_id)}


@router.get("/{supplier_id}", summary="공급처 상세 조회")
async def get_supplier(supplier_id: str, user_id: str = Depends(get_current_user_id)):
    return {"ok": True, "supplier": await get_supplier_service(user_id, supplier_id)}


@router.post("/", summary="공급처 등록")
async def create_supplier(data: SupplierCreate, user_id: str = Depends(get_current_user_id)):
    return {"ok": True, "supplier": await create_supplier_service(user_id, data.model_dump())}


@router.patch("/{supplier_id}", summary="공급처 수정")
async def update_supplier(supplier_id: str, data: SupplierUpdate, user_id: str = Depends(get_current_user_id)):
    return {"ok": True, "supplier": await update_supplier_service(user_id, supplier_id, data.model_dump())}


@router.delete("/{supplier_id}", summary="공급처 삭제")
async def delete_supplier(supplier_id: str, user_id: str = Depends(get_current_user_id)):
    return {"ok": True, "supplier": await delete_supplier_service(user_id, supplier_id)}
