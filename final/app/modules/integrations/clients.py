from __future__ import annotations

import base64
import hashlib
import hmac
import os
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

import httpx

NAVER_BASE_URL = "https://api.commerce.naver.com"
COUPANG_BASE_URL = "https://api-gateway.coupang.com"

# Process-local token cache. Naver tokens are valid for 3 hours; keep a small safety margin.
_NAVER_TOKEN_CACHE: dict[str, Any] = {"key": None, "token": None, "expires_at": 0.0}


def _env(name: str) -> str:
    return os.getenv(name, "").strip()


def integration_config() -> dict[str, dict[str, Any]]:
    naver_type = (_env("NAVER_COMMERCE_TOKEN_TYPE") or "SELF").upper()
    return {
        "NAVER": {
            "configured": bool(_env("NAVER_COMMERCE_CLIENT_ID") and _env("NAVER_COMMERCE_CLIENT_SECRET")),
            "client_id": bool(_env("NAVER_COMMERCE_CLIENT_ID")),
            "client_secret": bool(_env("NAVER_COMMERCE_CLIENT_SECRET")),
            "token_type": naver_type,
            "account_id": bool(_env("NAVER_COMMERCE_ACCOUNT_ID")) if naver_type == "SELLER" else False,
            "mode": "내 스토어 애플리케이션" if naver_type == "SELF" else "솔루션 판매자 연동",
        },
        "COUPANG": {
            "configured": bool(_env("COUPANG_ACCESS_KEY") and _env("COUPANG_SECRET_KEY") and _env("COUPANG_VENDOR_ID")),
            "access_key": bool(_env("COUPANG_ACCESS_KEY")),
            "secret_key": bool(_env("COUPANG_SECRET_KEY")),
            "vendor_id": _env("COUPANG_VENDOR_ID") or None,
        },
        "11ST": {
            "configured": False,
            "note": "11번가 연동은 다음 단계에서 추가 예정",
        },
    }


def naver_signature(client_id: str, client_secret: str, timestamp_ms: int) -> str:
    try:
        import bcrypt  # type: ignore
    except ImportError as exc:
        raise RuntimeError("네이버 커머스API 인증에 bcrypt 패키지가 필요합니다. requirements.txt를 다시 설치하세요.") from exc

    password = f"{client_id}_{timestamp_ms}".encode("utf-8")
    hashed = bcrypt.hashpw(password, client_secret.encode("utf-8"))
    return base64.b64encode(hashed).decode("utf-8")


def _naver_auth_config() -> tuple[str, str, str, str]:
    client_id = _env("NAVER_COMMERCE_CLIENT_ID")
    client_secret = _env("NAVER_COMMERCE_CLIENT_SECRET")
    token_type = (_env("NAVER_COMMERCE_TOKEN_TYPE") or "SELF").upper()
    account_id = _env("NAVER_COMMERCE_ACCOUNT_ID")

    if not client_id or not client_secret:
        raise RuntimeError("네이버 API 키가 설정되지 않았습니다. '네이버_API_설정.bat'을 먼저 실행하세요.")
    if token_type not in {"SELF", "SELLER"}:
        raise RuntimeError("NAVER_COMMERCE_TOKEN_TYPE은 SELF 또는 SELLER만 사용할 수 있습니다.")
    # Naver's current spec: own-store applications always use SELF and must NOT send account_id.
    if token_type == "SELLER" and not account_id:
        raise RuntimeError("SELLER 토큰에는 NAVER_COMMERCE_ACCOUNT_ID(판매자 UID)가 필요합니다.")
    return client_id, client_secret, token_type, account_id


def _naver_error_message(status: int, text: str) -> str:
    compact = (text or "").replace("\n", " ")[:500]
    if status == 401:
        return f"네이버 인증 실패(401). 애플리케이션 ID/시크릿과 토큰 규격을 확인하세요. {compact}"
    if status == 403:
        return f"네이버 권한 거부(403). API 그룹 권한, 등록한 API 호출 IP, 스토어 상태를 확인하세요. {compact}"
    return f"네이버 API 오류 ({status}): {compact}"


async def naver_access_token(*, force_refresh: bool = False) -> str:
    client_id, client_secret, token_type, account_id = _naver_auth_config()
    cache_key = f"{client_id}:{token_type}:{account_id if token_type == 'SELLER' else ''}"
    now = time.time()
    if not force_refresh and _NAVER_TOKEN_CACHE.get("key") == cache_key and _NAVER_TOKEN_CACHE.get("token") and float(_NAVER_TOKEN_CACHE.get("expires_at") or 0) > now + 60:
        return str(_NAVER_TOKEN_CACHE["token"])

    ts = int(time.time() * 1000)
    payload: dict[str, str] = {
        "client_id": client_id,
        "timestamp": str(ts),
        "client_secret_sign": naver_signature(client_id, client_secret, ts),
        "grant_type": "client_credentials",
        "type": token_type,
    }
    # IMPORTANT: SELF must omit account_id completely. SELLER must include it.
    if token_type == "SELLER":
        payload["account_id"] = account_id

    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(f"{NAVER_BASE_URL}/external/v1/oauth2/token", data=payload, headers=headers)
    if response.status_code >= 400:
        raise RuntimeError(_naver_error_message(response.status_code, response.text))
    body = response.json()
    token = body.get("access_token")
    if not token:
        raise RuntimeError("네이버 인증 응답에 access_token이 없습니다.")
    expires_in = int(body.get("expires_in") or 10800)
    _NAVER_TOKEN_CACHE.update({"key": cache_key, "token": str(token), "expires_at": now + max(60, expires_in - 120)})
    return str(token)


async def naver_request(method: str, path: str, *, params: dict | None = None, json: Any = None) -> Any:
    async def _call(token: str) -> httpx.Response:
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            return await client.request(method.upper(), f"{NAVER_BASE_URL}{path}", params=params, json=json, headers=headers)

    token = await naver_access_token()
    response = await _call(token)
    # Official guide recommends one token refresh/retry for GW.AUTHN/401.
    if response.status_code == 401:
        token = await naver_access_token(force_refresh=True)
        response = await _call(token)
    if response.status_code >= 400:
        raise RuntimeError(_naver_error_message(response.status_code, response.text))
    if response.status_code == 204 or not response.content:
        return {}
    return response.json()


async def naver_account_info() -> Any:
    return await naver_request("GET", "/external/v1/seller/account")


async def naver_product(origin_product_no: str) -> Any:
    product_no = str(origin_product_no or "").strip()
    if not product_no.isdigit():
        raise RuntimeError("원상품번호는 숫자만 입력하세요.")
    return await naver_request("GET", f"/external/v2/products/origin-products/{product_no}")


def coupang_authorization(method: str, path: str, query: str, access_key: str, secret_key: str, *, now: datetime | None = None) -> str:
    current = now or datetime.now(timezone.utc)
    signed_date = current.strftime("%y%m%dT%H%M%SZ")
    message = f"{signed_date}{method.upper()}{path}{query}"
    signature = hmac.new(secret_key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"CEA algorithm=HmacSHA256, access-key={access_key}, signed-date={signed_date}, signature={signature}"


async def coupang_request(method: str, path: str, *, params: dict | None = None, json: Any = None) -> Any:
    access_key = _env("COUPANG_ACCESS_KEY")
    secret_key = _env("COUPANG_SECRET_KEY")
    if not access_key or not secret_key:
        raise RuntimeError("COUPANG_ACCESS_KEY / COUPANG_SECRET_KEY 설정이 필요합니다.")
    query = urlencode(params or {}, doseq=True)
    authorization = coupang_authorization(method, path, query, access_key, secret_key)
    headers = {"Authorization": authorization, "Content-Type": "application/json;charset=UTF-8"}
    url = f"{COUPANG_BASE_URL}{path}"
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.request(method.upper(), url, params=params, json=json, headers=headers)
    if response.status_code >= 400:
        raise RuntimeError(f"쿠팡 API 오류 ({response.status_code}): {response.text[:400]}")
    if not response.content:
        return {}
    return response.json()


async def test_naver_connection() -> dict[str, Any]:
    body = await naver_account_info()
    return {"ok": True, "message": "네이버 커머스API 실연결 성공", "account": body, "token_type": (_env("NAVER_COMMERCE_TOKEN_TYPE") or "SELF").upper()}


async def test_coupang_connection() -> dict[str, Any]:
    vendor_id = _env("COUPANG_VENDOR_ID")
    if not vendor_id:
        raise RuntimeError("COUPANG_VENDOR_ID 설정이 필요합니다.")
    path = f"/v2/providers/openapi/apis/api/v5/vendors/{vendor_id}/ordersheets"
    now = datetime.now().astimezone()
    iso = now.strftime("%Y-%m-%dT%H:%M%z")
    iso = iso[:-2] + ":" + iso[-2:]
    params = {"createdAtFrom": iso, "createdAtTo": iso, "status": "ACCEPT", "searchType": "timeFrame"}
    body = await coupang_request("GET", path, params=params)
    return {"ok": True, "message": "쿠팡 Open API 인증/호출 성공", "response_code": body.get("code") if isinstance(body, dict) else None}
