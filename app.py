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
# 경로
# ======================
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

# ======================
# Supabase
# ======================
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    raise RuntimeError("SUPABASE env missing")

supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

def db_for_token(token: str):
    client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    client.postgrest.auth(token)
    return client

# ======================
# Auth helpers
# ======================
def get_token(request: Request) -> str:
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(401, "인증 정보가 없습니다.")
    return auth.replace("Bearer ", "").strip()

async def require_user(request: Request):
    token = get_token(request)
    try:
        user = supabase.auth.get_user(token).user
    except Exception:
        raise HTTPException(401, "유효하지 않은 토큰")

    try:
        client = db_for_token(token)
        res = (
            client.table("user_security")
            .select("role")
            .eq("user_id", user.id)
            .single()
            .execute()
        )
    except Exception as e:
        raise HTTPException(500, f"DB 오류: {str(e)}")

    if not res.data:
        raise HTTPException(403, "개인 코드 미등록")

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
# Pages
# ======================
@app.get("/", response_class=HTMLResponse)
def root():
    return (STATIC_DIR / "login.html").read_text(encoding="utf-8")

@app.get("/login", response_class=HTMLResponse)
def login_page():
    return (STATIC_DIR / "login.html").read_text(encoding="utf-8")

@app.get("/code", response_class=HTMLResponse)
def code_page():
    return (STATIC_DIR / "code.html").read_text(encoding="utf-8")

@app.get("/admin", response_class=HTMLResponse)
def admin_page():
    return (STATIC_DIR / "admin.html").read_text(encoding="utf-8")

@app.get("/user", response_class=HTMLResponse)
def user_page():
    return (STATIC_DIR / "user.html").read_text(encoding="utf-8")

# ======================
# API: Login
# ======================
@app.post("/api/login")
async def login(payload: dict):
    email = (payload.get("email") or "").strip()
    password = (payload.get("password") or "").strip()

    if not email or not password:
        raise HTTPException(400, "값 누락")

    try:
        res = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        session = res.session
    except Exception:
        raise HTTPException(401, "로그인 실패")

    if not session or not session.access_token:
        raise HTTPException(401, "로그인 실패")

    return {"access_token": session.access_token}

# ======================
# API: Verify code (🔥 500 방지 완료)
# ======================
@app.post("/api/verify-code")
async def verify_code(payload: dict, request: Request):
    token = get_token(request)

    code = (payload.get("access_code") or payload.get("code") or "").strip()
    if not code:
        raise HTTPException(400, "값 누락")

    try:
        user = supabase.auth.get_user(token).user
    except Exception:
        raise HTTPException(401, "유효하지 않은 토큰")

    code_hash = hashlib.sha256(code.encode()).hexdigest()

    try:
        client = db_for_token(token)
        res = (
            client.table("user_security")
            .select("access_code_hash, role")
            .eq("user_id", user.id)
            .single()
            .execute()
        )
    except Exception as e:
        raise HTTPException(500, f"DB 조회 실패: {str(e)}")

    if not res.data:
        raise HTTPException(403, "개인 코드 미등록")

    if res.data.get("access_code_hash") != code_hash:
        raise HTTPException(403, "개인 코드 불일치")

    return {"success": True, "role": res.data["role"]}

# ======================
# API: Admin create code
# ======================
@app.post("/api/admin/create-code")
async def create_code(payload: dict, request: Request, _=Depends(require_admin)):
    token = get_token(request)

    user_id = (payload.get("user_id") or "").strip()
    raw_code = (payload.get("access_code") or "").strip()
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
