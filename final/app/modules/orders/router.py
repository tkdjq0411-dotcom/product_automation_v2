from datetime import datetime
from fastapi import APIRouter,Depends,HTTPException
from app.db.supabase import select,insert,update,delete
from app.modules.operations_common import current_user_id
from app.modules.orders.schema import OrderCreate,OrderUpdate
from app.modules.activity_logs.service import create_activity_log
from app.modules.after_sales.service import process_request
router=APIRouter()
@router.get("/")
async def list_orders(user_id:str=Depends(current_user_id)):
    rows=await select("orders",{"user_id":f"eq.{user_id}","order":"created_at.desc"}); return {"ok":True,"orders":rows}
@router.post("/")
async def create_order(data:OrderCreate,user_id:str=Depends(current_user_id)):
    try: rows=await insert("orders",{"user_id":user_id,**data.model_dump()})
    except Exception as e: raise HTTPException(400,"주문번호가 중복되었거나 입력값이 올바르지 않습니다.")
    o=rows[0]; await create_activity_log(user_id,"order","주문 수집","order",o["id"],o["order_no"],o["product_name"]); return {"ok":True,"order":o}


@router.post("/app-import", summary="구매자 앱 결제완료 주문 자동수집")
async def import_app_order(data:OrderCreate,user_id:str=Depends(current_user_id)):
    if not data.app_order_id: raise HTTPException(400,"앱 주문번호가 필요합니다.")
    if data.payment_status!='PAID': raise HTTPException(400,"결제 완료가 검증된 주문만 접수할 수 있습니다.")
    payload=data.model_dump(); payload["channel"]="BUYER_APP"; payload["status"]="NEW"
    try: rows=await insert("orders",{"user_id":user_id,**payload})
    except Exception: raise HTTPException(400,"이미 접수된 앱 주문이거나 주문번호가 중복되었습니다.")
    order=rows[0]
    await create_activity_log(user_id,"order","구매자 앱 주문 자동수집","order",order["id"],order["order_no"],order["product_name"])
    return {"ok":True,"order":order,"next_action":"SUPPLIER_PAYMENT_PREPARE"}
@router.patch("/{order_id}")
async def patch_order(order_id:str,data:OrderUpdate,user_id:str=Depends(current_user_id)):
    if data.status == "CANCELLED":
        orders=await select("orders",{"id":f"eq.{order_id}","user_id":f"eq.{user_id}","limit":"1"})
        if not orders: raise HTTPException(404,"주문을 찾을 수 없습니다.")
        request=await process_request(user_id,orders[0],"CANCEL","판매자 화면에서 취소",float(orders[0].get("sale_price") or 0))
        refreshed=await select("orders",{"id":f"eq.{order_id}","user_id":f"eq.{user_id}","limit":"1"})
        return {"ok":True,"order":refreshed[0],"after_sales":request}
    rows=await update("orders",{"id":f"eq.{order_id}","user_id":f"eq.{user_id}"},{**data.model_dump(exclude_unset=True),"updated_at":datetime.now().isoformat()});
    if not rows: raise HTTPException(404,"주문을 찾을 수 없습니다.")
    await create_activity_log(user_id,"order","주문 변경","order",order_id,rows[0].get("order_no"),rows[0].get("status")); return {"ok":True,"order":rows[0]}
@router.delete("/{order_id}")
async def remove_order(order_id:str,user_id:str=Depends(current_user_id)):
    rows=await delete("orders",{"id":f"eq.{order_id}","user_id":f"eq.{user_id}"});
    if not rows: raise HTTPException(404,"주문을 찾을 수 없습니다.")
    return {"ok":True}
