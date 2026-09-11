from uuid import uuid4

from fastapi import Depends, Header, HTTPException

from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    is_legacy_password_hash,
    token_id,
    verify_password,
)
from app.db.supabase import insert, select, update
from app.db.sqlite import reset_test_data

REVOKED_TOKENS: set[str] = set()


def sanitize_user(user: dict | None) -> dict | None:
    if not user:
        return user

    safe_user = dict(user)
    safe_user.pop("password_hash", None)
    return safe_user


def get_bearer_token(authorization: str | None = Header(default=None)) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="authorization header required")

    if len(authorization) > 8192:
        raise HTTPException(status_code=401, detail="invalid authorization header")
    scheme, separator, value = authorization.partition(" ")
    if separator != " " or scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="invalid authorization header")

    token = value.strip()
    if not token:
        raise HTTPException(status_code=401, detail="token required")

    if token_id(token) in REVOKED_TOKENS:
        raise HTTPException(status_code=401, detail="logged out token")

    return token


async def get_current_user_service(token: str):
    payload = decode_access_token(token)
    user_id = payload.get("sub")

    users = await select(
        "users",
        {
            "id": f"eq.{user_id}",
            "limit": "1",
        },
    )

    if not users:
        raise HTTPException(status_code=401, detail="user not found")

    return sanitize_user(users[0])


async def get_current_user_id(token: str = Depends(get_bearer_token)) -> str:
    user = await get_current_user_service(token)
    return str(user.get("id"))


async def signup_service(email: str, password: str):
    email = str(email or "").strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="invalid email")

    if not password or len(password) < 8:
        raise HTTPException(status_code=400, detail="password must be at least 8 characters")

    exists = await select(
        "users",
        {
            "email": f"eq.{email}",
            "limit": "1",
        },
    )

    if exists:
        raise HTTPException(status_code=409, detail="email already exists")

    created = await insert(
        "users",
        {
            "id": str(uuid4()),
            "email": email,
            "password_hash": hash_password(password),
            "role": "user",
        },
    )

    if not created:
        raise HTTPException(status_code=400, detail="signup failed")

    return sanitize_user(created[0])


async def login_service(email: str, password: str):
    email = str(email or "").strip().lower()
    users = await select(
        "users",
        {
            "email": f"eq.{email}",
            "limit": "1",
        },
    )

    if not users:
        raise HTTPException(status_code=401, detail="invalid email or password")

    user = users[0]
    password_hash = user.get("password_hash")

    if not password_hash or not verify_password(password, password_hash):
        raise HTTPException(status_code=401, detail="invalid email or password")

    if is_legacy_password_hash(password_hash):
        await update(
            "users",
            {"id": f"eq.{user.get('id')}"},
            {"password_hash": hash_password(password)},
        )

    access_token = create_access_token(user)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": sanitize_user(user),
    }


async def admin_login_service(email: str, password: str):
    result = await login_service(email, password)
    user = result.get("user")

    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="admin permission required")

    return result


async def get_auth_me_service(token: str):
    return await get_current_user_service(token)


async def logout_service(token: str):
    REVOKED_TOKENS.add(token_id(token))
    return {"ok": True}


async def require_admin_service(token: str):
    user = await get_current_user_service(token)

    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="admin permission required")

    return user


async def reset_test_data_service(token: str):
    admin = await require_admin_service(token)
    reset_test_data()
    return {"ok": True, "message": "test data reset completed", "admin": admin}
