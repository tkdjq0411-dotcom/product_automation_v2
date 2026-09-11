from datetime import datetime
from fastapi import APIRouter,Depends,HTTPException
from app.db.supabase import select,insert,update
from app.modules.operations_common import current_user_id
from app.modules.shipping.schema import ShipmentCreate,ShipmentUpdate
from app.modules.activity_logs.service import create_activity_log
router=APIRouter()
@router.get("/")
async def list_rows(user_id:str=Depends(current_user_id)):
    rows=await select("shipments",{"user_id":f"eq.{user_id}","order":"created_at.desc"}); orders=await select("orders",{"user_id":f"eq.{user_id}"}); om={o['id']:o for o in orders}; return {"ok":True,"shipments":[{**r,"order":om.get(r['order_id'])} for r in rows]}
@router.post("/")
async def create_row(data:ShipmentCreate,user_id:str=Depends(current_user_id)):
    orders=await select("orders",{"id":f"eq.{data.order_id}","user_id":f"eq.{user_id}"});
    if not orders: raise HTTPException(404,"주문을 찾을 수 없습니다.")
    try: rows=await insert("shipments",{"user_id":user_id,**data.model_dump()})
    except Exception: raise HTTPException(400,"이미 배송 항목이 생성된 주문입니다.")
    await create_activity_log(user_id,"shipping","송장 등록","order",data.order_id,orders[0].get('order_no'),data.tracking_no); return {"ok":True,"shipment":rows[0]}
@router.patch("/{shipment_id}")
async def patch_row(shipment_id:str,data:ShipmentUpdate,user_id:str=Depends(current_user_id)):
    rows=await update("shipments",{"id":f"eq.{shipment_id}","user_id":f"eq.{user_id}"},{**data.model_dump(exclude_unset=True),"updated_at":datetime.now().isoformat()});
    if not rows: raise HTTPException(404,"배송 항목을 찾을 수 없습니다.")
    status=rows[0].get('status'); order_status='DONE' if status=='DELIVERED' else ('SHIPPING' if status in ('IN_TRANSIT','OUT_FOR_DELIVERY') else None)
    if order_status: await update("orders",{"id":f"eq.{rows[0]['order_id']}","user_id":f"eq.{user_id}"},{"status":order_status,"updated_at":datetime.now().isoformat()})
    await create_activity_log(user_id,"shipping","배송 상태 변경","shipment",shipment_id,None,status); return {"ok":True,"shipment":rows[0]}
