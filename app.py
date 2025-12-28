from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import HTMLResponse, JSONResponse
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
# Supabase 설정
# ======================
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    raise RuntimeError("SUPABASE 환경변수 없음")

supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

def db_for_token(token: str):
    client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    try:
        client.postgrest.auth(token)
    except Exception:
        # 토큰 컨텍스트 실패해도 여기서 죽지 않게
        pass
    return client

# ======================
# 공통 응답 (절대 HTML 에러 안 나게)
# ======================
def json_error(status: int, msg: str):
    return JSONResponse(
        status_code=status,
        content={"detail": msg}
    )

# ======================
# 인증 헬퍼
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
            client
            .table("user_security")
            .select("role")
            .eq("user_id", user.id)
            .single()
            .execute()
        )
    except Exception as e:
        raise HTTPException(500, f"user_security 조회 실패: {str(e)}")

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
# HTML
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
# API: 로그인
# ======================
@app.post("/api/login")
async def login(payload: dict):
    email = (payload.get("email") or "").strip()
    password = (payload.get("password") or "").strip()

    if not email or not password:
        return json_error(400, "값 누락")

    try:
        res = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        session = res.session
    except Exception:
        return json_error(401, "로그인 실패")

    if not session or not session.access_token:
        return json_error(401, "로그인 실패")

    return {"access_token": session.access_token}

# ======================
# API: 개인코드 검증 (🔥 절대 500 안 터짐)
# ======================
@app.post("/api/verify-code")
async def verify_code(payload: dict, request: Request):
    try:
        token = get_token(request)
    except HTTPException as e:
        return json_error(e.status_code, e.detail)

    raw_code = (payload.get("access_code") or payload.get("code") or "").strip()
    if not raw_code:
        return json_error(400, "값 누락")

    try:
        user = supabase.auth.get_user(token).user
    except Exception:
        return json_error(401, "유효하지 않은 토큰")

    code_hash = hashlib.sha256(raw_code.encode()).hexdigest()

    try:
        client = db_for_token(token)
        res = (
            client
            .table("user_security")
            .select("access_code_hash, role")
            .eq("user_id", user.id)
            .single()
            .execute()
        )
    except Exception as e:
        return json_error(500, f"DB 조회 실패: {str(e)}")

    if not res.data:
        return json_error(403, "개인 코드 미등록")

    if not res.data.get("access_code_hash"):
        return json_error(403, "개인 코드 미등록")

    if res.data["access_code_hash"] != code_hash:
        return json_error(403, "개인 코드 불일치")

    return {
        "success": True,
        "role": res.data["role"]
    }

# ======================
# API: 관리자 개인코드 발급
# ======================
@app.post("/api/admin/create-code")
async def create_code(payload: dict, request: Request, _=Depends(require_admin)):
    try:
        token = get_token(request)
    except HTTPException as e:
        return json_error(e.status_code, e.detail)

    user_id = (payload.get("user_id") or "").strip()
    raw_code = (payload.get("access_code") or "").strip()
    role = payload.get("role", "user")

    if not user_id or not raw_code:
        return json_error(400, "값 누락")

    code_hash = hashlib.sha256(raw_code.encode()).hexdigest()

    try:
        client = db_for_token(token)
        client.table("user_security").upsert({
            "user_id": user_id,
            "access_code_hash": code_hash,
            "role": role
        }).execute()
    except Exception as e:
        return json_error(500, f"저장 실패: {str(e)}")

    return {"success": True}
