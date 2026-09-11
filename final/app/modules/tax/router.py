from fastapi import APIRouter, Depends
from app.modules.auth.service import get_current_user_id
from app.modules.tax.service import tax_summary_service, product_tax_summary_service

router = APIRouter()

@router.get("/summary", summary="V4 세금 계산 요약")
async def tax_summary(user_id: str = Depends(get_current_user_id)):
    return {"ok": True, "tax": await tax_summary_service(user_id)}

@router.get("/products/{product_id}", summary="상품별 세금 계산 요약")
async def product_tax_summary(product_id: str, user_id: str = Depends(get_current_user_id)):
    return {"ok": True, "tax": await product_tax_summary_service(user_id, product_id)}
