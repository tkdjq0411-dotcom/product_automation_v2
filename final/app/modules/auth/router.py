from fastapi import APIRouter, Depends

from app.modules.auth.schema import LoginRequest, SignupRequest
from app.modules.auth.service import (
    admin_login_service,
    get_auth_me_service,
    get_bearer_token,
    login_service,
    logout_service,
    require_admin_service,
    reset_test_data_service,
    signup_service,
)

router = APIRouter()


@router.post("/signup", summary="회원가입")
async def signup(data: SignupRequest):
    user = await signup_service(data.email, data.password)

    return {
        "ok": True,
        "user_id": user.get("id"),
        "user": user,
    }


@router.post("/login", summary="로그인")
async def login(data: LoginRequest):
    result = await login_service(data.email, data.password)

    return {
        "ok": True,
        "access_token": result.get("access_token"),
        "token_type": result.get("token_type"),
        "user_id": result.get("user", {}).get("id"),
        "user": result.get("user"),
    }


@router.get("/me", summary="내 정보 조회")
async def auth_me(token: str = Depends(get_bearer_token)):
    user = await get_auth_me_service(token)

    return {
        "ok": True,
        "user": user,
    }


@router.post("/logout", summary="로그아웃")
async def logout(token: str = Depends(get_bearer_token)):
    return await logout_service(token)


@router.post("/admin/login", summary="관리자 로그인")
async def admin_login(data: LoginRequest):
    result = await admin_login_service(data.email, data.password)

    return {
        "ok": True,
        "access_token": result.get("access_token"),
        "token_type": result.get("token_type"),
        "admin": result.get("user"),
    }


@router.get("/admin/check", summary="관리자 권한 확인")
async def admin_check(token: str = Depends(get_bearer_token)):
    admin = await require_admin_service(token)

    return {
        "ok": True,
        "is_admin": True,
        "admin": admin,
    }


@router.get("/admin/page", summary="관리자 페이지")
async def admin_page(token: str = Depends(get_bearer_token)):
    admin = await require_admin_service(token)

    return {
        "ok": True,
        "message": "admin page access granted",
        "admin": admin,
    }


@router.post("/admin/reset-test-data", summary="테스트 데이터 초기화")
async def reset_test_data(token: str = Depends(get_bearer_token)):
    return await reset_test_data_service(token)
