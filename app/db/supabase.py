import os
import httpx

SUPABASE_URL = os.getenv("SUPABASE_URL")
SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SERVICE_ROLE_KEY:
    raise RuntimeError("Supabase env missing (SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY)")

HEADERS = {
    "apikey": SERVICE_ROLE_KEY,
    "Authorization": f"Bearer {SERVICE_ROLE_KEY}",
    "Content-Type": "application/json",
}

REST_URL = f"{SUPABASE_URL}/rest/v1"

async def sb_select(table: str, params: dict):
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(f"{REST_URL}/{table}", headers=HEADERS, params=params)
    if r.status_code != 200:
        raise RuntimeError(f"Supabase select error {r.status_code}: {r.text}")
    return r.json()

async def sb_select_one(table: str, params: dict):
    rows = await sb_select(table, {**params, "limit": "1"})
    return rows[0] if rows else None
