from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from pathlib import Path
from typing import Dict, Any, Optional, List
import os
import hashlib
import secrets
import httpx
from bs4 import BeautifulSoup
from supabase import create_client

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "").strip()
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
ADMIN_MASTER_CODE = (os.getenv("ADMIN_MASTER_CODE", "").strip() or "K9FQ7M2XPA").strip()

if not SUPABASE_URL or not SUPABASE_ANON_KEY or not SUPABASE_SERVICE_ROLE_KEY:
    raise RuntimeError("Missing SUPABASE_URL / SUPABASE_ANON_KEY / SUPABASE_SERVICE_ROLE_KEY in .env")

sb_admin = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

app = FastAPI()
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# --------------------
# URL → 마켓 자동 감지(도메인 기반)
# --------------------
MARKET_DOMAIN_MAP = [
    ("coupang.com", "coupang"),
    ("smartstore.naver.com", "naver"),
    ("shopping.naver.com", "naver"),
    ("11st.co.kr", "11st"),
    ("gmarket.co.kr", "gmarket"),
]


def sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _to_int(v, default=0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def detect_market_from_url(url: str) -> str:
    u = (url or "").lower()
    for dom, mk in MARKET_DOMAIN_MAP:
        if dom in u:
            return mk
    return "etc"


async def fetch_title(url: str) -> Optional[str]:
    """
    URL에서 og:title → title 순으로 시도.
    (차단/봇방지/동적렌더링이면 실패할 수 있음)
    """
    if not url:
        return None

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    try:
        async with httpx.AsyncClient(timeout=8, follow_redirects=True) as client:
            r = await client.get(url, headers=headers)

        if r.status_code != 200:
            return None

        soup = BeautifulSoup(r.text, "html.parser")

        og = soup.find("meta", property="og:title")
        if og and og.get("content"):
            t = og["content"].strip()
            return t[:200] if t else None

        title = soup.find("title")
        if title and title.text:
            t = title.text.strip()
            return t[:200] if t else None

        return None
    except Exception:
        return None


async def get_user_from_token(access_token: str) -> dict:
    """
    Supabase Auth 토큰 검증 (/auth/v1/user)
    """
    url = f"{SUPABASE_URL}/auth/v1/user"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
    }
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url, headers=headers)
    if r.status_code != 200:
        raise HTTPException(401, "Invalid or expired token")
    return r.json()


async def require_auth(req: Request) -> dict:
    auth = req.headers.get("authorization") or ""
    if not auth.lower().startswith("bearer "):
        raise HTTPException(401, "Missing bearer token")
    token = auth.split(" ", 1)[1].strip()
    return await get_user_from_token(token)


def get_user_security(user_id: str) -> Optional[Dict[str, Any]]:
    res = sb_admin.table("user_security").select("*").eq("user_id", user_id).execute()
    rows = res.data or []
    return rows[0] if rows else None


def is_admin_user(user_id: str) -> bool:
    sec = get_user_security(user_id)
    return bool(sec) and (sec.get("role") == "admin")


async def require_admin(req: Request) -> dict:
    user = await require_auth(req)
    user_id = user.get("id")
    if not user_id:
        raise HTTPException(401, "No user id")
    if not is_admin_user(user_id):
        raise HTTPException(403, "Admin only")
    return user


def get_admin_settings() -> Dict[str, Any]:
    try:
        res = sb_admin.table("admin_settings").select("*").eq("id", 1).execute()
        row = (res.data or [None])[0]
        if not row:
            return {"min_profit": 500, "safety_buffer_rate": 0.01}
        return {
            "min_profit": int(row.get("min_profit") or 500),
            "safety_buffer_rate": float(row.get("safety_buffer_rate") or 0.01),
        }
    except Exception:
        return {"min_profit": 500, "safety_buffer_rate": 0.01}


def get_fee_rule(market: str, category: str) -> Dict[str, Any]:
    """
    market+category 룰 우선, 없으면 market+unknown, 없으면 etc+unknown.
    """
    m = (market or "etc").lower().strip()
    c = (category or "unknown").lower().strip()

    # 1) market + category
    res = sb_admin.table("fee_rules").select("*").eq("market", m).eq("category", c).execute()
    rows = res.data or []
    if rows:
        row = rows[0]
        return {"base_rate": float(row["base_rate"]), "category_rate": float(row["category_rate"])}

    # 2) market + unknown
    res = sb_admin.table("fee_rules").select("*").eq("market", m).eq("category", "unknown").execute()
    rows = res.data or []
    if rows:
        row = rows[0]
        return {"base_rate": float(row["base_rate"]), "category_rate": float(row["category_rate"])}

    # 3) etc + unknown
    res = sb_admin.table("fee_rules").select("*").eq("market", "etc").eq("category", "unknown").execute()
    rows = res.data or []
    if rows:
        row = rows[0]
        return {"base_rate": float(row["base_rate"]), "category_rate": float(row["category_rate"])}

    return {"base_rate": 0.12, "category_rate": 0.0}


def calc(
    market: str,
    category: str,
    tax_type: str,
    buy_price: int,
    sell_price: int,
    shipping_fee: int,
) -> Dict[str, Any]:
    """
    서버 단일 계산(보수 계산).
    commission_rate = base_rate + category_rate + safety_buffer_rate
    commission_fee = floor(sell_price * commission_rate)

    vat_fee(보수):
      - simple: 0
      - general: commission_fee의 10% (수수료에 대한 VAT 가정)
        * 실제 마켓/정산 방식 따라 다를 수 있음 → 보수 계산 유지

    total_cost = buy + shipping + commission + vat
    profit = sell - total_cost
    margin_rate = profit / sell
    decision = profit >= min_profit ? SELL : STOP
    """
    settings = get_admin_settings()
    min_profit = settings["min_profit"]
    safety = settings["safety_buffer_rate"]

    rule = get_fee_rule(market, category)
    base_rate = float(rule["base_rate"])
    cat_rate = float(rule["category_rate"])

    commission_rate = base_rate + cat_rate + float(safety)
    commission_fee = int(sell_price * commission_rate)

    t = (tax_type or "simple").lower().strip()
    if t == "general":
        vat_fee = int(commission_fee * 0.10)
    else:
        vat_fee = 0

    total_cost = buy_price + shipping_fee + commission_fee + vat_fee
    profit = sell_price - total_cost

    margin_rate = (profit / sell_price) if sell_price > 0 else 0.0

    if profit >= min_profit:
        decision, reason = "SELL", "PROFIT_OK"
    else:
        decision, reason = "STOP", "PROFIT_TOO_LOW"

    return {
        "min_profit": min_profit,
        "safety_buffer_rate": float(safety),
        "base_rate": base_rate,
        "category_rate": cat_rate,
        "commission_rate": commission_rate,
        "commission_fee": commission_fee,
        "vat_fee": vat_fee,
        "total_cost": total_cost,
        "profit": profit,
        "margin_rate": float(margin_rate),
        "decision": decision,
        "reason": reason,
    }


# --------------------
# Pages
# --------------------
@app.get("/")
@app.get("/login")
def login_page():
    return FileResponse(STATIC_DIR / "login.html")


@app.get("/code")
def code_page():
    return FileResponse(STATIC_DIR / "code.html")


@app.get("/admin")
def admin_page():
    return FileResponse(STATIC_DIR / "admin.html")


@app.get("/admin/dashboard")
def admin_dashboard_page():
    return FileResponse(STATIC_DIR / "admin_dashboard.html")


@app.get("/user")
def user_page():
    return FileResponse(STATIC_DIR / "user.html")


# --------------------
# Public config
# --------------------
@app.get("/api/public-config")
def public_config():
    settings = get_admin_settings()
    return {
        "supabaseUrl": SUPABASE_URL,
        "supabaseAnonKey": SUPABASE_ANON_KEY,
        "minProfitDefault": settings["min_profit"],
        "safetyBufferRate": settings["safety_buffer_rate"],
        "markets": ["coupang", "naver", "11st", "gmarket", "etc"],
        "categoriesDefault": ["unknown", "electronics", "fashion", "food", "beauty", "sports", "home", "etc"],
    }


# --------------------
# Access code verify
# - 1) 마스터 코드(K9FQ7M2XPA)면 admin 부트스트랩
# - 2) 그 외: access_codes 풀(발급된 코드) 검사 → 사용 처리 + admin 등록
# - 3) 이미 user_security에 코드 해시가 있으면(기존 방식) 그것도 호환
# --------------------
@app.post("/api/verify-access-code")
async def verify_access_code(req: Request):
    user = await require_auth(req)
    user_id = user.get("id")
    if not user_id:
        raise HTTPException(401, "No user id")

    body = await req.json()
    code = (body.get("code") or "").strip()
    if not code:
        raise HTTPException(400, "Code required")

    code_hash = sha256(code)

    # 1) 마스터 코드면 admin 부트스트랩
    if code == ADMIN_MASTER_CODE:
        sb_admin.table("user_security").upsert({
            "user_id": user_id,
            "role": "admin",
            "access_code_hash": code_hash,
        }).execute()
        return {"success": True, "role": "admin", "bootstrapped": True}

    # 2) 발급 풀(access_codes)에서 미사용 코드 찾기
    pool = sb_admin.table("access_codes").select("*") \
        .eq("code_hash", code_hash).eq("used", False).limit(1).execute()
    rows = pool.data or []
    if rows:
        row = rows[0]
        role = (row.get("role") or "admin").lower().strip()

        # 사용 처리
        sb_admin.table("access_codes").update({
            "used": True,
            "used_by": user_id,
            "used_at": "now()"
        }).eq("id", row["id"]).execute()

        # user_security 등록/업데이트
        sb_admin.table("user_security").upsert({
            "user_id": user_id,
            "role": role,
            "access_code_hash": code_hash,
        }).execute()

        return {"success": True, "role": role, "enrolled": True}

    # 3) 호환: 기존 user_security에 해시가 있는 경우
    sec = get_user_security(user_id)
    if not sec:
        raise HTTPException(403, "Not enrolled. Ask admin for an access code.")

    expected = (sec.get("access_code_hash") or "").strip()
    if not expected:
        raise HTTPException(403, "No access code set for this account")

    if code_hash != expected:
        raise HTTPException(403, "Invalid access code")

    role = sec.get("role") or "user"
    return {"success": True, "role": role}


# --------------------
# Admin APIs
# --------------------
@app.get("/api/admin/settings")
async def admin_get_settings(req: Request):
    await require_admin(req)
    return get_admin_settings()


@app.post("/api/admin/set-settings")
async def admin_set_settings(req: Request):
    await require_admin(req)
    body = await req.json()

    min_profit = body.get("min_profit")
    safety_buffer_rate = body.get("safety_buffer_rate")

    if min_profit is None or not isinstance(min_profit, int) or min_profit <= 0:
        raise HTTPException(400, "Invalid min_profit (int > 0)")

    try:
        sbr = float(safety_buffer_rate)
    except Exception:
        raise HTTPException(400, "Invalid safety_buffer_rate (number)")

    if sbr < 0 or sbr > 0.10:
        raise HTTPException(400, "safety_buffer_rate out of range (0~0.10)")

    sb_admin.table("admin_settings").upsert({
        "id": 1,
        "min_profit": min_profit,
        "safety_buffer_rate": sbr,
    }).execute()
    return {"success": True}


@app.post("/api/admin/generate-access-code")
async def admin_generate_access_code(req: Request):
    """
    관리자가 "다른 계정에게 줄" 개인코드 발급
    - DB에는 해시만 저장
    - 코드 원문은 응답에서 딱 1번만 보여줌
    """
    await require_admin(req)
    body = await req.json()
    role = (body.get("role") or "admin").lower().strip()
    if role not in ["admin", "user"]:
        raise HTTPException(400, "role must be admin/user")

    raw_code = secrets.token_hex(5).upper()  # 10 hex = 10 chars
    code_hash = sha256(raw_code)

    sb_admin.table("access_codes").insert({
        "code_hash": code_hash,
        "role": role,
        "used": False
    }).execute()

    return {"success": True, "access_code": raw_code, "role": role}


@app.get("/api/admin/fee-categories")
async def admin_fee_categories(req: Request, market: str = "etc"):
    """
    마켓별 카테고리 목록(룰 테이블 기준)
    """
    await require_admin(req)
    m = (market or "etc").lower().strip()
    res = sb_admin.table("fee_rules").select("category").eq("market", m).execute()
    cats = sorted(list({(r.get("category") or "unknown") for r in (res.data or [])}))
    if "unknown" not in cats:
        cats = ["unknown"] + cats
    return {"market": m, "categories": cats}


@app.post("/api/admin/analyze-url")
async def admin_analyze_url(req: Request):
    """
    URL 입력 → (1) 마켓 자동 감지 (2) 상품명(title) 추출 시도
    """
    await require_admin(req)
    body = await req.json()
    url = (body.get("url") or "").strip()
    if not url:
        raise HTTPException(400, "url required")

    market = detect_market_from_url(url)
    title = await fetch_title(url)

    return {"success": True, "url": url, "market": market, "name_guess": title}


@app.post("/api/admin/items")
async def admin_add_item(req: Request):
    user = await require_admin(req)
    owner_user_id = user["id"]

    body = await req.json()

    url = (body.get("url") or "").strip()
    name = (body.get("name") or "").strip()
    market = (body.get("market") or detect_market_from_url(url)).lower().strip()
    category = (body.get("category") or "unknown").lower().strip()
    tax_type = (body.get("tax_type") or "simple").lower().strip()

    buy_price = _to_int(body.get("buy_price"))
    sell_price = _to_int(body.get("sell_price"))
    shipping_fee = _to_int(body.get("shipping_fee"), 0)

    if buy_price <= 0 or sell_price <= 0:
        raise HTTPException(400, "buy_price and sell_price must be positive")
    if shipping_fee < 0:
        raise HTTPException(400, "shipping_fee must be >= 0")
    if tax_type not in ["simple", "general"]:
        raise HTTPException(400, "tax_type must be simple/general")

    # 이름이 비어있으면 URL에서 추출을 한번 더 시도(실패해도 OK)
    if not name and url:
        name_guess = await fetch_title(url)
        if name_guess:
            name = name_guess

    result = calc(market, category, tax_type, buy_price, sell_price, shipping_fee)

    payload = {
        "owner_user_id": owner_user_id,
        "url": url,
        "name": name,
        "market": market,
        "category": category,
        "tax_type": tax_type,
        "buy_price": buy_price,
        "sell_price": sell_price,
        "shipping_fee": shipping_fee,
        "commission_rate": result["commission_rate"],
        "commission_fee": result["commission_fee"],
        "vat_fee": result["vat_fee"],
        "total_cost": result["total_cost"],
        "profit": result["profit"],
        "margin_rate": result["margin_rate"],
        "decision": result["decision"],
        "reason": result["reason"],
    }

    inserted = sb_admin.table("items").insert(payload).execute()
    item = (inserted.data[0] if inserted.data else payload)

    return JSONResponse({
        "success": True,
        "calc": result,
        "item": item
    })


@app.get("/api/admin/items")
async def admin_list_items(req: Request):
    await require_admin(req)
    rows = sb_admin.table("items").select("*").order("id", desc=True).limit(200).execute()
    return {"items": rows.data or []}


@app.get("/api/admin/dashboard")
async def admin_dashboard(req: Request):
    await require_admin(req)
    settings = get_admin_settings()

    rows = sb_admin.table("items").select("id,name,market,category,tax_type,profit,margin_rate,decision,reason,url,created_at").order("id", desc=True).limit(300).execute()
    items = rows.data or []

    total = len(items)
    sell = sum(1 for x in items if x.get("decision") == "SELL")
    stop = total - sell

    return {
        "min_profit": settings["min_profit"],
        "safety_buffer_rate": settings["safety_buffer_rate"],
        "total": total,
        "sell": sell,
        "stop": stop,
        "items": items
    }
