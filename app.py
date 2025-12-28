from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, Request, Depends, status
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
# ✅ 개인 코드 검증 (최종 안정판)
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

    return {
        "success": True,
        "role": res.data["role"]
    }

# ======================
# 관리자: 개인 코드 발급
# ======================
@app.post("/api/admin/create-code")
async def create_code(request: Request, _=Depends(require_admin)):
    token, admin_user, _ = await require_user(request)

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
# 사용자 상품 CRUD
# ======================
@app.post("/api/user/items")
async def add_item(request: Request):
    token, user, _ = await require_user(request)
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

@app.get("/api/user/items")
async def get_items(request: Request):
    token, user, _ = await require_user(request)
    client = db_for_token(token)
    res = (
        client
        .table("user_items")
        .select("*")
        .eq("user_id", user.id)
        .order("created_at", desc=True)
        .execute()
    )
    return res.data
