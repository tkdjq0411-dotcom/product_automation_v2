from fastapi import HTTPException
from app.db.supabase import select, update
from app.modules.auth.service import sanitize_user

PLAN_LIMITS={
    "free":{"label":"무료","products":50,"calculations":100},
    "pro":{"label":"유료","products":None,"calculations":None},
}
def normalize_plan(value):
    plan=str(value or "free").lower()
    return plan if plan in PLAN_LIMITS else "free"

async def usage_service(user_id):
    users=await select("users",{"id":f"eq.{user_id}","limit":"1"})
    if not users: raise HTTPException(status_code=404,detail="user not found")
    user=users[0]; plan=normalize_plan(user.get("plan"))
    products=await select("products",{"user_id":f"eq.{user_id}"})
    calculations=await select("margin_calculations",{"user_id":f"eq.{user_id}"})
    used={"products":len(products),"calculations":len(calculations)}
    limits=PLAN_LIMITS[plan]
    return {"plan":plan,"plan_label":limits["label"],"limits":{"products":limits["products"],"calculations":limits["calculations"]},
            "used":used,"remaining":{k:(None if limits[k] is None else max(limits[k]-used[k],0)) for k in used}}

async def ensure_usage_available(user_id, resource, additional=1):
    usage=await usage_service(user_id); limit=usage["limits"][resource]
    if limit is not None and usage["used"][resource]+additional>limit:
        raise HTTPException(status_code=403,detail=f"{usage['plan']} plan {resource} limit exceeded")
    return usage

async def set_user_plan_service(user_id, plan):
    raw=str(plan or "").lower()
    if raw not in PLAN_LIMITS: raise HTTPException(status_code=422,detail="plan must be free or pro")
    plan=raw
    rows=await update("users",{"id":f"eq.{user_id}"},{"plan":plan})
    if not rows: raise HTTPException(status_code=404,detail="user not found")
    return sanitize_user(rows[0])
