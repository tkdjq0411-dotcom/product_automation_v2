from __future__ import annotations
from typing import Any
from urllib.parse import urlparse

REQUIRED_FIELDS=("product_name","purchase_price","shipping_fee","image_urls")


def _source_slug(url: str) -> str:
    parts=[p for p in urlparse(url).path.split("/") if p]
    return parts[0].strip() if parts else ""


def _diag_message(diag: dict[str, Any]) -> str:
    stage=str(diag.get("stage") or "").strip()
    error=str(diag.get("error") or "").strip()
    direct=diag.get("direct_fields") if isinstance(diag.get("direct_fields"),dict) else {}
    if error:
        if "Executable doesn't exist" in error or "playwright install" in error.lower():
            return "서버 브라우저가 설치되지 않아 렌더링 수집을 실행하지 못했습니다."
        return f"서버 브라우저 자동진단: {stage or '실행'} 단계 실패"
    if stage == "complete":
        count=sum([
            bool(direct.get("product_name")), bool(direct.get("store_name")), bool(direct.get("price")),
            bool(direct.get("shipping")), int(direct.get("images") or 0)>0, int(direct.get("option_groups") or 0)>0,
        ])
        return f"서버 브라우저 렌더링 완료 · 핵심 필드 {count}/6 감지"
    if stage:
        return f"서버 브라우저 자동진단 단계: {stage}"
    return "서버 브라우저 진단 정보 없음"


async def collect_naver(url: str) -> dict[str, Any]:
    """Automatic server-side Naver sourcing collector.

    Users only paste a URL. The collector tries HTTP + a real server-side browser,
    inspects the rendered shopper-facing DOM and browser-received JSON/XHR, and
    returns only verified values. It never requires a Chrome extension and never
    fabricates missing fields.
    """
    from app.modules.sourcing.url_importer import import_product_url
    item=await import_product_url(url)

    images=[u for u in (item.get("image_urls") or []) if u]
    item["image_urls"]=images
    item["image_url"]=images[0] if images else None

    # A URL path slug is an identifier, not the shopper-facing store name.
    # If browser rendering did not verify the visible store label, do not show the slug as supplier.
    slug=_source_slug(url)
    rendered=bool(item.get("rendered_collector_used"))
    store=str(item.get("supplier_store_name") or "").strip()
    if not rendered and slug and store.casefold()==slug.casefold():
        item["supplier_store_name"]=None
        item["supplier_name"]=None

    missing=[]
    if not item.get("product_name"): missing.append("상품명")
    if not item.get("supplier_store_name"): missing.append("상점명")
    if item.get("purchase_price") is None: missing.append("매입가")
    if item.get("shipping_fee") is None: missing.append("배송비")
    if not images: missing.append("상품 이미지")
    if not (item.get("option_groups") or []): missing.append("옵션")

    diag=item.get("collector_diagnostics") or {}
    item["collector"]="NAVER_SERVER_AUTO_DIAGNOSTIC"
    item["extension_required"]=False
    item["diagnostic_summary"]=_diag_message(diag)

    if missing:
        any_verified=any([
            item.get("product_name"), item.get("supplier_store_name"),
            item.get("purchase_price") is not None, item.get("shipping_fee") is not None,
            images, item.get("option_groups")
        ])
        item["import_status"]="PARTIAL" if any_verified else "COLLECT_FAILED"
        item["import_message"]=(
            "자동수집 미완료: " + ", ".join(missing) + " · " + item["diagnostic_summary"]
        )
    else:
        item["import_status"]="OK"
        item["import_message"]="네이버 실페이지 1~7 필드 자동수집 완료"
    return item
