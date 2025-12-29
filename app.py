from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from pathlib import Path
from typing import Dict, Any
import os
import hashlib
import httpx
from supabase import create_client

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "").strip()
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()

# ✅ 정훈이 이미 확정한 관리자 개인코드
DEFAULT_ADMIN_CODE = "K9FQ7M2XPA"

# (선택) .env에 있으면 그걸 쓰고, 없으면 DEFAULT_ADMIN_CODE 사용
ADMIN_MASTER_CODE = os.getenv("ADMIN_MASTER_CODE", "").strip() or DEFAULT_ADMIN_CODE

if not SUPABASE_URL or not SUPABASE_ANON_KEY or not SUPABASE_SERVICE_ROLE_KEY:
    raise RuntimeError("Missing SUPABASE_URL / SUPABASE_ANON_KEY / SUPABASE_SERVICE_ROLE_KEY in .env")

sb_admin = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

app = FastAPI()
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# --------------------
# 보수 계산 룰(초기값은 코드에 둠. 다음 단계에서 DB 룰테이블로 이관 가능)
# --------------------
MARKET_BASE_RATE = {
    "coupang": 0.12,
    "naver": 0.10,
    "gmarket": 0.12,
    "11st": 0.12,
    "etc": 0.12,
}

DEFAULT_MIN_PROFIT = 500
DEFAULT_SAFETY_BUFFER_RATE = 0.01


def sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _to_int(v, default=0) -> int:
    try:
        return int(v)
    except Exception:
        return default


async def get_user_from_token(access_token: str) -> dict:
    """
    access_token 유효성 검증:
    service_role key를 apikey로 사용하고, Authorization에는 유저 토큰을 넣어 /auth/v1/user 호출
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


def get_admin_settings() -> Dict[str, Any]:
    """
    admin_settings 단일 row(id=1)
    """
    try:
        res = sb_admin.table("admin_settings").select("*").eq("id", 1).execute()
        row = (res.data or [None])[0]
        if not row:
            return {"min_profit": DEFAULT_MIN_PROFIT, "safety_buffer_rate": DEFAULT_SAFETY_BUFFER_RATE}
        return {
            "min_profit": int(row.get("min_profit") or DEFAULT_MIN_PROFIT),
            "safety_buffer_rate": float(row.get("safety_buffer_rate") or DEFAULT_SAFETY_BUFFER_RATE),
        }
    except Exception:
        return {"min_profit": DEFAULT_MIN_PROFIT, "safety_buffer_rate": DEFAULT_SAFETY_BUFFER_RATE}


def calc(market: str, tax_type: str, buy_price: int, sell_price: int, shipping_fee: int) -> Dict[str, Any]:
    """
    서버 단일 계산(보수 계산).
    commission_rate = market_base + safety_buffer
    vat_fee:
      - simple: 0 (단순화)
      - general: commission_fee의 10% (보수 가정)
    """
    settings = get_admin_settings()
    min_profit = settings["min_profit"]
    safety_buffer = settings["safety_buffer_rate"]

    m = (market or "etc").lower().strip()
    base = float(MARKET_BASE_RATE.get(m, MARKET_BASE_RATE["etc"]))

    commission_rate = base + float(safety_buffer)
    commission_fee = int(sell_price * commission_rate)

    t = (tax_type or "simple").lower().strip()
    if t == "general":
        vat_fee = int(commission_fee * 0.10)
    else:
        vat_fee = 0

    profit = sell_price - buy_price - shipping_fee - commission_fee - vat_fee

    if profit >= min_profit:
        decision, reason = "SELL", "PROFIT_OK"
    else:
        decision, reason = "STOP", "PROFIT_TOO_LOW"

    return {
        "min_profit": min_profit,
        "safety_buffer_rate": safety_buffer,
        "commission_rate": commission_rate,
        "commission_fee": commission_fee,
        "vat_fee": vat_fee,
        "profit": profit,
        "decision": decision,
        "reason": reason,
    }


def get_user_security(user_id: str) -> Dict[str, Any] | None:
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
# Public config (프론트에서 Supabase client 생성용)
# --------------------
@app.get("/api/public-config")
def public_config():
    settings = get_admin_settings()
    return {
        "supabaseUrl": SUPABASE_URL,
        "supabaseAnonKey": SUPABASE_ANON_KEY,
        "markets": list(MARKET_BASE_RATE.keys()),
        "minProfitDefault": settings["min_profit"],
        "safetyBufferRate": settings["safety_buffer_rate"],
        "marketBaseRates": MARKET_BASE_RATE,
    }


# --------------------
# 개인코드 인증 & admin 부트스트랩/검증
# - ✅ 최초 admin 등록도 K9FQ7M2XPA로 처리
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

    # 1) 부트스트랩 코드(= K9FQ7M2XPA)면 즉시 admin 등록
    if code == ADMIN_MASTER_CODE:
        sb_admin.table("user_security").upsert({
            "user_id": user_id,
            "role": "admin",
            "access_code_hash": sha256(ADMIN_MASTER_CODE),
        }).execute()
        return {"success": True, "role": "admin", "bootstrapped": True}

    # 2) 일반 검증: user_security의 access_code_hash와 비교
    sec = get_user_security(user_id)
    if not sec:
        raise HTTPException(403, "Not enrolled. Use the admin code to enroll once.")

    expected = (sec.get("access_code_hash") or "").strip()
    if not expected:
        raise HTTPException(403, "No access code set for this account")

    if sha256(code) != expected:
        raise HTTPException(403, "Invalid access code")

    role = sec.get("role") or "user"
    return {"success": True, "role": role}


# --------------------
# 관리자: 설정(SELL 기준/버퍼) 조회/변경
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


# --------------------
# 관리자: 상품 추가(자동 계산 + DB 저장)
# --------------------
@app.post("/api/admin/items")
async def admin_add_item(req: Request):
    user = await require_admin(req)
    owner_user_id = user["id"]

    body = await req.json()
    url = (body.get("url") or "").strip()
    market = (body.get("market") or "etc").strip().lower()
    tax_type = (body.get("tax_type") or "simple").strip().lower()

    buy_price = _to_int(body.get("buy_price"))
    sell_price = _to_int(body.get("sell_price"))
    shipping_fee = _to_int(body.get("shipping_fee"), 0)

    if buy_price <= 0 or sell_price <= 0:
        raise HTTPException(400, "buy_price and sell_price must be positive")
    if shipping_fee < 0:
        raise HTTPException(400, "shipping_fee must be >= 0")
    if tax_type not in ["simple", "general"]:
        raise HTTPException(400, "tax_type must be simple/general")

    result = calc(market, tax_type, buy_price, sell_price, shipping_fee)

    payload = {
        "owner_user_id": owner_user_id,
        "url": url,
        "market": market,
        "tax_type": tax_type,
        "buy_price": buy_price,
        "sell_price": sell_price,
        "shipping_fee": shipping_fee,
        "commission_rate": result["commission_rate"],
        "commission_fee": result["commission_fee"],
        "vat_fee": result["vat_fee"],
        "profit": result["profit"],
        "decision": result["decision"],
        "reason": result["reason"],
    }

    inserted = sb_admin.table("items").insert(payload).execute()
    item = (inserted.data[0] if inserted.data else payload)

    return JSONResponse({
        "success": True,
        "settings": {
            "min_profit": result["min_profit"],
            "safety_buffer_rate": result["safety_buffer_rate"],
        },
        "item": item
    })


@app.get("/api/admin/items")
async def admin_list_items(req: Request):
    await require_admin(req)
    rows = sb_admin.table("items").select("*").order("id", desc=True).limit(100).execute()
    return {"items": rows.data or []}


# --------------------
# 관리자: 대시보드 데이터
# --------------------
@app.get("/api/admin/dashboard")
async def admin_dashboard(req: Request):
    await require_admin(req)
    settings = get_admin_settings()

    rows = sb_admin.table("items").select("id,profit,decision,reason,url,market,tax_type,created_at").order("id", desc=True).limit(200).execute()
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

