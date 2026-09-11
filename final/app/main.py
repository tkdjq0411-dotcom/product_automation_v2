from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.modules.auth.router import router as auth_router
from app.modules.admin.router import router as admin_router
from app.modules.activity_logs.router import router as activity_logs_router
from app.modules.calculations.router import router as calculations_router
from app.modules.dashboard.router import router as dashboard_router
from app.modules.products.router import router as products_router
from app.modules.plans.router import router as plans_router
from app.modules.bulk_products.router import router as bulk_products_router
from app.modules.risk_analysis.router import router as risk_analysis_router
from app.modules.sell_stop.router import router as sell_stop_router
from app.modules.suppliers.router import router as suppliers_router
from app.modules.tax_warning.router import router as tax_warning_router
from app.modules.tax.router import router as tax_router
from app.modules.users.router import router as users_router
from app.modules.sourcing.router import router as sourcing_router
from app.modules.orders.router import router as orders_router
from app.modules.purchases.router import router as purchases_router
from app.modules.shipping.router import router as shipping_router
from app.modules.price_tracking.router import router as price_tracking_router
from app.modules.ai_content.router import router as ai_content_router
from app.modules.automation.router import router as automation_router
from app.modules.integrations.router import router as integrations_router
from app.modules.reports.router import router as reports_router
from app.modules.tax_reserve.router import router as tax_reserve_router
from app.modules.after_sales.router import router as after_sales_router

app = FastAPI(
    title="B2B SaaS V1 API 문서",
    docs_url=None,
    redoc_url=None,
)


@app.middleware("http")
async def no_cache_web_assets(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/web"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

app.include_router(auth_router, prefix="/auth", tags=["인증"])
app.include_router(admin_router, prefix="/admin", tags=["관리자"])
app.include_router(activity_logs_router, prefix="/activity-logs", tags=["로그/히스토리"])
app.include_router(users_router, prefix="/users", tags=["사용자"])
app.include_router(suppliers_router, prefix="/suppliers", tags=["공급처"])
app.include_router(products_router, prefix="/products", tags=["상품관리"])
app.include_router(plans_router, prefix="/plans", tags=["요금제/사용량"])
app.include_router(bulk_products_router, prefix="/bulk-products", tags=["상품 대량처리"])
app.include_router(risk_analysis_router, prefix="/risk-analysis", tags=["리스크분석"])
app.include_router(dashboard_router, prefix="/dashboard", tags=["대시보드"])
app.include_router(calculations_router, prefix="/calculations", tags=["계산"])
app.include_router(sell_stop_router, prefix="/sell-stop", tags=["판매판단"])
app.include_router(tax_warning_router, prefix="/tax-warning", tags=["과세경고"])
app.include_router(tax_router, prefix="/tax", tags=["세금관리"])
app.include_router(sourcing_router, prefix="/sourcing", tags=["상품소싱"])
app.include_router(orders_router, prefix="/orders", tags=["주문"])
app.include_router(purchases_router, prefix="/purchases", tags=["발주"])
app.include_router(shipping_router, prefix="/shipping", tags=["배송"])
app.include_router(price_tracking_router, prefix="/price-tracking", tags=["가격추적"])
app.include_router(ai_content_router, prefix="/ai-content", tags=["AI상품초안"])
app.include_router(automation_router, prefix="/automation", tags=["가격자동화"])
app.include_router(integrations_router, prefix="/integrations", tags=["판매채널연결"])
app.include_router(reports_router, prefix="/reports", tags=["운영리포트"])
app.include_router(tax_reserve_router, prefix="/tax-reserve", tags=["세금적립/실사용이익"])
app.include_router(after_sales_router, prefix="/after-sales", tags=["취소/반품/교환"])


SWAGGER_KOREAN_SCRIPT = """
<script>
(function () {
  const replacements = new Map([
    ["Parameters", "매개변수"],
    ["No parameters", "매개변수 없음"],
    ["Request body", "요청 데이터"],
    ["required", "필수"],
    ["Example Value", "예시 값"],
    ["Schema", "구조"],
    ["Responses", "응답"],
    ["Code", "상태 코드"],
    ["Description", "설명"],
    ["Successful Response", "정상 응답"],
    ["Validation Error", "입력값 오류"],
    ["Media type", "데이터 형식"],
    ["Controls Accept header", "응답 형식 선택"],
    ["Links", "링크"],
    ["No links", "링크 없음"],
    ["detail", "상세 내용"],
    ["loc", "위치"],
    ["msg", "오류 메시지"],
    ["type", "오류 종류"]
  ]);

  function translateTextNode(node) {
    const text = node.nodeValue;
    const trimmed = text.trim();
    if (!trimmed) return;
    if (replacements.has(trimmed)) {
      node.nodeValue = text.replace(trimmed, replacements.get(trimmed));
    }
  }

  function translateElement(root) {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    nodes.forEach(translateTextNode);

    document.querySelectorAll('[title], [aria-label]').forEach(function (el) {
      ['title', 'aria-label'].forEach(function (attr) {
        const value = el.getAttribute(attr);
        if (replacements.has(value)) el.setAttribute(attr, replacements.get(value));
      });
    });
  }

  function run() {
    translateElement(document.body);
  }

  const observer = new MutationObserver(run);
  observer.observe(document.body, { childList: true, subtree: true });
  window.addEventListener('load', function () {
    run();
    setTimeout(run, 500);
    setTimeout(run, 1500);
  });
})();
</script>
"""


@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    html = get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title="B2B SaaS V1 API 문서",
        swagger_ui_parameters={
            "defaultModelsExpandDepth": -1,
            "docExpansion": "list",
        },
    )
    body = html.body.decode("utf-8").replace("</body>", SWAGGER_KOREAN_SCRIPT + "</body>")
    return HTMLResponse(body)


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title="B2B SaaS V1 API 문서",
        version="1.0.0",
        description="B2B SaaS V1 API 명세서입니다.",
        routes=app.routes,
    )

    validation_error_schema = openapi_schema.get("components", {}).get("schemas", {}).get("ValidationError")
    if validation_error_schema:
        validation_error_schema["title"] = "입력값 오류"
        properties = validation_error_schema.get("properties", {})
        if "loc" in properties:
            properties["loc"]["title"] = "위치"
            properties["loc"]["description"] = "오류가 발생한 입력 위치"
        if "msg" in properties:
            properties["msg"]["title"] = "오류 메시지"
            properties["msg"]["description"] = "입력값 오류 메시지"
        if "type" in properties:
            properties["type"]["title"] = "오류 종류"
            properties["type"]["description"] = "입력값 오류 종류"

    http_validation_error_schema = openapi_schema.get("components", {}).get("schemas", {}).get("HTTPValidationError")
    if http_validation_error_schema:
        http_validation_error_schema["title"] = "입력값 오류"
        properties = http_validation_error_schema.get("properties", {})
        if "detail" in properties:
            properties["detail"]["title"] = "상세 내용"
            properties["detail"]["description"] = "입력값 오류 상세 내용"

    for path_item in openapi_schema.get("paths", {}).values():
        for operation in path_item.values():
            if not isinstance(operation, dict):
                continue
            responses = operation.get("responses", {})
            if "200" in responses and responses["200"].get("description") == "Successful Response":
                responses["200"]["description"] = "정상 응답"
            if "422" in responses and responses["422"].get("description") == "Validation Error":
                responses["422"]["description"] = "입력값 오류"

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


app.mount("/web", StaticFiles(directory="app/web", html=True), name="web")


@app.get("/", summary="서버 상태 조회")
async def root():
    return {"status": "product_automation_v2 backend running"}


@app.get("/health", summary="헬스 체크")
async def health():
    return {"status": "ok"}
