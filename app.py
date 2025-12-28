from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from supabase import create_client
from pathlib import Path
import os
import io
import hashlib
from datetime import datetime

from openpyxl import Workbook


# ======================
# Paths
# ======================
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

# ======================
# Supabase
# ======================
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    raise RuntimeError("SUPABASE_URL / SUPABASE_ANON_KEY 환경변수가 없습니다. (.env 또는 Render 환경변수 확인)")

supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)


def db_for_token(access_token: str):
    """
    RLS가 적용된 테이블 쿼리를 위해 user token을 postgrest에 주입하는 클라이언트
    """
    client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    client.postgrest.auth(access_token)
    return client


# ======================
# Auth helpers
# ======================
def get_bearer_token(request: Request) -> str:
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(401, "인증 정보가 없습니다.")
    return auth.replace("Bearer ", "").strip()


async def require_user(request: Request):
    token = get_bearer_token(request)

    try:
        user = supabase.auth.get_user(token).user
    except Exception:
        raise HTTPException(401, "유효하지 않은 토큰")

    client = db_for_token(token)
    sec = (
        client
        .table("user_security")
        .select("role")
        .eq("user_id", user.id)
        .single()
        .execute()
    )
    if not sec.data:
        raise HTTPException(403, "권한 정보(user_security)가 없습니다. (관리자에게 개인코드/권한 등록 요청)")

    role = sec.data.get("role", "user")
    return token, user, role


async def require_admin(request: Request):
    token, user, role = await require_user(request)
    if role != "admin":
        raise HTTPException(403, "관리자 권한이 필요합니다.")
    return token, user


# ======================
# Business rules
# ======================
SELL_MIN_PROFIT = 500  # 순이익 500원부터 SELL


def _to_float(v, default=0.0) -> float:
    try:
        if v is None or v == "":
            return float(default)
        return float(v)
    except Exception:
        return float(default)


def calc_fields(payload: dict) -> dict:
    """
    자동 계산:
    - commission_fee
    - vat_amount
    - net_profit
    - margin_rate
    - signal
    """
    sell_price = _to_float(payload.get("sell_price"), 0)
    cost_price = _to_float(payload.get("cost_price"), 0)
    shipping_fee = _to_float(payload.get("shipping_fee"), 0)

    commission_rate = _to_float(payload.get("commission_rate"), 0)
    if commission_rate < 0:
        commission_rate = 0

    commission_fee = sell_price * commission_rate

    vat_type = (payload.get("vat_type") or "simple").strip().lower()
    # ⚠️ 실전용 “추정 모델”
    # - normal: 매출의 10%를 매출세액으로 단순 가정
    # - simple: 간이과세 추정(여기서는 5%로 고정) -> 나중에 업종별로 확장 가능
    if vat_type == "normal":
        vat_amount = sell_price * 0.10
    else:
        vat_type = "simple"
        vat_amount = sell_price * 0.05

    net_profit = sell_price - cost_price - shipping_fee - commission_fee - vat_amount
    margin_rate = (net_profit / sell_price * 100.0) if sell_price > 0 else 0.0

    signal = "SELL" if net_profit >= SELL_MIN_PROFIT else "STOP"

    return {
        "commission_rate": commission_rate,
        "commission_fee": commission_fee,
        "vat_type": vat_type,
        "vat_amount": vat_amount,
        "net_profit": net_profit,
        "margin_rate": margin_rate,
        "signal": signal,
    }


def items_to_xlsx_bytes(items: list[dict]) -> bytes:
    """
    openpyxl로 XLSX 생성 (pandas 없이)
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "items"

    # 컬럼 순서(원하는 항목 우선)
    preferred_cols = [
        "id",
        "created_at",
        "user_id",
        "url",
        "title",
        "market",
        "category",
        "cost_price",
        "sell_price",
        "shipping_fee",
        "commission_rate",
        "commission_fee",
        "vat_type",
        "vat_amount",
        "net_profit",
        "margin_rate",
        "signal",
    ]

    # 실제 데이터에 존재하는 키 수집
    keys = set()
    for it in items:
        keys |= set(it.keys())

    cols = [c for c in preferred_cols if c in keys]
    # 나머지 컬럼 뒤에 붙이기
    for k in sorted(keys):
        if k not in cols:
            cols.append(k)

    ws.append(cols)
    for it in items:
        ws.append([it.get(c, "") for c in cols])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ======================
# App
# ======================
app = FastAPI()
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ======================
# Pages
# ======================
@app.get("/", response_class=HTMLResponse)
@app.get("/login", response_class=HTMLResponse)
def login_page():
    return (STATIC_DIR / "login.html").read_text(encoding="utf-8")


@app.get("/code", response_class=HTMLResponse)
def code_page():
    return (STATIC_DIR / "code.html").read_text(encoding="utf-8")


@app.get("/user", response_class=HTMLResponse)
def user_page():
    return (STATIC_DIR / "user.html").read_text(encoding="utf-8")


@app.get("/admin", response_class=HTMLResponse)
def admin_page():
    return (STATIC_DIR / "admin.html").read_text(encoding="utf-8")


# ======================
# Public config (frontend supabase init)
# ======================
@app.get("/api/public-config")
def public_config():
    return {"supabaseUrl": SUPABASE_URL, "supabaseAnonKey": SUPABASE_ANON_KEY}


# ======================
# Verify personal code (2FA)
# ======================
@app.post("/api/verify-code")
async def verify_code(request: Request):
    token = get_bearer_token(request)

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(400, "JSON 파싱 실패")

    code = (payload.get("code") or "").strip()
    if not code:
        raise HTTPException(400, "code 값 누락")

    try:
        user = supabase.auth.get_user(token).user
    except Exception:
        raise HTTPException(401, "유효하지 않은 토큰")

    code_hash = hashlib.sha256(code.encode("utf-8")).hexdigest()

    client = db_for_token(token)
    row = (
        client
        .table("user_security")
        .select("access_code_hash, role")
        .eq("user_id", user.id)
        .single()
        .execute()
    )

    if not row.data:
        raise HTTPException(401, "개인 코드 미등록 (관리자에게 발급 요청)")

    if row.data.get("access_code_hash") != code_hash:
        raise HTTPException(401, "개인 코드 불일치")

    return {"success": True, "role": row.data.get("role", "user")}


# ======================
# Admin: create/update user code
# ======================
@app.post("/api/admin/create-code")
async def admin_create_code(request: Request, _=Depends(require_admin)):
    token, admin_user = await require_admin(request)

    payload = await request.json()
    user_id = (payload.get("user_id") or "").strip()
    raw_code = (payload.get("code") or "").strip()
    role = (payload.get("role") or "user").strip()

    if not user_id or not raw_code:
        raise HTTPException(400, "user_id / code 값 누락")

    if role not in ("user", "admin"):
        role = "user"

    code_hash = hashlib.sha256(raw_code.encode("utf-8")).hexdigest()
    client = db_for_token(token)

    client.table("user_security").upsert({
        "user_id": user_id,
        "access_code_hash": code_hash,
        "role": role
    }).execute()

    return {"success": True}


# ======================
# Items CRUD (admin/user shared)
# ======================
@app.get("/api/items")
async def list_items(request: Request):
    token, user, role = await require_user(request)
    client = db_for_token(token)

    q = client.table("user_items").select("*").order("created_at", desc=True)
    if role != "admin":
        q = q.eq("user_id", user.id)

    res = q.execute()
    return res.data or []


@app.post("/api/items")
async def create_item(request: Request):
    token, user, role = await require_user(request)
    payload = await request.json()

    # 최소 필수: sell_price
    if payload.get("sell_price") is None:
        raise HTTPException(400, "sell_price 누락")

    # 기본 정리
    payload["user_id"] = user.id
    payload["title"] = (payload.get("title") or "").strip()
    payload["url"] = (payload.get("url") or "").strip()
    payload["market"] = (payload.get("market") or "").strip()
    payload["category"] = (payload.get("category") or "").strip()

    computed = calc_fields(payload)
    payload.update(computed)

    client = db_for_token(token)
    res = client.table("user_items").insert(payload).execute()
    return res.data


def _ensure_owner_or_admin(client, item_id: int, user_id: str, role: str):
    row = (
        client.table("user_items")
        .select("id,user_id")
        .eq("id", item_id)
        .single()
        .execute()
    )
    if not row.data:
        raise HTTPException(404, "상품을 찾을 수 없습니다.")
    if role != "admin" and row.data["user_id"] != user_id:
        raise HTTPException(403, "권한이 없습니다.")
    return row.data


@app.patch("/api/items/{item_id}")
async def update_item(item_id: int, request: Request):
    token, user, role = await require_user(request)
    payload = await request.json()
    client = db_for_token(token)

    _ensure_owner_or_admin(client, item_id, user.id, role)

    # 현재 값 읽어서 + 변경 적용 후 재계산
    current = (
        client.table("user_items")
        .select("*")
        .eq("id", item_id)
        .single()
        .execute()
    ).data or {}

    # 허용 업데이트 필드
    allowed = {
        "url", "title", "market", "category",
        "cost_price", "sell_price", "shipping_fee",
        "commission_rate", "vat_type",
    }

    merged = dict(current)
    for k in allowed:
        if k in payload:
            merged[k] = payload[k]

    # 문자열 정리
    if "title" in merged:
        merged["title"] = (merged.get("title") or "").strip()
    if "url" in merged:
        merged["url"] = (merged.get("url") or "").strip()
    if "market" in merged:
        merged["market"] = (merged.get("market") or "").strip()
    if "category" in merged:
        merged["category"] = (merged.get("category") or "").strip()

    computed = calc_fields(merged)

    update_data = {k: merged.get(k) for k in allowed}
    update_data.update(computed)

    res = (
        client.table("user_items")
        .update(update_data)
        .eq("id", item_id)
        .execute()
    )
    return res.data


@app.delete("/api/items/{item_id}")
async def delete_item(item_id: int, request: Request):
    token, user, role = await require_user(request)
    client = db_for_token(token)

    _ensure_owner_or_admin(client, item_id, user.id, role)

    client.table("user_items").delete().eq("id", item_id).execute()
    return {"success": True}


# ======================
# Export XLSX (all / sell only)
# ======================
@app.get("/api/items/export")
async def export_items(request: Request, mode: str = "all"):
    token, user, role = await require_user(request)
    client = db_for_token(token)

    q = client.table("user_items").select("*").order("created_at", desc=True)
    if role != "admin":
        q = q.eq("user_id", user.id)

    if mode == "sell":
        q = q.eq("signal", "SELL")

    items = q.execute().data or []
    xlsx_bytes = items_to_xlsx_bytes(items)

    filename = "items_all.xlsx" if mode == "all" else "items_sell.xlsx"
    return StreamingResponse(
        io.BytesIO(xlsx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
