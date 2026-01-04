from fastapi import Request, HTTPException

def admin_guard(request: Request):
    if not request.session.get("authed"):
        raise HTTPException(status_code=401, detail="not authed")
    if not request.session.get("is_admin"):
        raise HTTPException(status_code=403, detail="not admin")

