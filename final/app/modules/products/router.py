from fastapi import APIRouter, Depends, Query

from app.modules.auth.service import get_bearer_token, get_current_user_service
from app.modules.products.schema import ProductCreate, ProductUpdate
from app.modules.products.service import (
    all_product_pricing_analysis_service,
    create_product_service,
    delete_product_service,
    get_product_service,
    list_products_service,
    product_analysis_dashboard_service,
    product_pricing_analysis_service,
    product_recalculation_history_service,
    recalculate_all_products_service,
    recalculate_product_service,
    sell_stop_policy_service,
    update_product_service,
)

router = APIRouter()


async def get_product_user_id(token: str = Depends(get_bearer_token)) -> str:
    user = await get_current_user_service(token)
    return user.get("id")


@router.get("/", summary="상품 검색 / 필터 / 정렬")
async def list_products(
    sku: str | None = Query(default=None, max_length=100, description="SKU 검색"),
    q: str | None = Query(default=None, max_length=200, description="상품명 또는 SKU 통합 검색"),
    status: str | None = Query(default=None, max_length=10, description="SELL/STOP"),
    supplier_id: str | None = Query(default=None, max_length=100, description="공급처 ID"),
    min_selling_price: float | None = Query(default=None, allow_inf_nan=False),
    max_selling_price: float | None = Query(default=None, allow_inf_nan=False),
    min_net_profit: float | None = Query(default=None, allow_inf_nan=False),
    max_net_profit: float | None = Query(default=None, allow_inf_nan=False),
    min_margin_rate: float | None = Query(default=None, allow_inf_nan=False),
    max_margin_rate: float | None = Query(default=None, allow_inf_nan=False),
    sort_by: str = Query(default="created", max_length=30),
    sort_dir: str = Query(default="desc", max_length=4),
    user_id: str = Depends(get_product_user_id),
):
    products = await list_products_service(
        user_id, sku=sku, q=q, status=status, supplier_id=supplier_id,
        min_selling_price=min_selling_price, max_selling_price=max_selling_price,
        min_net_profit=min_net_profit, max_net_profit=max_net_profit,
        min_margin_rate=min_margin_rate, max_margin_rate=max_margin_rate,
        sort_by=sort_by, sort_dir=sort_dir,
    )
    return {"ok": True, "products": products, "count": len(products)}


@router.get("/analysis/dashboard", summary="상품 분석 대시보드")
async def product_analysis_dashboard(user_id: str = Depends(get_product_user_id)):
    dashboard = await product_analysis_dashboard_service(user_id)

    return {
        "ok": True,
        **dashboard,
    }



@router.get("/analysis/pricing", summary="전체 상품 최저 판매 가능가")
async def all_product_pricing(user_id: str = Depends(get_product_user_id)):
    rows = await all_product_pricing_analysis_service(user_id)
    return {"ok": True, "pricing": rows, "count": len(rows)}


@router.get("/analysis/policy", summary="SELL/STOP 판정 기준")
async def sell_stop_policy(user_id: str = Depends(get_product_user_id)):
    return {
        "ok": True,
        "policy": sell_stop_policy_service(),
    }




@router.get("/recalculate/history", summary="재계산 이력 조회")
async def product_recalculation_history(user_id: str = Depends(get_product_user_id)):
    history = await product_recalculation_history_service(user_id)

    return {
        "ok": True,
        "history": history,
    }


@router.post("/recalculate-all", summary="전체 상품 일괄 재계산")
async def recalculate_all_products(user_id: str = Depends(get_product_user_id)):
    result = await recalculate_all_products_service(user_id)

    return {
        "ok": True,
        **result,
    }


@router.post("/{product_id}/recalculate", summary="상품별 재계산")
async def recalculate_product(product_id: str, user_id: str = Depends(get_product_user_id)):
    result = await recalculate_product_service(user_id, product_id)

    return {
        "ok": True,
        "result": result,
    }


@router.get("/{product_id}/pricing", summary="상품별 최저 판매 가능가")
async def product_pricing(product_id: str, user_id: str = Depends(get_product_user_id)):
    result = await product_pricing_analysis_service(user_id, product_id)
    return {"ok": True, **result}


@router.get("/{product_id}", summary="상품 상세 조회")
async def get_product(product_id: str, user_id: str = Depends(get_product_user_id)):
    product = await get_product_service(user_id, product_id)

    return {
        "ok": True,
        "product": product,
    }


@router.post("/", summary="상품 등록")
async def create_product(data: ProductCreate, user_id: str = Depends(get_product_user_id)):
    product = await create_product_service(user_id, data.model_dump())

    return {
        "ok": True,
        "product": product,
    }


@router.patch("/{product_id}", summary="상품 수정")
async def update_product(
    product_id: str,
    data: ProductUpdate,
    user_id: str = Depends(get_product_user_id),
):
    product = await update_product_service(
        user_id,
        product_id,
        data.model_dump(exclude_unset=True),
    )

    return {
        "ok": True,
        "product": product,
    }


@router.delete("/{product_id}", summary="상품 삭제")
async def delete_product(product_id: str, user_id: str = Depends(get_product_user_id)):
    product = await delete_product_service(user_id, product_id)

    return {
        "ok": True,
        "product": product,
    }
