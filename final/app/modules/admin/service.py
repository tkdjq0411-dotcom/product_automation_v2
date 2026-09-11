from app.db.supabase import select
from app.modules.auth.service import sanitize_user
from app.modules.plans.service import usage_service

async def admin_overview_service():
    users=await select("users",{"order":"created_at.desc"})
    products=await select("products")
    suppliers=await select("suppliers")
    inventory=await select("inventory")
    calculations=await select("margin_calculations")
    logs=await select("activity_logs")
    regular=[u for u in users if u.get("role")!="admin"]
    return {
        "user_count":len(regular),
        "admin_count":sum(1 for u in users if u.get("role")=="admin"),
        "product_count":len(products),
        "supplier_count":len(suppliers),
        "calculation_count":len(calculations),
        "total_inventory_quantity":sum(int(x.get("quantity") or 0) for x in inventory),
        "activity_log_count":len(logs),
        "sell_count":sum(1 for p in products if (p.get("status")=="SELL" or (p.get("status")=="HOLD" and float(p.get("net_profit") or 0)>0))),
        "stop_count":sum(1 for p in products if (p.get("status")=="STOP" or (p.get("status")=="HOLD" and float(p.get("net_profit") or 0)<=0))),
    }

async def admin_users_service():
    users=await select("users",{"order":"created_at.desc"})
    products=await select("products")
    suppliers=await select("suppliers")
    calculations=await select("margin_calculations")
    rows=[]
    for user in users:
        uid=user.get("id")
        safe=sanitize_user(user)
        usage=await usage_service(uid)
        safe.update({
            "product_count":sum(1 for x in products if x.get("user_id")==uid),
            "supplier_count":sum(1 for x in suppliers if x.get("user_id")==uid),
            "calculation_count":sum(1 for x in calculations if x.get("user_id")==uid),
            "plan":usage["plan"], "usage":usage,
        })
        rows.append(safe)
    return rows
