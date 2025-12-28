from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from supabase import create_client
from pathlib import Path
import os
import hashlib

# ======================
# 경로 설정
# ======================
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

# ======================
# Supabase 설정
# ======================
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    raise RuntimeError("SUPABASE 환경변수 없음 (.env 확인)")

supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

def db_for_token(access_token: str):
    client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    client.postgrest.auth(access_token)
    return client

# ======================
# 인증 유틸
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
    res = (
        client
        .table("user_security")
        .select("role")
        .eq("user_id", user.id)
        .single()
        .execute()
    )

    if not res.data:
        raise HTTPException(403, "권한 정보 없음")

    return token, user, res.data["role"]

async def require_admin(request: Request):
    token, user, role = await require_user(request)
    if role != "admin":
        raise HTTPException(403, "관리자 권한 필요")
    return token, user

# ======================
# FastAPI
# ======================
app = FastAPI()
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# ======================
# HTML Routes
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
# 공개 설정
# ======================
@app.get("/api/public-config")
def public_config():
    return {
        "supabaseUrl": SUPABASE_URL,
        "supabaseAnonKey": SUPABASE_ANON_KEY
    }

# ======================
# 개인 코드 검증
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
        raise HTTPException(400, "값 누락")

    try:
        user = supabase.auth.get_user(token).user
    except Exception:
        raise HTTPException(401, "유효하지 않은 토큰")

    code_hash = hashlib.sha256(code.encode()).hexdigest()

    client = db_for_token(token)
    res = (
        client
        .table("user_security")
        .select("access_code_hash, role")
        .eq("user_id", user.id)
        .single()
        .execute()
    )

    if not res.data:
        raise HTTPException(401, "개인 코드 미등록")

    if res.data["access_code_hash"] != code_hash:
        raise HTTPException(401, "개인 코드 불일치")

    return {"success": True, "role": res.data["role"]}

# ======================
# 관리자: 개인 코드 발급
# ======================
@app.post("/api/admin/create-code")
async def create_code(request: Request, _=Depends(require_admin)):
    token, admin_user, _role = await require_user(request)

    payload = await request.json()
    user_id = payload.get("user_id")
    raw_code = payload.get("code")
    role = payload.get("role", "user")

    if not user_id or not raw_code:
        raise HTTPException(400, "값 누락")

    code_hash = hashlib.sha256(raw_code.encode()).hexdigest()

    client = db_for_token(token)
    client.table("user_security").upsert({
        "user_id": user_id,
        "access_code_hash": code_hash,
        "role": role
    }).execute()

    return {"success": True}

# ======================
# ✅ 공통 상품 CRUD (관리자/유저 공용)
# - admin: 전체 상품 조회/수정/삭제 가능
# - user : 본인 상품만 가능
# ======================

@app.get("/api/items")
async def list_items(request: Request):
    token, user, role = await require_user(request)
    client = db_for_token(token)

    q = client.table("user_items").select("*").order("created_at", desc=True)
    if role != "admin":
        q = q.eq("user_id", user.id)

    res = q.execute()
    return res.data

@app.post("/api/items")
async def create_item(request: Request):
    token, user, role = await require_user(request)
    payload = await request.json()

    title = (payload.get("title") or "").strip()
    price = payload.get("price")

    if not title or price is None:
        raise HTTPException(400, "값 누락")

    client = db_for_token(token)
    res = client.table("user_items").insert({
        "user_id": user.id,
        "title": title,
        "price": price
    }).execute()

    return res.data

def _ensure_item_owner_or_admin(client, item_id: int, user_id: str, role: str):
    item_res = (
        client
        .table("user_items")
        .select("id,user_id")
        .eq("id", item_id)
        .single()
        .execute()
    )
    if not item_res.data:
        raise HTTPException(404, "상품을 찾을 수 없습니다.")

    if role != "admin" and item_res.data["user_id"] != user_id:
        raise HTTPException(403, "권한이 없습니다.")

    return item_res.data

@app.patch("/api/items/{item_id}")
async def update_item(item_id: int, request: Request):
    token, user, role = await require_user(request)
    payload = await request.json()
    client = db_for_token(token)

    _ensure_item_owner_or_admin(client, item_id, user.id, role)

    update_data = {}
    if "title" in payload:
        update_data["title"] = (payload.get("title") or "").strip()
    if "price" in payload:
        update_data["price"] = payload.get("price")

    if not update_data:
        raise HTTPException(400, "수정할 값이 없습니다.")

    res = (
        client
        .table("user_items")
        .update(update_data)
        .eq("id", item_id)
        .execute()
    )
    return res.data

@app.delete("/api/items/{item_id}")
async def delete_item(item_id: int, request: Request):
    token, user, role = await require_user(request)
    client = db_for_token(token)

    _ensure_item_owner_or_admin(client, item_id, user.id, role)

    res = (
        client
        .table("user_items")
        .delete()
        .eq("id", item_id)
        .execute()
    )
    return {"success": True, "deleted": res.data}
