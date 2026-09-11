from fastapi import HTTPException

from app.db.supabase import select, update
from app.modules.auth.service import sanitize_user


async def get_user_service(user_id: str):
    users = await select(
        "users",
        {
            "id": f"eq.{user_id}",
            "limit": "1",
        },
    )

    if not users:
        raise HTTPException(status_code=404, detail="user not found")

    return sanitize_user(users[0])


async def get_user_me_service(user: dict):
    if not user:
        raise HTTPException(status_code=401, detail="unauthorized")

    return sanitize_user(user)


async def update_tax_type_service(user_id: str, tax_type: str):
    if tax_type not in ["simple", "general"]:
        raise HTTPException(status_code=400, detail="invalid tax type")

    return await update(
        "users",
        {"id": f"eq.{user_id}"},
        {"tax_type": tax_type},
    )
