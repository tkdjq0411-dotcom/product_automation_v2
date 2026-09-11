from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException

from app.db.supabase import select, insert, update
from app.modules.operations_common import current_user_id
from app.modules.integrations.schema import ConnectionUpdate
from app.modules.integrations.clients import integration_config, test_naver_connection, test_coupang_connection, naver_account_info, naver_product

router = APIRouter()
CHANNELS = ["NAVER", "COUPANG", "11ST"]


@router.get("/")
async def list_connections(user_id: str = Depends(current_user_id)):
    rows = await select("channel_connections", {"user_id": f"eq.{user_id}"})
    saved = {x["channel"]: x for x in rows}
    config = integration_config()
    connections = []
    for channel in CHANNELS:
        row = saved.get(channel) or {
            "channel": channel,
            "enabled": 0,
            "account_label": None,
            "note": "API 자격증명은 서버 환경변수로 관리합니다.",
        }
        row = dict(row)
        row["api_config"] = config.get(channel, {})
        connections.append(row)
    return {"ok": True, "connections": connections}


@router.get("/status")
async def connection_status(user_id: str = Depends(current_user_id)):
    _ = user_id
    return {"ok": True, "channels": integration_config()}


@router.post("/{channel}/test")
async def test_connection(channel: str, user_id: str = Depends(current_user_id)):
    _ = user_id
    channel = channel.upper()
    try:
        if channel == "NAVER":
            return await test_naver_connection()
        if channel == "COUPANG":
            return await test_coupang_connection()
        raise HTTPException(400, "아직 연결 테스트를 지원하지 않는 채널입니다.")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(400, str(exc))


@router.get("/NAVER/account")
async def get_naver_account(user_id: str = Depends(current_user_id)):
    _ = user_id
    try:
        return {"ok": True, "account": await naver_account_info()}
    except Exception as exc:
        raise HTTPException(400, str(exc))


@router.get("/NAVER/product/{origin_product_no}")
async def get_naver_product(origin_product_no: str, user_id: str = Depends(current_user_id)):
    _ = user_id
    try:
        return {"ok": True, "product": await naver_product(origin_product_no)}
    except Exception as exc:
        raise HTTPException(400, str(exc))


@router.patch("/{channel}")
async def save(channel: str, data: ConnectionUpdate, user_id: str = Depends(current_user_id)):
    channel = channel.upper()
    if channel not in CHANNELS:
        raise HTTPException(400, "지원하지 않는 판매 채널입니다.")
    existing = await select("channel_connections", {"user_id": f"eq.{user_id}", "channel": f"eq.{channel}"})
    payload = {
        "enabled": 1 if data.enabled else 0,
        "account_label": data.account_label,
        "note": data.note,
        "updated_at": datetime.now().isoformat(),
    }
    rows = await update("channel_connections", {"id": f'eq.{existing[0]["id"]}'}, payload) if existing else await insert("channel_connections", {"user_id": user_id, "channel": channel, **payload})
    result = dict(rows[0])
    result["api_config"] = integration_config().get(channel, {})
    return {"ok": True, "connection": result}
