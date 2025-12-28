from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Header, HTTPException, Request, Depends, status
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
    raise RuntimeError("SUPABASE 환경변수 없음")

supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# ======================
# 권한 체크 (API 전용)
# ======================
async def require_user(request: Request):
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(401, "인증 정보가 없습니다.")

    token = auth.replace("Bearer ", "")
    try:
        user = supabase.auth.get_user(token).user
    except:
        raise HTTPException(401, "유효하지 않은 토큰입니다.")

    res = (
        supabase
        .table("user_security")
        .select("role")
        .eq("user_id", user.id)
        .single()
        .execute()
    )

    if not res.data:
        raise HTTPException(403, "접근 권한이 없습니다.")

    return user, res.data["role"]


async def require_admin(request: Request):
    user, role = await require_user(request)
    if role != "admin":
        raise HTTPException(403, "관리자 권한이 필요합니다.")
    return user

# ======================
# FastAPI
# ======================
app = FastAPI()
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# ======================
# HTML 페이지 (❗ 보호 제거)
# ======================
@app.get("/", response_class=HTMLResponse)
def root():
    return (STATIC_DIR / "login.html").read_text("utf-8")

@app.get("/login", response_class=HTMLResponse)
def login():
    return (STATIC_DIR / "login.html").read_text("utf-8")

@app.get("/code", response_class=HTMLResponse)
def code():
    return (STATIC_DIR / "code.html").read_text("utf-8")

@app.get("/admin", response_class=HTMLResponse)
def admin_page():
    return (STATIC_DIR / "admin.html").read_text("utf-8")

@app.get("/user", response_class=HTMLResponse)
def user_page():
    return (STATIC_DIR / "user.html").read_text("utf-8")

# ======================
# API
# ======================
@app.post("/api/verify-code")
def verify_code(data: dict):
    user_id = data.get("user_id")
    code = data.get("code")

    if not user_id or not code:
        raise HTTPException(400, "값 누락")

    code_hash = hashlib.sha256(code.encode()).hexdigest()

    res = (
        supabase
        .table("user_security")
        .select("access_code_hash, role")
        .eq("user_id", user_id)
        .execute()
    )

    if not res.data:
        raise HTTPException(401, "개인 코드 미등록")

    if res.data[0]["access_code_hash"] != code_hash:
        raise HTTPException(401, "개인 코드 불일치")

    return {
        "success": True,
        "role": res.data[0]["role"]
    }

# ======================
# 관리자 API (🔒 보호)
# ======================
@app.post("/api/admin/create-code")
async def create_code(payload: dict, user=Depends(require_admin)):
    user_id = payload.get("user_id")
    raw_code = payload.get("code")
    role = payload.get("role", "user")

    if not user_id or not raw_code:
        raise HTTPException(400, "값 누락")

    supabase.table("user_security").upsert({
        "user_id": user_id,
        "access_code_hash": hashlib.sha256(raw_code.encode()).hexdigest(),
        "role": role
    }).execute()

    return {"success": True}

# ======================
# 사용자 API (기존 유지)
# ======================
@app.post("/api/user/add-item")
def add_item(data: dict, x_user_id: str = Header(None)):
    if not x_user_id:
        raise HTTPException(400, "user id 없음")

    supabase.table("user_items").insert({
        "user_id": x_user_id,
        "title": data["title"],
        "price": data["price"]
    }).execute()

    return {"success": True}

@app.get("/api/user/items")
def get_items(x_user_id: str = Header(None)):
    return (
        supabase
        .table("user_items")
        .select("*")
        .eq("user_id", x_user_id)
        .execute()
        .data
    )

