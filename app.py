from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from supabase import create_client
from pathlib import Path
import os, asyncio, hashlib

# ======================
# Paths
# ======================
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

# ======================
# Env
# ======================
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_DEFAULT_CHAT_ID")

SELL_MIN_PROFIT = 500
MONITOR_INTERVAL_SECONDS = int(os.getenv("MONITOR_INTERVAL_SECONDS", "3600"))

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    raise RuntimeError("SUPABASE_URL / SUPABASE_ANON_KEY missing in .env")

supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# ======================
# App (정상 선언)
# ======================
app = FastAPI()
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# ======================
# Helpers
# ======================
def get_bearer_token(req: Request) -> str:
    auth = req.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(401, "No auth token")
    return auth.replace("Bearer ", "").strip()

def db_for_token(token: str):
    client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    client.postgrest.auth(token)
    return client

async def require_user(req: Request):
    token = get_bearer_token(req)
    user = supabase.auth.get_user(token).user
    client = db_for_token(token)

    sec = client.table("user_security") \
        .select("role") \
        .eq("user_id", user.id) \
        .single() \
        .execute()

    if not sec.data:
        raise HTTPException(403, "Personal code not verified")

    return token, user, sec.data.get("role", "user")

async def require_admin(req: Request):
    token, user, role = await require_user(req)
    if role != "admin":
        raise HTTPException(403, "Admin only")
    return token, user

# ======================
# Public config (Supabase)
# ======================
@app.get("/api/public-config")
def public_config():
    return {
        "supabaseUrl": SUPABASE_URL,
        "supabaseAnonKey": SUPABASE_ANON_KEY
    }

# ======================
# Calculation Engine
# ======================
def calc_fields(item: dict):
    sell = float(item.get("sell_price") or 0)
    cost = float(item.get("cost_price") or 0)
    ship = float(item.get("shipping_fee") or 0)
    rate = float(item.get("commission_rate") or 0)
    vat_type = (item.get("vat_type") or "simple").lower()

    fee = sell * rate
    vat = sell * (0.1 if vat_type == "normal" else 0.05)
    profit = sell - cost - ship - fee - vat

    if profit >= SELL_MIN_PROFIT:
        decision = "SELL"
        reason = "PROFIT_OK"
    elif profit >= 0:
        decision = "HOLD"
        reason = "LOW_MARGIN"
    else:
        decision = "STOP"
        reason = "NEGATIVE_MARGIN"

    return {
        "last_profit": profit,
        "decision_status": decision,
        "reason_code": reason,
    }

# ======================
# Auto Monitor
# ======================
async def monitor_loop():
    await asyncio.sleep(5)
    while True:
        try:
            await run_monitor_once()
        except Exception as e:
            print("Monitor error:", e)
        await asyncio.sleep(MONITOR_INTERVAL_SECONDS)

async def run_monitor_once():
    rows = supabase.table("user_items").select("*").execute().data or []

    for it in rows:
        before = it.get("decision_status")
        computed = calc_fields(it)

        if computed["decision_status"] != before:
            supabase.table("user_items") \
                .update(computed) \
                .eq("id", it["id"]) \
                .execute()

            supabase.table("auto_decision_logs").insert({
                "item_id": it["id"],
                "from_decision": before,
                "to_decision": computed["decision_status"],
                "reason_code": computed["reason_code"],
                "profit": computed["last_profit"]
            }).execute()

# ======================
# Startup
# ======================
@app.on_event("startup")
async def startup():
    asyncio.create_task(monitor_loop())

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
# Verify personal code
# ======================
@app.post("/api/verify-code")
async def verify_code(req: Request):
    token = get_bearer_token(req)
    payload = await req.json()
    code = (payload.get("code") or "").strip()

    if not code:
        raise HTTPException(400, "code missing")

    user = supabase.auth.get_user(token).user
    code_hash = hashlib.sha256(code.encode()).hexdigest()

    client = db_for_token(token)
    row = client.table("user_security") \
        .select("access_code_hash, role") \
        .eq("user_id", user.id) \
        .single() \
        .execute()

    if not row.data or row.data["access_code_hash"] != code_hash:
        raise HTTPException(401, "Invalid code")

    return {"success": True, "role": row.data.get("role", "user")}

# ======================
# Admin create code
# ======================
@app.post("/api/admin/create-code")
async def admin_create_code(req: Request):
    token, admin = await require_admin(req)
    payload = await req.json()

    user_id = payload.get("user_id")
    raw_code = payload.get("code")
    role = payload.get("role", "user")

    if not user_id or not raw_code:
        raise HTTPException(400, "user_id / code missing")

    code_hash = hashlib.sha256(raw_code.encode()).hexdigest()
    client = db_for_token(token)

    client.table("user_security").upsert({
        "user_id": user_id,
        "access_code_hash": code_hash,
        "role": role
    }).execute()

    return {"success": True}

# ======================
# Items API
# ======================
@app.get("/api/items")
async def list_items(req: Request):
    token, user, role = await require_user(req)
    client = db_for_token(token)

    q = client.table("user_items").select("*")
    if role != "admin":
        q = q.eq("user_id", user.id)

    return q.execute().data or []

@app.post("/api/items")
async def create_item(req: Request):
    token, user, role = await require_user(req)
    payload = await req.json()
    payload["user_id"] = user.id

    payload.update(calc_fields(payload))
    client = db_for_token(token)

    return client.table("user_items").insert(payload).execute().data

@app.patch("/api/items/{item_id}")
async def update_item(item_id: str, req: Request):
    token, user, role = await require_user(req)
    client = db_for_token(token)

    current = client.table("user_items") \
        .select("*") \
        .eq("id", item_id) \
        .single() \
        .execute() \
        .data

    merged = {**current, **(await req.json())}
    merged.update(calc_fields(merged))

    return client.table("user_items") \
        .update(merged) \
        .eq("id", item_id) \
        .execute() \
        .data

