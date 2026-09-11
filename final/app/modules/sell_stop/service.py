from fastapi import HTTPException

from app.db.supabase import insert, select


async def list_sell_stop_results_service(user_id: str):
    return await select(
        "sell_stop_results",
        {
            "user_id": f"eq.{user_id}",
            "order": "id.desc",
        },
    )


async def get_sell_stop_result_service(user_id: str, result_id: str):
    rows = await select(
        "sell_stop_results",
        {
            "id": f"eq.{result_id}",
            "user_id": f"eq.{user_id}",
            "limit": "1",
        },
    )

    if not rows:
        raise HTTPException(status_code=404, detail="sell stop result not found")

    return rows[0]


async def create_sell_stop_result_service(user_id: str, data: dict):
    result = "SELL" if data["net_profit"] > 0 else "STOP"

    payload = {
        **data,
        "user_id": user_id,
        "result": result,
    }

    saved = await insert("sell_stop_results", payload)

    return {
        "saved": saved,
        "result": result,
    }