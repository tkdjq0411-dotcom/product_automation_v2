from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from supabase import create_client
from pathlib import Path
import os, hashlib

# ======================
# 기본 설정
# ======================
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    raise RuntimeError("SUPABASE env missing")

supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

def db_with_token(token: str):
    client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    client.postgrest.auth(token)
    return client

# ======================
# Auth helpers
# ======================
def get_token(request: Request):
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(401, "No token")
    return auth.replace("Bearer ", "").strip()

async def require_user(request: Request):
    token = get_token(request)
    user = supabase.auth.get_user(token).user
    client = db_with_token(token)

    sec = (
        client.table("user_security")
        .select("role")
        .eq("user_id", user.id)
        .single()
        .execute()
    )

    if not sec.data:
        raise HTTPException(403, "No access")

    return token, user, sec.data["role"]

async def require_admin(request: Request):
    token, user, role = await require_user(request)
    if role != "admin":
        raise HTTPException(403, "Admin only")
    return token, user

# ======================
# App
# ======================
app = FastAPI()
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/", response_class=HTMLResponse)
def root():
    return (STATIC_DIR / "login.html").read_text(encoding="utf-8")

@app.get("/login", response_class=HTMLResponse)
def login():
    return (STATIC_DIR / "login.html").read_text(encoding="utf-8")

@app.get("/code", response_class=HTMLResponse)
def code():
    return (STATIC_DIR / "code.html").read_text(encoding="utf-8")

@app.get("/user", response_class=HTMLResponse)
def user():
    return (STATIC_DIR / "user.html").read_text(encoding="utf-8")

@app.get("/admin", response_class=HTMLResponse)
def admin():
    return (STATIC_DIR / "admin.html").read_text(encoding="utf-8")

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
async def verify_code(payload: dict, request: Request):
    token = get_token(request)
    code = (payload.get("access_code") or "").strip()
    if not code:
        raise HTTPException(400, "값 누락")

    user = supabase.auth.get_user(token).user
    code_hash = hashlib.sha256(code.encode()).hexdigest()

    client = db_with_token(token)
    row = (
        client.table("user_security")
        .select("access_code_hash, role")
        .eq("user_id", user.id)
        .single()
        .execute()
    )

    if not row.data:
        raise HTTPException(401, "개인 코드 미등록")

    if row.data["access_code_hash"] != code_hash:
        raise HTTPException(401, "개인 코드 불일치")

    return {"success": True, "role": row.data["role"]}

# ======================
# 관리자: 코드 발급
# ======================
@app.post("/api/admin/create-code")
async def create_code(payload: dict, request: Request, _=Depends(require_admin)):
    token = get_token(request)
    user_id = payload.get("user_id")
    code = payload.get("code")
    role = payload.get("role", "user")

    if not user_id or not code:
        raise HTTPException(400, "값 누락")

    code_hash = hashlib.sha256(code.encode()).hexdigest()
    client = db_with_token(token)

    client.table("user_security").upsert({
        "user_id": user_id,
        "access_code_hash": code_hash,
        "role": role
    }).execute()

    return {"success": True}

# ======================
# 상품 CRUD
# ======================
@app.post("/api/user/items")
async def add_item(payload: dict, request: Request):
    token, user, _ = await require_user(request)
    title = payload.get("title")
    price = payload.get("price")

    if not title or price is None:
        raise HTTPException(400, "값 누락")

    client = db_with_token(token)
    return client.table("user_items").insert({
        "user_id": user.id,
        "title": title,
        "price": price
    }).execute().data

@app.get("/api/user/items")
async def get_items(request: Request):
    token, user, _ = await require_user(request)
    client = db_with_token(token)
    return client.table("user_items").select("*").eq("user_id", user.id).execute().data
