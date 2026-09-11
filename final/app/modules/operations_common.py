from fastapi import Depends
from app.modules.auth.service import get_bearer_token, get_current_user_service

async def current_user_id(token: str = Depends(get_bearer_token)) -> str:
    user = await get_current_user_service(token)
    return user.get("id")
