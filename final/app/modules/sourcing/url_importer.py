from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from pathlib import Path
import html as html_lib
import ipaddress
import json
import re
import socket
from dataclasses import dataclass, asdict
from html.parser import HTMLParser
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse

import httpx

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/151.0 Safari/537.36"
)

# Supported sourcing markets are intentionally fixed to the business scope.
# Unknown shopping sites are not silently treated as supported.
PLATFORMS = {
    # Korea
    "smartstore.naver.com": "NAVER_SMARTSTORE",
    "brand.naver.com": "NAVER_SMARTSTORE",
    "shopping.naver.com": "NAVER_SHOPPING",
    "m.shopping.naver.com": "NAVER_SHOPPING",
    "coupang.com": "COUPANG",
    "gmarket.co.kr": "GMARKET",
    "auction.co.kr": "AUCTION",
    "11st.co.kr": "11ST",
    # China
    "alibaba.com": "ALIBABA",
    "1688.com": "1688",
    "aliexpress.com": "ALIEXPRESS",
    "taobao.com": "TAOBAO",
    "tmall.com": "TMALL",
    # Global
    "amazon.com": "AMAZON",
    "ebay.com": "EBAY",
    "temu.com": "TEMU",
}

SUPPORTED_LABELS = {
    "NAVER_SMARTSTORE": "네이버 스마트스토어",
    "NAVER_SHOPPING": "네이버쇼핑",
    "COUPANG": "쿠팡",
    "GMARKET": "G마켓",
    "AUCTION": "옥션",
    "11ST": "11번가",
    "ALIBABA": "Alibaba.com",
    "1688": "1688",
    "ALIEXPRESS": "AliExpress",
    "TAOBAO": "Taobao",
    "TMALL": "Tmall",
    "AMAZON": "Amazon",
    "EBAY": "eBay",
    "TEMU": "Temu",
}


BLOCKED_MARKERS = (
    "captcha", "verify you are human", "access denied", "robot check", "unusual traffic",
    "please verify", "security check", "请进行验证", "滑动验证", "人机验证", "접근이 제한",
    "에러페이지", "오류 페이지", "일시적인 오류", "서비스에 접속할 수 없습니다",
    "비정상적인 접근", "요청하신 페이지를 찾을 수 없습니다", "접근 권한이 없습니다",
)


class ProductHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.json_ld_chunks: list[str] = []
        self.script_chunks: list[str] = []
        self.title_chunks: list[str] = []
        self._script_type = ""
        self._in_script = False
        self._in_title = False
        self._buf: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        d = {str(k).lower(): (v or "") for k, v in attrs}
        t = tag.lower()
        if t == "meta":
            key = (d.get("property") or d.get("name") or d.get("itemprop") or "").strip().lower()
            content = d.get("content", "").strip()
            if key and content and key not in self.meta:
                self.meta[key] = content
        elif t == "script":
            self._in_script = True
            self._script_type = d.get("type", "").lower()
            self._buf = []
        elif t == "title":
            self._in_title = True
            self._buf = []

    def handle_endtag(self, tag: str) -> None:
        t = tag.lower()
        if t == "script" and self._in_script:
            chunk = "".join(self._buf).strip()
            if chunk:
                if "ld+json" in self._script_type:
                    self.json_ld_chunks.append(chunk)
                elif len(chunk) <= 2_000_000:
                    self.script_chunks.append(chunk)
            self._in_script = False
            self._script_type = ""
            self._buf = []
        elif t == "title" and self._in_title:
            self.title_chunks.append("".join(self._buf).strip())
            self._in_title = False
            self._buf = []

    def handle_data(self, data: str) -> None:
        if self._in_script or self._in_title:
            self._buf.append(data)


@dataclass
class ImportedProduct:
    source_url: str
    final_url: str
    platform: str
    source_product_id: str | None = None
    product_name: str | None = None
    supplier_name: str | None = None
    supplier_store_name: str | None = None
    supplier_store_url: str | None = None
    purchase_price: float | None = None
    shipping_fee: float | None = None
    currency: str | None = None
    options: list[str] | None = None
    option_groups: list[dict[str, Any]] | None = None
    option_variants: list[dict[str, Any]] | None = None
    image_urls: list[str] | None = None
    availability: str = "UNKNOWN"
    description: str | None = None
    import_status: str = "PARTIAL"
    import_message: str = ""
    extraction_method: str = "LIVE_HTTP"
    confidence: int = 0
    live_fetch: bool = True

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if self.option_groups:
            parts = []
            for group in self.option_groups:
                name = _clean_text(str(group.get("name") or ""), 100)
                values = [_clean_text(str(x), 100) for x in (group.get("values") or [])]
                values = [x for x in values if x]
                if values:
                    parts.append(f"{name}: " + " / ".join(values) if name else " / ".join(values))
            d["options_text"] = " | ".join(parts) if parts else (" / ".join(self.options or []) if self.options else None)
        else:
            d["options_text"] = " / ".join(self.options or []) if self.options else None
        d["options_json"] = json.dumps({"groups": self.option_groups or [], "variants": self.option_variants or []}, ensure_ascii=False)
        d["image_url"] = (self.image_urls or [None])[0]
        d["image_urls_json"] = json.dumps(self.image_urls or [], ensure_ascii=False)
        return d


def detect_platform(host: str) -> str:
    host = host.lower().split(":", 1)[0].strip(".")
    for domain, platform in PLATFORMS.items():
        if host == domain or host.endswith("." + domain):
            return platform
    # Amazon/eBay/Temu operate regional domains. Keep them in the same supported family.
    if re.fullmatch(r"(?:www\.)?amazon\.[a-z.]{2,10}", host) or ".amazon." in host:
        return "AMAZON"
    if re.fullmatch(r"(?:www\.)?ebay\.[a-z.]{2,10}", host) or ".ebay." in host:
        return "EBAY"
    if re.fullmatch(r"(?:www\.)?temu\.[a-z.]{2,10}", host) or ".temu." in host:
        return "TEMU"
    return "UNSUPPORTED"


def product_id_from_url(url: str, platform: str) -> str | None:
    p = urlparse(url)
    qs = parse_qs(p.query)
    for key in ("id", "itemId", "item_id", "productId", "product_id", "goodsNo", "offerId", "sku", "asin"):
        value = qs.get(key, [None])[0]
        if value and re.fullmatch(r"[A-Za-z0-9_-]{4,100}", str(value)):
            return str(value)
    patterns = [
        r"/dp/([A-Z0-9]{8,16})(?:[/?]|$)",
        r"/gp/product/([A-Z0-9]{8,16})(?:[/?]|$)",
        r"/itm/(?:[^/]+/)?(\d{8,})(?:[/?]|$)",
        r"/vp/products/(\d+)",
        r"/(?:item|product|products|goods|offer)[/_-]?(\d{5,})",
        r"/offer/(\d+)\.html",
        r"/item\.htm.*?[?&]id=(\d+)",
        r"product-detail/[^/?]*[_-](\d{7,})\.html",
        r"/(\d{8,})(?:\.html)?(?:/|$)",
    ]
    target = p.path + ("?" + p.query if p.query else "")
    for pat in patterns:
        m = re.search(pat, target, re.I)
        if m:
            return m.group(1)
    return None


def _is_public_ip(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return not (addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_multicast or addr.is_reserved or addr.is_unspecified)


async def _validate_public_url(url: str) -> None:
    p = urlparse(url)
    if p.scheme not in {"http", "https"} or not p.hostname:
        raise ValueError("http/https 상품 URL만 사용할 수 있습니다.")
    if p.username or p.password:
        raise ValueError("인증정보가 포함된 URL은 사용할 수 없습니다.")
    try:
        infos = await asyncio.to_thread(socket.getaddrinfo, p.hostname, p.port or (443 if p.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError("상품 사이트 주소를 찾을 수 없습니다.") from exc
    ips = {info[4][0] for info in infos}
    if not ips or any(not _is_public_ip(ip) for ip in ips):
        raise ValueError("내부망/로컬 주소는 가져올 수 없습니다.")


def _number(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        n = float(value)
        return n if n >= 0 else None
    text = html_lib.unescape(str(value)).replace(",", "")
    # Range price uses the first/lower displayed price.
    m = re.search(r"(?:US\s*\$|USD|KRW|CNY|RMB|JPY|₩|￥|¥|\$|€|£)?\s*([0-9]+(?:\.[0-9]+)?)", text)
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def _walk_product(obj: Any) -> dict[str, Any] | None:
    if isinstance(obj, dict):
        typ = obj.get("@type")
        types = typ if isinstance(typ, list) else [typ]
        if any(str(x).lower() == "product" for x in types if x):
            return obj
        for key in ("@graph", "mainEntity", "itemListElement", "hasVariant", "product"):
            if key in obj:
                hit = _walk_product(obj[key])
                if hit:
                    return hit
        for v in obj.values():
            hit = _walk_product(v)
            if hit:
                return hit
    elif isinstance(obj, list):
        for v in obj:
            hit = _walk_product(v)
            if hit:
                return hit
    return None


def _is_placeholder_image(url: str) -> bool:
    u=(url or "").lower()
    bad=("sp_u_skip.png","sp_common.png","favicon","logo_naver","noimage","no_image","blank.gif","transparent.gif")
    return any(x in u for x in bad)


def _images(value: Any, base_url: str = "") -> list[str]:
    out: list[str] = []
    if isinstance(value, str):
        s = value.replace("\\/", "/").strip()
        if s.startswith("//"):
            s = "https:" + s
        elif s.startswith("/") and base_url:
            s = urljoin(base_url, s)
        if s.startswith(("http://", "https://")):
            out.append(s)
    elif isinstance(value, list):
        for x in value:
            out.extend(_images(x, base_url))
    elif isinstance(value, dict):
        for key in ("url", "contentUrl", "imageUrl", "image", "src"):
            if value.get(key):
                out.extend(_images(value[key], base_url))
    return [u for u in list(dict.fromkeys(out)) if not _is_placeholder_image(u)][:50]


def _offer(product: dict[str, Any]) -> dict[str, Any]:
    offers = product.get("offers") or {}
    if isinstance(offers, list):
        return next((x for x in offers if isinstance(x, dict)), {})
    return offers if isinstance(offers, dict) else {}


def _availability(value: Any) -> str:
    text = str(value or "").lower()
    if any(k in text for k in ("instock", "in_stock", "available", "판매중", "구매가능", "有货", "现货")):
        return "AVAILABLE"
    if any(k in text for k in ("outofstock", "out_of_stock", "soldout", "품절", "일시품절", "无货", "下架")):
        return "OUT_OF_STOCK"
    return "UNKNOWN"


def _mojibake_score(text: str) -> int:
    """Lower is better. Penalize replacement/control/mojibake artifacts."""
    if not text:
        return 10_000
    bad = text.count("�") * 20
    bad += sum(text.count(x) * 4 for x in ("Ã", "Â", "ì", "ë", "ê", "ð"))
    bad += sum(1 for ch in text if ord(ch) < 32 and ch not in "\r\n\t") * 5
    # Reward readable Korean/ASCII slightly so a recovered string wins ties.
    readable = sum(1 for ch in text if ("가" <= ch <= "힣") or ch.isascii())
    return bad - min(readable // 50, 10)


def _repair_mojibake(value: str) -> str:
    """Repair common UTF-8/CP949 decoding mistakes without inventing text."""
    candidates = [value]
    for src in ("latin1", "cp1252"):
        try:
            candidates.append(value.encode(src).decode("utf-8"))
        except Exception:
            pass
    # Replacement characters cannot be reversed reliably. Keep the original so
    # the validator can reject it instead of saving garbage as a product title.
    return min(candidates, key=_mojibake_score)


def _looks_corrupted_text(value: str | None) -> bool:
    if not value:
        return False
    if "�" in value:
        return True
    return _mojibake_score(value) >= 12


def _clean_text(value: str | None, max_len: int = 5000) -> str | None:
    if not value:
        return None
    value = _repair_mojibake(str(value))
    value = re.sub(r"\s+", " ", html_lib.unescape(value)).strip()
    if not value or _looks_corrupted_text(value):
        return None
    return value[:max_len] or None


def _embedded_values(html: str, keys: tuple[str, ...], max_items: int = 80) -> list[str]:
    found: list[str] = []
    key_alt = "|".join(re.escape(k) for k in keys)
    patterns = [
        rf'["\'](?:{key_alt})["\']\s*:\s*["\']([^"\']{{1,500}})["\']',
        rf'\b(?:{key_alt})\b\s*[:=]\s*["\']([^"\']{{1,500}})["\']',
    ]
    for pat in patterns:
        for raw in re.findall(pat, html, re.I):
            clean = _clean_text(raw, 500)
            if clean and clean not in found:
                found.append(clean)
                if len(found) >= max_items:
                    return found
    return found


def _heuristic_options(html: str) -> list[str]:
    keys = (
        "propertyValueDisplayName", "skuPropertyValue", "skuPropertyName", "skuName", "skuValue",
        "variationValue", "variationName", "optionValue", "optionName", "specValue", "specName",
    )
    found = _embedded_values(html, keys, 100)
    # Platform state often stores value/name in SKU arrays. Restrict to short human strings.
    for block_pat in (
        r'"skuPropertyValues"\s*:\s*\[(.{0,150000}?)\]\s*[,}]',
        r'"skuProps"\s*:\s*\[(.{0,150000}?)\]\s*[,}]',
        r'"variations?"\s*:\s*\[(.{0,150000}?)\]\s*[,}]',
    ):
        for block in re.findall(block_pat, html, re.I | re.S):
            for raw in re.findall(r'"(?:displayName|name|value|label)"\s*:\s*"([^"\\]{1,100})"', block):
                clean = _clean_text(raw, 100)
                if clean and clean not in found and not re.fullmatch(r"\d+(?:\.\d+)?", clean):
                    found.append(clean)
                if len(found) >= 100:
                    return found[:100]
    return found[:100]


def _heuristic_images(html: str, base_url: str) -> list[str]:
    values = _embedded_values(html, ("imageUrls", "images", "imageList", "productImages", "imageUrl", "imageURL", "image", "mainImage", "skuImage", "picUrl", "picURL", "src"), 100)
    out: list[str] = []
    for raw in values:
        out.extend(_images(raw, base_url))
    # Common escaped CDN image strings.
    for raw in re.findall(r'https?:\\?/\\?/[^"\'<> ]+?\.(?:jpg|jpeg|png|webp)(?:\?[^"\'<> ]*)?', html, re.I):
        out.extend(_images(raw, base_url))
    return [u for u in list(dict.fromkeys(out)) if not _is_placeholder_image(u)][:50]


def _clean_product_title(value: str | None) -> str | None:
    value = _clean_text(value, 500)
    if not value:
        return None
    # Commerce pages often append the store/channel to the actual product title.
    value = re.sub(r"\s*[:|\-]\s*(?:네이버\s*)?(?:스마트스토어|브랜드스토어|쇼핑)\s*$", "", value, flags=re.I)
    value = re.sub(r"\s*[:|\-]\s*NAVER\s*(?:SmartStore|Shopping)?\s*$", "", value, flags=re.I)
    return value.strip() or None


def _heuristic_title(html: str) -> str | None:
    vals = _embedded_values(html, ("productTitle", "subject", "itemTitle", "goodsName", "productName", "title"), 20)
    for v in vals:
        if 3 <= len(v) <= 300 and not v.startswith(("http://", "https://")):
            return v
    return None


def _heuristic_price(html: str) -> float | None:
    vals = _embedded_values(html, ("salePrice", "discountPrice", "minPrice", "price", "priceValue", "itemPrice", "promotionPrice"), 50)
    nums = [_number(v) for v in vals]
    nums = [n for n in nums if n is not None and 0 < n < 1_000_000_000]
    return nums[0] if nums else None


def _heuristic_currency(html: str) -> str | None:
    vals = _embedded_values(html, ("priceCurrency", "currency", "currencyCode"), 20)
    for v in vals:
        c = v.strip().upper()
        if re.fullmatch(r"[A-Z]{3}", c):
            return c
    return None



STORE_KEYS = ("storeName", "smartStoreName", "channelName", "mallName", "sellerName", "merchantName", "shopName", "brandStoreName")
PRICE_KEYS = ("salePrice", "discountedPrice", "discountPrice", "sellingPrice", "finalPrice", "price", "minPrice")
SHIPPING_KEYS = ("deliveryFee", "baseDeliveryFee", "shippingFee", "deliveryPrice", "shippingCost", "deliveryCharge")
OPTION_GROUP_KEYS = ("optionGroups", "optionGroup", "options", "optionInfo", "optionInfos", "optionCombinations", "optionProducts", "skuProps", "skuPropertyList", "variations")
AVAILABILITY_KEYS = ("stockQuantity", "stock", "quantity", "saleStatus", "status", "soldOut", "isSoldOut", "available")


def _walk_dicts(obj: Any):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _walk_dicts(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk_dicts(v)


def _json_objects_from_text(text: str) -> list[Any]:
    out: list[Any] = []
    raw = (text or "").strip()
    if not raw:
        return out
    try:
        out.append(json.loads(raw))
        return out
    except Exception:
        pass
    # Script bodies frequently wrap JSON in assignment/callback syntax.
    for pat in (r'__NEXT_DATA__\s*=\s*(\{.*\})\s*;?$', r'__INITIAL_STATE__\s*=\s*(\{.*\})\s*;?$', r'\((\{.*\})\)\s*;?$'):
        m = re.search(pat, raw, re.S)
        if m:
            try:
                out.append(json.loads(m.group(1)))
            except Exception:
                pass
    return out


def _first_key_value(objs: list[Any], keys: tuple[str, ...], *, numeric: bool = False) -> Any:
    keyset = {k.casefold() for k in keys}
    for obj in objs:
        for d in _walk_dicts(obj):
            for k, v in d.items():
                if str(k).casefold() in keyset and v not in (None, "", [], {}):
                    if numeric:
                        n = _number(v)
                        if n is not None and 0 <= n < 1_000_000_000:
                            return n
                    elif isinstance(v, (str, int, float, bool)):
                        return v
    return None


def _store_url(final_url: str, platform: str) -> str | None:
    p = urlparse(final_url)
    parts = [x for x in p.path.split('/') if x]
    if platform == 'NAVER_SMARTSTORE' and parts:
        # brand.naver.com/nuldam/products/... or smartstore.naver.com/store/...
        return f"{p.scheme}://{p.netloc}/{parts[0]}"
    return f"{p.scheme}://{p.netloc}" if p.scheme and p.netloc else None


def _platform_prefix(platform: str) -> str:
    return {
        'NAVER_SMARTSTORE':'네이버','NAVER_SHOPPING':'네이버','COUPANG':'쿠팡','GMARKET':'G마켓',
        'AUCTION':'옥션','11ST':'11번가','ALIBABA':'Alibaba','1688':'1688','ALIEXPRESS':'AliExpress',
        'TAOBAO':'Taobao','TMALL':'Tmall','AMAZON':'Amazon','EBAY':'eBay','TEMU':'Temu'
    }.get(platform, SUPPORTED_LABELS.get(platform, platform))


def _extract_store_name(objs: list[Any], html: str, meta: dict[str, str], final_url: str, platform: str) -> str | None:
    value = _first_key_value(objs, STORE_KEYS)
    clean = _clean_text(str(value), 200) if value is not None else None
    if not clean:
        clean = _clean_text(meta.get('og:site_name'), 200)
    # Never manufacture the visible supplier name from a Naver URL slug.
    # The user-facing supplier must come from an actual page/store label or trusted product data.
    return clean


def _extract_option_groups(objs: list[Any], html: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    groups: dict[str, list[str]] = {}
    variants: list[dict[str, Any]] = []
    seen_variants: set[str] = set()

    def add_group(name: Any, values: Any):
        n = _clean_text(str(name or ''), 100) or '옵션'
        vals: list[str] = []
        if isinstance(values, list):
            for x in values:
                if isinstance(x, dict):
                    raw = next((x.get(k) for k in ('valueName','optionValue','name','label','value','text','displayName') if x.get(k) not in (None,'')), None)
                else:
                    raw = x
                c = _clean_text(str(raw),100) if raw is not None else None
                if c and c not in vals and not re.fullmatch(r'[-+]?\d+(?:\.\d+)?', c): vals.append(c)
        if vals:
            bucket=groups.setdefault(n,[])
            for v in vals:
                if v not in bucket: bucket.append(v)

    for obj in objs:
        for d in _walk_dicts(obj):
            # Common option group shapes across marketplaces.
            name = next((d.get(k) for k in ('optionName','groupName','propertyName','attributeName','skuPropertyName','name') if d.get(k) not in (None,'')), None)
            values = next((d.get(k) for k in ('optionValues','values','items','choices','skuPropertyValues','valueList') if isinstance(d.get(k), list)), None)
            if name is not None and values:
                add_group(name, values)

            # Combination/SKU variant. Capture exact choice text, extra/final price, availability, ids.
            choice_parts=[]
            for k in ('optionName1','optionName2','optionName3','optionValue1','optionValue2','optionValue3','combinationName','skuName','optionName'):
                v=d.get(k)
                if isinstance(v,(str,int,float)):
                    c=_clean_text(str(v),120)
                    if c and c not in choice_parts: choice_parts.append(c)
            if not choice_parts:
                for k in ('options','optionValues','selectedOptions'):
                    vals=d.get(k)
                    if isinstance(vals,list):
                        for x in vals:
                            if isinstance(x,dict):
                                v=next((x.get(q) for q in ('valueName','name','label','value') if x.get(q) not in (None,'')),None)
                                c=_clean_text(str(v),120) if v is not None else None
                                if c and c not in choice_parts: choice_parts.append(c)
            variant_id = next((d.get(k) for k in ('optionId','optionNo','skuId','skuNo','combinationId','id') if isinstance(d.get(k),(str,int)) and str(d.get(k))), None)
            price = next((_number(d.get(k)) for k in ('salePrice','price','discountPrice','optionPrice','additionalPrice','extraPrice') if _number(d.get(k)) is not None), None)
            additional = next((_number(d.get(k)) for k in ('additionalPrice','optionPrice','extraPrice') if _number(d.get(k)) is not None), None)
            av='UNKNOWN'
            for k in AVAILABILITY_KEYS:
                if k in d:
                    v=d.get(k)
                    if isinstance(v,bool): av='OUT_OF_STOCK' if k.lower().find('soldout')>=0 and v else ('AVAILABLE' if v else 'OUT_OF_STOCK')
                    elif isinstance(v,(int,float)): av='AVAILABLE' if float(v)>0 else 'OUT_OF_STOCK'
                    else:
                        av2=_availability(v)
                        if av2!='UNKNOWN': av=av2
                    if av!='UNKNOWN': break
            if choice_parts and (variant_id is not None or price is not None or av!='UNKNOWN'):
                key='|'.join(choice_parts)+f'|{variant_id}|{price}|{av}'
                if key not in seen_variants:
                    seen_variants.add(key)
                    variants.append({'id': str(variant_id) if variant_id is not None else None, 'options': choice_parts, 'price': price, 'additional_price': additional, 'availability': av})

    # Regex fallback for pages where the script is not valid JSON.
    if not groups:
        vals=_heuristic_options(html)
        if vals: groups['옵션']=vals
    return ([{'name': k, 'values': v[:200]} for k,v in groups.items()][:20], variants[:1000])


def _extract_shipping(objs: list[Any], html: str) -> float | None:
    n=_first_key_value(objs, SHIPPING_KEYS, numeric=True)
    if n is not None: return n
    # Human-readable Korean fallback: 배송비 3,000원 / 무료배송.
    if re.search(r'무료\s*배송|배송비\s*무료', html, re.I):
        return 0.0
    for pat in (r'배송비[^0-9]{0,50}([0-9][0-9,]{1,10})\s*원', r'(?:delivery|shipping)\s*(?:fee|cost)[^0-9]{0,50}([0-9][0-9,.]{1,12})'):
        m=re.search(pat, html, re.I)
        if m:
            n=_number(m.group(1))
            if n is not None: return n
    return None


def _extract_structured_objects(parser: ProductHTMLParser) -> list[Any]:
    objs=[]
    for chunk in parser.json_ld_chunks + parser.script_chunks:
        objs.extend(_json_objects_from_text(chunk))
    return objs[:200]

def parse_product_html(html: str, source_url: str, final_url: str, status_code: int, method: str = "LIVE_HTTP") -> ImportedProduct:
    p = urlparse(final_url)
    platform = detect_platform(p.hostname or "")
    item = ImportedProduct(source_url=source_url, final_url=final_url, platform=platform, extraction_method=method)
    item.source_product_id = product_id_from_url(final_url, platform)

    parser = ProductHTMLParser()
    parser.feed(html)
    structured_objects = _extract_structured_objects(parser)

    product: dict[str, Any] = {}
    for chunk in parser.json_ld_chunks:
        if not chunk:
            continue
        try:
            obj = json.loads(chunk)
        except Exception:
            continue
        hit = _walk_product(obj)
        if hit:
            product = hit
            break

    offer = _offer(product)
    meta = parser.meta
    item.supplier_store_name = _extract_store_name(structured_objects, html, meta, final_url, platform)
    item.supplier_store_url = _store_url(final_url, platform)
    if item.supplier_store_name:
        item.supplier_name = f"{_platform_prefix(platform)}-{item.supplier_store_name}"
    item.product_name = _clean_product_title(
        product.get("name") or meta.get("og:title") or meta.get("twitter:title") or _heuristic_title(html) or
        (parser.title_chunks[0] if parser.title_chunks else None)
    )
    item.description = _clean_text(product.get("description") or meta.get("og:description") or meta.get("description"), 5000)
    item.image_urls = (
        _images(product.get("image"), final_url) or _images(meta.get("og:image"), final_url) or
        _images(meta.get("twitter:image"), final_url) or _heuristic_images(html, final_url)
    )
    item.purchase_price = _number(
        offer.get("price") or offer.get("lowPrice") or meta.get("product:price:amount") or
        meta.get("og:price:amount") or meta.get("price")
    )
    if item.purchase_price is None:
        item.purchase_price = _first_key_value(structured_objects, PRICE_KEYS, numeric=True)
    if item.purchase_price is None:
        item.purchase_price = _heuristic_price(html)
    item.shipping_fee = _extract_shipping(structured_objects, html)
    item.currency = str(
        offer.get("priceCurrency") or meta.get("product:price:currency") or meta.get("og:price:currency") or ""
    ).upper() or _heuristic_currency(html)
    item.availability = _availability(offer.get("availability") or meta.get("product:availability"))
    if item.availability == "UNKNOWN":
        item.availability = _availability(html[:1_500_000])
    item.option_groups, item.option_variants = _extract_option_groups(structured_objects, html)

    # Browser extension sends a DOM-first snapshot under __B2B_DIRECT__.
    # Prefer these values over generic script heuristics because they are the values
    # actually rendered on the product page the user is viewing.
    direct = None
    for obj in structured_objects:
        if isinstance(obj, dict) and isinstance(obj.get("__B2B_DIRECT__"), dict):
            direct = obj.get("__B2B_DIRECT__")
            break
    if direct:
        dn = _clean_product_title(direct.get("productName"))
        if dn and not _looks_corrupted_text(dn) and not any(x in dn.lower() for x in BLOCKED_MARKERS):
            item.product_name = dn
        sn = _clean_text(str(direct.get("storeName") or ""), 200)
        if sn:
            item.supplier_store_name = sn
            item.supplier_name = f"{_platform_prefix(platform)}-{sn}"
        su = str(direct.get("storeUrl") or "").strip()
        if su:
            item.supplier_store_url = su
        dp = _number(direct.get("price"))
        if dp is not None:
            item.purchase_price = dp
        ds = _number(direct.get("shippingFee"))
        if ds is not None:
            item.shipping_fee = ds
        di = direct.get("imageUrls")
        if isinstance(di, list):
            real=[]
            for u in di:
                u=str(u or '').strip()
                if u and not _is_placeholder_image(u) and u not in real:
                    real.append(u)
            if real:
                item.image_urls=real[:50]
        dg = direct.get("optionGroups")
        if isinstance(dg, list) and dg:
            clean_groups=[]
            for idx,g in enumerate(dg,1):
                if not isinstance(g,dict): continue
                name=_clean_text(str(g.get("name") or f"옵션{idx}"),100) or f"옵션{idx}"
                vals=[]
                for v in g.get("values") or []:
                    c=_clean_text(str(v),160)
                    if c and c not in vals: vals.append(c)
                if vals: clean_groups.append({"name":name,"values":vals})
            if clean_groups:
                item.option_groups=clean_groups
        dav = str(direct.get("availability") or "").strip().upper()
        if dav in {"AVAILABLE","OUT_OF_STOCK","UNKNOWN"}:
            item.availability = dav

    item.options = []
    for group in item.option_groups or []:
        for value in group.get("values") or []:
            if value not in item.options:
                item.options.append(value)
    if not item.options:
        item.options = _heuristic_options(html)

    if not item.source_product_id:
        item.source_product_id = str(product.get("sku") or product.get("productID") or meta.get("product:retailer_item_id") or "") or None

    # Never accept a garbled page title/product name as real sourced data.
    if _looks_corrupted_text(item.product_name):
        item.product_name = None
    if _looks_corrupted_text(item.description):
        item.description = None
    item.options = [x for x in (item.options or []) if not _looks_corrupted_text(x)] or None

    score = 0
    score += 25 if item.product_name else 0
    score += 25 if item.purchase_price is not None else 0
    score += 15 if item.image_urls else 0
    score += 10 if item.source_product_id else 0
    score += 10 if item.options else 0
    score += 5 if item.shipping_fee is not None else 0
    score += 5 if item.supplier_store_name else 0
    score += 5 if item.currency else 0
    score += 5 if item.availability != "UNKNOWN" else 0
    score += 5 if item.description else 0
    item.confidence = min(score, 100)

    html_l = html.lower()
    blocked = status_code in (401, 403, 429) or any(x in html_l for x in BLOCKED_MARKERS)
    # Never treat a platform error shell as a partially imported product.
    # URL/product-id alone are not product data, and shared UI assets are not product images.
    if blocked:
        item.product_name = None if (item.product_name and any(x in item.product_name.lower() for x in BLOCKED_MARKERS)) else item.product_name
        item.image_urls = [u for u in (item.image_urls or []) if not _is_placeholder_image(u)] or None
        has_real_core = bool(item.product_name and item.purchase_price is not None and item.image_urls)
        if not has_real_core:
            item.import_status = "API_REQUIRED"
            item.import_message = "정상 상품 페이지가 아니라 오류/접근제한 페이지가 반환되었습니다. 서버 크롤링 결과는 저장하지 않고 일반 Chrome 직접수집으로 전환해야 합니다."
            item.confidence = min(item.confidence, 25)
            return item
    if blocked and item.confidence < 50:
        item.import_status = "API_REQUIRED"
        item.import_message = "사이트가 자동 조회를 제한했습니다. 허용된 공식 API/제휴 권한이 있으면 해당 방식으로 연결해야 합니다."
    elif item.confidence >= 70:
        item.import_status = "OK"
        item.import_message = "실제 상품 페이지에서 핵심 정보를 수집했습니다. 판매 전 가격·옵션은 최종 확인하세요."
    elif item.confidence >= 35:
        item.import_status = "PARTIAL"
        item.import_message = "실제 페이지에서 일부 정보를 수집했습니다. 비어 있는 항목은 동적 로딩 또는 로그인/API 권한이 필요한 항목입니다."
    else:
        item.import_status = "API_REQUIRED" if blocked else "PARTIAL"
        item.import_message = "상품 페이지는 열렸지만 핵심 정보가 공개 HTML에 충분히 노출되지 않았습니다. 브라우저 렌더링/공식 API 연결이 필요합니다."
    return item


def _decode_http_body(response: httpx.Response) -> str:
    raw = response.content[:8_000_000]
    candidates: list[str] = []
    # Honor an explicit charset first, then try encodings used by Korean commerce sites.
    ctype = response.headers.get("content-type", "")
    m = re.search(r"charset\s*=\s*[\"']?([^;\"'\s]+)", ctype, re.I)
    encodings = [m.group(1) if m else None, "utf-8", "cp949", "euc-kr"]
    seen: set[str] = set()
    for enc in encodings:
        if not enc:
            continue
        enc = enc.strip().lower()
        if enc in seen:
            continue
        seen.add(enc)
        try:
            candidates.append(raw.decode(enc, errors="strict"))
        except Exception:
            pass
    if not candidates:
        candidates.append(raw.decode("utf-8", errors="replace"))
    return min(candidates, key=_mojibake_score)


async def _http_fetch(url: str) -> tuple[str, str, int]:
    timeout = httpx.Timeout(20.0, connect=10.0)
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache",
    }
    async with httpx.AsyncClient(timeout=timeout, headers=headers, follow_redirects=False) as client:
        current = url
        response: httpx.Response | None = None
        for _ in range(6):
            await _validate_public_url(current)
            response = await client.get(current)
            if response.status_code in {301, 302, 303, 307, 308} and response.headers.get("location"):
                current = str(response.url.join(response.headers["location"]))
                continue
            break
        if response is None:
            raise ValueError("상품 페이지를 가져오지 못했습니다.")
        content_type = response.headers.get("content-type", "").lower()
        if not any(x in content_type for x in ("text/html", "application/xhtml", "text/plain")):
            raise ValueError("상품 상세페이지 URL을 입력해주세요.")
        return _decode_http_body(response), str(response.url), response.status_code


async def _browser_fetch(url: str) -> dict[str, Any] | None:
    """Render in an isolated Python process.

    Uvicorn on some Windows/Python configurations runs an asyncio loop that cannot
    create subprocess transports. Playwright itself needs a child process, so run
    the browser worker outside the server event loop. No CAPTCHA/access-control
    bypass is attempted.
    """
    worker = Path(__file__).with_name("browser_worker.py")
    if not worker.exists():
        return None

    def _run_worker() -> dict[str, Any] | None:
        try:
            env = dict(__import__("os").environ)
            env["PYTHONUTF8"] = "1"
            env["PYTHONIOENCODING"] = "utf-8"
            proc = subprocess.run(
                [sys.executable, "-X", "utf8", str(worker), url],
                capture_output=True,
                text=False,
                timeout=45,
                check=False,
                env=env,
                creationflags=(subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0),
            )
            if not proc.stdout.strip():
                stderr = proc.stderr.decode("utf-8", errors="replace")[-2000:]
                return {"ok": False, "diagnostics": {"stage": "worker_process", "error": stderr or f"exit={proc.returncode}"}}
            stdout = proc.stdout.decode("utf-8", errors="strict")
            payload = json.loads(stdout)
            if proc.returncode != 0:
                payload.setdefault("ok", False)
                payload.setdefault("diagnostics", {})["process_returncode"] = proc.returncode
            return payload
        except Exception as exc:
            return {"ok": False, "diagnostics": {"stage": "worker_parent", "error": f"{type(exc).__name__}: {exc}"}}

    payload = await asyncio.to_thread(_run_worker)
    if not payload:
        return {"collector_ok": False, "diagnostics": {"stage": "worker_parent", "error": "empty payload"}}
    if not payload.get("ok"):
        return {"collector_ok": False, "diagnostics": payload.get("diagnostics") or {"stage": "unknown"}}
    final_url = str(payload.get("final_url") or url)
    await _validate_public_url(final_url)
    return {
        "collector_ok": True,
        "html": str(payload.get("html") or "")[:8_000_000],
        "final_url": final_url,
        "status": int(payload.get("status") or 200),
        "title": str(payload.get("title") or ""),
        "network_blobs": payload.get("network_blobs") or [],
        "globals": payload.get("globals") or {},
        "diagnostics": payload.get("diagnostics") or {},
    }



def _json_load_loose(body: str) -> Any:
    """Parse JSON/JSONP bodies the browser legitimately received."""
    body=(body or '').strip().lstrip('\ufeff')
    if not body:
        return None
    for candidate in (body, re.sub(r'^[^(]*\((.*)\)\s*;?$', r'\1', body, flags=re.S)):
        try:
            return json.loads(candidate)
        except Exception:
            pass
    return None


def _network_naver_fields(source_url: str, blobs: list[dict[str, Any]]) -> dict[str, Any]:
    """Extract Naver product fields from browser-received JSON/XHR with product anchoring.

    V7 rule: never treat arbitrary page JSON as product data. A candidate subtree must
    either contain the requested product id or have strong product semantics. This
    prevents UI strings such as "비밀번호 표시 삭제" or platform labels such as
    "네이버" from being promoted into sourcing fields.
    """
    platform = detect_platform(urlparse(source_url).hostname or '')
    product_id = product_id_from_url(source_url, platform)
    out: dict[str, Any] = {"images": [], "option_groups": [], "confidence": {}}
    image_seen: set[str] = set()
    groups: dict[str, list[str]] = {}

    NAME_KEYS={'productname','product_name','goodsname','goods_name','itemname','item_name','producttitle','product_title','goods_title','title','name'}
    STORE_KEYS={'storename','store_name','shopname','shop_name','sellername','seller_name','mallname','mall_name','brandstorename','brand_store_name'}
    PRICE_KEYS=['finalprice','final_price','customerbenefitprice','customer_benefit_price','benefitprice','benefit_price','discountedsaleprice','discounted_sale_price','discountprice','discount_price','saleprice','sale_price','mobileprice','mobile_price','price']
    SHIPPING_KEYS={'deliveryfee','delivery_fee','shippingfee','shipping_fee','basefee','base_fee','deliveryprice','delivery_price','shippingprice','shipping_price'}
    IMAGE_KEYS={'imageurl','image_url','representativeimageurl','representative_image_url','mainimageurl','main_image_url','productimageurl','product_image_url','thumbnailurl','thumbnail_url','images','imageurls','image_urls','productimages','product_images'}
    OPTION_NAME_KEYS={'optionname','option_name','groupname','group_name','attribute','attribute_name','optiongroupname','option_group_name'}
    OPTION_VALUE_KEYS={'optionvalue','option_value','value','values','optionvalues','option_values','items','options'}
    AVAIL_KEYS={'sale_status','salestatus','status','productstatus','product_status','stockstatus','stock_status','availability'}
    ID_KEYS={'productid','product_id','productno','product_no','productnumber','product_number','goodsno','goods_no','itemid','item_id','id'}

    BAD_PRODUCT_RE=re.compile(r'(비밀번호\s*표시|비밀번호|로그인|NAVER\s*로그인|네이버\s*로그인|삭제|검색|장바구니|알림받기|혜택|배송조회|주문조회|고객센터|접근이\s*제한|에러페이지)',re.I)
    BAD_STORE_RE=re.compile(r'^(?:NAVER|네이버|네이버쇼핑|스마트스토어|브랜드스토어|쇼핑)$',re.I)

    def keynorm(k: Any)->str:
        return re.sub(r'[^a-z0-9_]', '', str(k or '').lower())
    def textv(v: Any, maxlen=300)->str|None:
        if isinstance(v,(str,int,float)):
            t=_clean_text(str(v),maxlen)
            return t or None
        return None
    def valid_product_name(v: Any)->str|None:
        t=textv(v,500)
        if not t or len(t)<4 or re.fullmatch(r'\d+',t) or BAD_PRODUCT_RE.search(t): return None
        if re.fullmatch(r'(?:NAVER|네이버|옵션|배송|리뷰|혜택|상품)',t,re.I): return None
        return t
    def valid_store(v: Any)->str|None:
        t=textv(v,150)
        if not t or BAD_STORE_RE.fullmatch(t): return None
        return t
    def explicit_number(v: Any)->float|None:
        if isinstance(v,(int,float)):
            n=float(v); return n if n>=0 else None
        if isinstance(v,str):
            t=v.strip().replace(',','').replace('원','').strip()
            if re.fullmatch(r'\d+(?:\.\d+)?',t):
                try: return float(t)
                except Exception: return None
        return None
    def add_image(v: Any):
        for u in _images(v, source_url):
            if u not in image_seen:
                image_seen.add(u); out['images'].append(u)
    def add_group(name: Any, vals: Any):
        n=textv(name,100)
        if not n: return
        raw=vals if isinstance(vals,list) else [vals]
        cleaned=[]
        for x in raw:
            if isinstance(x,dict):
                for kk in ('name','value','optionValue','option_value','text','label','optionName'):
                    if kk in x:
                        tv=textv(x.get(kk),180)
                        if tv: cleaned.append(tv); break
            else:
                tv=textv(x,180)
                if tv: cleaned.append(tv)
        cleaned=[v for v in dict.fromkeys(cleaned) if v and not re.search(r'선택해?주세요|옵션\s*선택|품절상품 제외',v)]
        if cleaned:
            groups.setdefault(n,[])
            for v in cleaned:
                if v not in groups[n]: groups[n].append(v)

    def contains_pid(obj: Any, depth=0)->bool:
        if not product_id or depth>8: return False
        pid=str(product_id)
        if isinstance(obj,dict):
            for k,v in obj.items():
                nk=keynorm(k)
                if nk in ID_KEYS and str(v).strip()==pid: return True
            return any(contains_pid(v,depth+1) for v in list(obj.values())[:150])
        if isinstance(obj,list):
            return any(contains_pid(v,depth+1) for v in obj[:150])
        return False

    def semantic_score(obj: dict[str,Any])->int:
        kn={keynorm(k):k for k in obj.keys()}
        score=0
        if any(k in kn for k in NAME_KEYS): score+=2
        if any(k in kn for k in PRICE_KEYS): score+=3
        if any(k in kn for k in IMAGE_KEYS): score+=2
        if any(k in kn for k in SHIPPING_KEYS): score+=1
        if any(k in kn for k in OPTION_NAME_KEYS|OPTION_VALUE_KEYS): score+=2
        if any(k in kn for k in STORE_KEYS): score+=1
        if product_id and any(str(obj.get(orig)).strip()==str(product_id) for nk,orig in kn.items() if nk in ID_KEYS): score+=20
        return score

    def collect_candidate_dicts(obj: Any, out_list: list[tuple[int,dict[str,Any]]], depth=0):
        if depth>18: return
        if isinstance(obj,dict):
            sc=semantic_score(obj)
            anchored=contains_pid(obj,0)
            if anchored: sc+=12
            if sc>=4: out_list.append((sc,obj))
            for v in list(obj.values())[:300]: collect_candidate_dicts(v,out_list,depth+1)
        elif isinstance(obj,list):
            for v in obj[:500]: collect_candidate_dicts(v,out_list,depth+1)

    def extract_from(obj: Any, depth=0, trusted=False):
        if depth>14: return
        if isinstance(obj,dict):
            kn={keynorm(k):k for k in obj.keys()}
            local_score=semantic_score(obj)
            local_trusted=trusted or local_score>=6 or (product_id and contains_pid(obj,0))
            if local_trusted:
                if not out.get('product_name'):
                    for nk in ('productname','product_name','goodsname','goods_name','itemname','item_name','producttitle','product_title','goods_title','title','name'):
                        if nk in kn:
                            t=valid_product_name(obj.get(kn[nk]))
                            if t:
                                out['product_name']=t; out['confidence']['product_name']='network_product_object'; break
                if not out.get('store_name'):
                    for nk in STORE_KEYS:
                        if nk in kn:
                            t=valid_store(obj.get(kn[nk]))
                            if t:
                                out['store_name']=t; out['confidence']['store_name']='network_product_object'; break
                if out.get('price') is None:
                    for pk in PRICE_KEYS:
                        if pk in kn:
                            n=explicit_number(obj.get(kn[pk]))
                            if n is not None and n>0:
                                out['price']=n; out['price_key']=pk; out['confidence']['price']='network_product_object'; break
                if out.get('shipping_fee') is None:
                    for nk in SHIPPING_KEYS:
                        if nk in kn:
                            n=explicit_number(obj.get(kn[nk]))
                            if n is not None:
                                out['shipping_fee']=n; out['shipping_key']=nk; out['confidence']['shipping_fee']='network_product_object'; break
                for nk in IMAGE_KEYS:
                    if nk in kn: add_image(obj.get(kn[nk]))
                oname=None; ovals=None
                for nk in OPTION_NAME_KEYS:
                    if nk in kn: oname=obj.get(kn[nk]); break
                for nk in OPTION_VALUE_KEYS:
                    if nk in kn and isinstance(obj.get(kn[nk]),(list,tuple)):
                        ovals=obj.get(kn[nk]); break
                if oname is not None and ovals is not None: add_group(oname,ovals)
                if out.get('availability') is None:
                    for nk in AVAIL_KEYS:
                        if nk in kn:
                            a=_availability(obj.get(kn[nk]))
                            if a!='UNKNOWN': out['availability']=a; break
            for v in list(obj.values())[:300]: extract_from(v,depth+1,local_trusted)
        elif isinstance(obj,list):
            for v in obj[:500]: extract_from(v,depth+1,trusted)

    parsed_blobs=[]
    for blob in blobs or []:
        body=str((blob or {}).get('body') or '')
        obj=_json_load_loose(body)
        if obj is None: continue
        u=str((blob or {}).get('url') or '')
        base_score=sum(2 for h in ('product','detail','option','price','commerce','shopping') if h in u.lower())
        if product_id and str(product_id) in u: base_score+=20
        parsed_blobs.append((base_score,u,obj))

    candidates: list[tuple[int,dict[str,Any]]] = []
    for base,_,obj in parsed_blobs:
        local=[]; collect_candidate_dicts(obj,local)
        candidates.extend((base+sc,d) for sc,d in local)
    # Prefer requested-product anchored/strong product objects; deduplicate by identity.
    seen_ids=set()
    for score,obj in sorted(candidates,key=lambda x:x[0],reverse=True):
        oid=id(obj)
        if oid in seen_ids: continue
        seen_ids.add(oid)
        if score < 7: continue
        extract_from(obj, trusted=(score>=12))
        if out.get('price') is not None and out.get('images') and out.get('option_groups') and out.get('product_name'):
            break

    out['images']=out['images'][:50]
    out['option_groups']=[{'name':k,'values':v[:300]} for k,v in groups.items() if v][:30]
    return out

def _parse_browser_payload(source_url: str, payload: dict[str, Any]) -> ImportedProduct:
    html = str(payload.get("html") or "")
    final_url = str(payload.get("final_url") or source_url)
    status = int(payload.get("status") or 200)
    best = parse_product_html(html, source_url, final_url, status, "LIVE_BROWSER")

    # Product pages often render a shell and fetch the real product object through JSON/XHR.
    # Parse only responses the browser itself legitimately received; no access-control bypass.
    candidates: list[str] = []
    globals_obj = payload.get("globals") or {}
    if globals_obj:
        try:
            candidates.append(json.dumps(globals_obj, ensure_ascii=False))
        except Exception:
            pass
    for blob in payload.get("network_blobs") or []:
        body = str((blob or {}).get("body") or "")
        if body:
            candidates.append(body[:2_000_000])

    for body in candidates[:100]:
        synthetic = f"<html><body><script>{body}</script></body></html>"
        candidate = parse_product_html(synthetic, source_url, final_url, 200, "LIVE_BROWSER_NETWORK")
        best = _better(best, candidate)

    # The rendered shopper-facing DOM is authoritative for Naver sourcing.
    # Earlier builds collected this payload in browser_worker.py but never applied it here,
    # so the UI kept falling back to incomplete HTTP heuristics.
    direct_dom = globals_obj.get("__B2B_DIRECT__") if isinstance(globals_obj, dict) else None
    if isinstance(direct_dom, dict):
        def _clean_direct_text(value: Any) -> str | None:
            text = re.sub(r"\s+", " ", str(value or "")).strip()
            return text or None

        product_name = _clean_direct_text(direct_dom.get("productName"))
        store_name = _clean_direct_text(direct_dom.get("storeName"))
        store_url = _clean_direct_text(direct_dom.get("storeUrl"))
        price = _number(direct_dom.get("price"))
        shipping = _number(direct_dom.get("shippingFee"))
        direct_images = _images(direct_dom.get("imageUrls") or [], final_url)
        direct_groups = direct_dom.get("optionGroups") if isinstance(direct_dom.get("optionGroups"), list) else []
        direct_groups = [g for g in direct_groups if isinstance(g, dict) and (g.get("values") or [])]
        availability = str(direct_dom.get("availability") or "UNKNOWN").upper()

        # Do not manufacture a store name from the URL slug. Only the visible store label is accepted.
        bad_product = re.compile(r"(비밀번호\s*표시|비밀번호|로그인|삭제|검색|장바구니|알림받기|고객센터|접근이\s*제한|에러페이지)", re.I)
        bad_store = re.compile(r"^(?:NAVER|네이버|네이버쇼핑|스마트스토어|브랜드스토어|쇼핑)$", re.I)
        # Direct DOM is authoritative only when it contains a valid value.
        # A missing/invalid direct field must NOT erase a valid OG/JSON-LD fallback.
        if product_name and len(product_name) >= 4 and not bad_product.search(product_name):
            # Preserve the complete original seller title. Some SmartStore layouts expose a
            # shortened direct-DOM/OG title even though another captured source contains the
            # full title. If either title is a prefix of the other, keep the longer original.
            current_name = _clean_direct_text(best.product_name)
            if current_name:
                a = re.sub(r"\s+", " ", current_name).strip()
                b = re.sub(r"\s+", " ", product_name).strip()
                if a.startswith(b) or b.startswith(a):
                    best.product_name = a if len(a) >= len(b) else b
                else:
                    best.product_name = product_name
            else:
                best.product_name = product_name
        if store_name and not bad_store.fullmatch(store_name):
            best.supplier_store_name = store_name
            best.supplier_name = f"네이버-{store_name}"
        if store_url:
            best.supplier_store_url = store_url
        # Override with shopper-visible values when direct capture verified them.
        # When direct capture is missing a field, preserve an already parsed positive
        # browser/structured value instead of erasing it. This is important for SmartStore
        # layouts where OG/JSON-LD can be more stable than the purchase-panel DOM.
        if price is not None and price > 0:
            best.purchase_price = price
        elif best.purchase_price is not None and best.purchase_price <= 0:
            best.purchase_price = None
        if shipping is not None and shipping >= 0:
            best.shipping_fee = shipping
        elif best.shipping_fee is not None and best.shipping_fee < 0:
            best.shipping_fee = None
        if direct_images:
            best.image_urls = direct_images
        if direct_groups:
            best.option_groups = direct_groups
            best.options = list(dict.fromkeys(
                str(v).strip() for g in direct_groups for v in (g.get("values") or []) if str(v).strip()
            ))[:500]
        if availability in {"AVAILABLE", "OUT_OF_STOCK", "UNKNOWN"}:
            best.availability = availability
        best.extraction_method = "LIVE_BROWSER_DOM"

    # V6: recover fields that Naver keeps outside the initially rendered DOM from
    # JSON/XHR responses the same Playwright page already received. Rendered DOM
    # remains first priority; network data only fills fields that are still missing.
    network_fields = _network_naver_fields(source_url, payload.get("network_blobs") or [])
    if not best.product_name and network_fields.get("product_name"):
        nname = _clean_text(str(network_fields["product_name"]), 500)
        if nname and not re.search(r"비밀번호\s*표시|비밀번호|로그인|삭제|검색|장바구니|알림받기|고객센터", nname, re.I):
            best.product_name = nname
    if not best.supplier_store_name and network_fields.get("store_name"):
        network_store = _clean_text(str(network_fields["store_name"]), 150)
        slug_parts=[p for p in urlparse(source_url).path.split("/") if p]
        slug=(slug_parts[0] if slug_parts else "").casefold()
        if network_store and network_store.casefold() != slug and not re.fullmatch(r"(?:NAVER|네이버|네이버쇼핑|스마트스토어|브랜드스토어|쇼핑)", network_store, re.I):
            best.supplier_store_name = network_store
            best.supplier_name = f"네이버-{network_store}"
    if best.purchase_price is None:
        nprice = _number(network_fields.get("price"))
        if nprice is not None and nprice > 0:
            best.purchase_price = nprice
    if best.shipping_fee is None and network_fields.get("shipping_fee") is not None:
        nship = _number(network_fields.get("shipping_fee"))
        if nship is not None and nship >= 0:
            best.shipping_fee = nship
    network_images = _images(network_fields.get("images") or [], final_url)
    # A single rendered main image plus a small product-image array from the same
    # browser session is a safe recovery path. Keep a hard cap to avoid page-wide assets.
    if network_images and (not best.image_urls or len(best.image_urls) <= 1):
        merged=list(dict.fromkeys((best.image_urls or []) + network_images))
        if len(merged) <= 20:
            best.image_urls = merged
    network_groups = network_fields.get("option_groups") if isinstance(network_fields.get("option_groups"), list) else []
    if not best.option_groups and network_groups:
        best.option_groups = network_groups[:30]
        best.options = list(dict.fromkeys(
            str(v).strip() for g in best.option_groups for v in (g.get("values") or []) if str(v).strip()
        ))[:500]
    if best.availability == "UNKNOWN" and network_fields.get("availability") in {"AVAILABLE","OUT_OF_STOCK"}:
        best.availability = network_fields["availability"]
    if any((network_fields.get("price") is not None, network_fields.get("shipping_fee") is not None, network_groups, network_images)):
        best.extraction_method = "LIVE_BROWSER_DOM+NETWORK"

    diag = payload.get("diagnostics") if isinstance(payload.get("diagnostics"), dict) else {}
    diag["network_recovered"] = {
        "product_name": bool(network_fields.get("product_name")),
        "store_name": bool(network_fields.get("store_name")),
        "price": network_fields.get("price") is not None,
        "price_key": network_fields.get("price_key"),
        "shipping": network_fields.get("shipping_fee") is not None,
        "shipping_key": network_fields.get("shipping_key"),
        "images": len(network_images),
        "option_groups": len(network_groups),
    }

    # A blocked/error document must never become a fake product merely because its page title exists.
    title_l = str(payload.get("title") or "").strip().lower()
    html_l = html[:1_000_000].lower()
    is_error_doc = any(x in title_l or x in html_l for x in BLOCKED_MARKERS)
    if is_error_doc and best.confidence < 70:
        best.import_status = "API_REQUIRED"
        best.import_message = "네이버/오픈마켓이 정상 상품 데이터 대신 오류 또는 접근제한 응답을 반환했습니다. 브라우저가 실제로 받은 JSON/XHR까지 확인했지만 핵심 상품 데이터가 없었습니다."
    return best


def _better(a: ImportedProduct, b: ImportedProduct | None) -> ImportedProduct:
    if b is None:
        return a
    # Prefer rendered result if it materially improves extraction.
    if b.confidence > a.confidence:
        return b
    # Merge non-empty details even when direct HTML had a similar score.
    a.product_name = a.product_name or b.product_name
    a.supplier_name = a.supplier_name or b.supplier_name
    a.supplier_store_name = a.supplier_store_name or b.supplier_store_name
    a.supplier_store_url = a.supplier_store_url or b.supplier_store_url
    a.purchase_price = a.purchase_price if a.purchase_price is not None else b.purchase_price
    a.shipping_fee = a.shipping_fee if a.shipping_fee is not None else b.shipping_fee
    a.currency = a.currency or b.currency
    a.source_product_id = a.source_product_id or b.source_product_id
    a.description = a.description or b.description
    a.image_urls = list(dict.fromkeys((a.image_urls or []) + (b.image_urls or [])))[:50]
    a.options = list(dict.fromkeys((a.options or []) + (b.options or [])))[:200]
    if not a.option_groups or (b.option_groups and sum(len(x.get("values") or []) for x in b.option_groups) > sum(len(x.get("values") or []) for x in a.option_groups)):
        a.option_groups = b.option_groups
    if not a.option_variants or (b.option_variants and len(b.option_variants) > len(a.option_variants)):
        a.option_variants = b.option_variants
    if a.availability == "UNKNOWN":
        a.availability = b.availability
    if b.extraction_method == "LIVE_BROWSER" and b.confidence >= a.confidence:
        a.extraction_method = "LIVE_HTTP+LIVE_BROWSER"
    return a


_NAVER_COMMON_UI_RE = re.compile(
    r"비밀번호\s*표시|비밀번호|로그인|삭제|스마트봇\s*상담|고객센터|언어선택|"
    r"한국어|English|中文|日本語|Tiếng\s*Việt|접근이\s*제한|에러페이지",
    re.I,
)
_NAVER_BAD_STORE_RE = re.compile(r"^(?:NAVER|네이버|네이버쇼핑|스마트스토어|브랜드스토어|쇼핑|UNSUPPORTED(?:-네이버)?)$", re.I)


def _sanitize_naver_result(result: ImportedProduct, source_url: str) -> ImportedProduct:
    """Reject NAVER chrome/footer UI that can masquerade as product data.

    Brand-store successes are preserved. SmartStore values are accepted only when they
    look like product data; language/help/password controls are never treated as options.
    """
    if result.product_name:
        pn = _clean_text(str(result.product_name), 500)
        if not pn or _NAVER_COMMON_UI_RE.search(pn) or re.fullmatch(r"(?:NAVER|네이버|상품|옵션|배송)", pn, re.I):
            result.product_name = None

    store = _clean_text(str(result.supplier_store_name or ""), 150)
    slug_parts = [p for p in urlparse(source_url).path.split("/") if p]
    slug = (slug_parts[0] if slug_parts else "").casefold()
    if (not store or _NAVER_BAD_STORE_RE.fullmatch(store) or _NAVER_COMMON_UI_RE.search(store)
            or (slug and store.casefold() == slug)):
        result.supplier_store_name = None
        result.supplier_name = None
    else:
        result.supplier_store_name = store
        result.supplier_name = f"네이버-{store}"

    clean_groups=[]
    for idx,g in enumerate(result.option_groups or [],1):
        if not isinstance(g,dict):
            continue
        name=_clean_text(str(g.get("name") or f"옵션{idx}"),100) or f"옵션{idx}"
        vals=[]
        for raw in g.get("values") or []:
            v=_clean_text(str(raw),200)
            if not v or _NAVER_COMMON_UI_RE.search(v):
                continue
            if re.fullmatch(r"(?:선택|선택해주세요|옵션\s*선택)",v,re.I):
                continue
            if v not in vals:
                vals.append(v)
        if vals and not _NAVER_COMMON_UI_RE.search(name):
            clean_groups.append({"name":name,"values":vals})
    result.option_groups=clean_groups[:30]
    result.options=list(dict.fromkeys(v for g in result.option_groups for v in g.get("values") or []))[:500]

    # Missing is different from a verified zero. Keep price/shipping null unless a source verified it.
    if result.purchase_price is not None and result.purchase_price <= 0:
        result.purchase_price = None
    if result.shipping_fee is not None and result.shipping_fee < 0:
        result.shipping_fee = None
    return result


async def import_product_url(url: str) -> dict[str, Any]:
    url = url.strip()
    await _validate_public_url(url)
    requested_platform = detect_platform(urlparse(url).hostname or "")
    if requested_platform == "UNSUPPORTED":
        supported = ", ".join(SUPPORTED_LABELS.values())
        raise ValueError(f"현재 무재고 소싱 지원 대상 URL이 아닙니다. 지원: {supported}")

    direct: ImportedProduct | None = None
    try:
        html, final_url, status = await _http_fetch(url)
        direct = parse_product_html(html, url, final_url, status, "LIVE_HTTP")
    except ValueError:
        raise
    except Exception:
        direct = None

    # Render with a real browser when direct HTML is incomplete or blocked.
    rendered: ImportedProduct | None = None
    browser_diagnostics: dict[str, Any] = {}
    # Naver sourcing must use the rendered shopper-facing page every time.
    # A direct HTTP shell can score highly while still missing/differing from the values a shopper sees.
    if requested_platform in {"NAVER_SMARTSTORE", "NAVER_SHOPPING"} or direct is None or direct.confidence < 80 or direct.import_status == "API_REQUIRED":
        browser_result = await _browser_fetch(url)
        browser_diagnostics = (browser_result or {}).get("diagnostics") or {}
        if browser_result and browser_result.get("collector_ok"):
            rendered = _parse_browser_payload(url, browser_result)

    if direct is None and rendered is None:
        raise ValueError(
            "실제 상품 페이지에 접근하지 못했습니다. Playwright Chromium 설치 또는 해당 오픈마켓의 공식 API/제휴 권한이 필요합니다."
        )

    # For Naver, rendered DOM is authoritative. Do not let HTTP/meta heuristics overwrite
    # the exact visible title/store/price/shipping/gallery/options.
    if requested_platform in {"NAVER_SMARTSTORE", "NAVER_SHOPPING"} and rendered is not None:
        result = rendered
    else:
        result = _better(direct or rendered, rendered if direct is not None else None)

    # The marketplace identity belongs to the URL the seller pasted, not to an
    # error/redirect page returned by the marketplace.  A Naver error shell can
    # redirect to another host and previously made the preview say UNSUPPORTED.
    result.platform = requested_platform
    result.source_url = url
    result.source_product_id = result.source_product_id or product_id_from_url(url, requested_platform)
    if requested_platform in {"NAVER_SMARTSTORE", "NAVER_SHOPPING"}:
        result = _sanitize_naver_result(result, url)

    # Store URL may be derived from the source URL, but the store *name* must be the
    # actual visible marketplace label. Never turn a slug such as "hahaliving" into
    # a fake display name.
    if not result.supplier_store_url:
        result.supplier_store_url = _store_url(url, requested_platform)
    if requested_platform not in {"NAVER_SMARTSTORE", "NAVER_SHOPPING"}:
        if not result.supplier_store_name:
            result.supplier_store_name = _extract_store_name([], "", {}, url, requested_platform)
        if not result.supplier_name and result.supplier_store_name:
            result.supplier_name = f"{_platform_prefix(requested_platform)}-{result.supplier_store_name}"

    # Never invent missing source data.
    result.live_fetch = True
    if result.import_status == "API_REQUIRED" and rendered is None:
        stage = str(browser_diagnostics.get("stage") or "")
        error = str(browser_diagnostics.get("error") or "")
        if "Executable doesn't exist" in error or "playwright install" in error.lower():
            result.import_message += " 서버 브라우저가 설치되지 않았습니다. 실행.bat에서 Chromium 설치를 완료해야 합니다."
        elif stage:
            result.import_message += f" 서버 브라우저 자동진단 단계: {stage}."
    payload = result.to_dict()
    payload["collector_diagnostics"] = browser_diagnostics
    payload["rendered_collector_used"] = rendered is not None
    return payload
