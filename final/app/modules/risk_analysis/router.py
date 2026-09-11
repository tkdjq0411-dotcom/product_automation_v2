from fastapi import APIRouter, Depends
from app.modules.auth.service import get_bearer_token, get_current_user_service
from app.modules.risk_analysis.service import list_risks_service, product_risk_service, risk_summary_service

router = APIRouter()

async def current_user_id(token: str = Depends(get_bearer_token)):
    user = await get_current_user_service(token)
    return user.get("id")

@router.get("/", summary="전체 상품 리스크 분석")
async def list_risks(user_id: str = Depends(current_user_id)):
    rows = await list_risks_service(user_id)
    return {"ok": True, "risks": rows, "count": len(rows)}

@router.get("/summary", summary="리스크 요약")
async def risk_summary(user_id: str = Depends(current_user_id)):
    return {"ok": True, "summary": await risk_summary_service(user_id)}

@router.get("/{product_id}", summary="상품별 리스크 분석")
async def product_risk(product_id: str, user_id: str = Depends(current_user_id)):
    return {"ok": True, "risk": await product_risk_service(user_id, product_id)}
