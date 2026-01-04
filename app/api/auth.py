from fastapi import APIRouter, Request, HTTPException
from app.core.security import hash_code
from app.db.supabase import sb_select_one

router = APIRouter()

@router.post("/api/code/verify")
async def verify_code(request: Request):
    body = await request.json()
    code = (body.get("code") or "").strip()
    if not code:
        raise HTTPException(status_code=400, detail="code required")

    hashed = hash_code(code)
    row = await sb_select_one("user_security", {"select": "*", "access_code_hash": f"eq.{hashed}"})
    if not row:
        raise HTTPException(status_code=401, detail="invalid code")

    request.session.clear()
    request.session["authed"] = True
    request.session["is_admin"] = (row.get("role") == "admin")
    request.session["user_id"] = row.get("user_id")

    return {"ok": True}

@router.post("/api/logout")
async def logout(request: Request):
    request.session.clear()
    return {"ok": True}
