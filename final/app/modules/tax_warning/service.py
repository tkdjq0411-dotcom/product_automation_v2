from datetime import datetime, timezone

from fastapi import HTTPException

from app.db.supabase import select, update
from app.modules.calculations.engine import calculate_profit


def build_warning_status(user: dict):
    tax_type = user.get("tax_type")
    confirmed_at = user.get("tax_warning_confirmed_at")

    if tax_type == "general":
        return {
            "warning": False,
            "repeat": False,
            "level": 0,
            "message": "일반과세자 기준입니다.",
            "tax_warning_confirmed_at": confirmed_at,
        }

    return {
        "warning": False,
        "repeat": False,
        "level": 0,
        "message": "현재 과세 전환 위험 확인 기준 데이터가 없습니다.",
        "tax_warning_confirmed_at": confirmed_at,
    }


async def get_tax_warning_status_service(user_id: str):
    users = await select(
        "users",
        {
            "id": f"eq.{user_id}",
            "limit": "1",
        },
    )

    if not users:
        raise HTTPException(status_code=404, detail="user not found")

    return build_warning_status(users[0])


async def confirm_tax_warning_service(user_id: str, confirmed: bool):
    confirmed_at = datetime.now(timezone.utc).isoformat() if confirmed else None

    result = await update(
        "users",
        {
            "id": f"eq.{user_id}",
        },
        {
            "tax_warning_confirmed_at": confirmed_at,
        },
    )

    return result


async def recalculate_general_service(data: dict):
    result = calculate_profit(
        purchase_price=data["supply_price"],
        international_shipping=0,
        domestic_shipping=data["shipping_fee"],
        selling_price=data["sale_price"],
        fee_rate=data["market_fee_rate"],
        vat_rate=data["vat_rate"],
    )
    return {
        "tax_type": "general",
        "market_fee": result["fee_amount"],
        "vat_amount": result["vat_amount"],
        "total_cost": result["total_cost"],
        "net_profit": result["net_profit"],
        "margin_rate": result["margin_rate"],
    }
