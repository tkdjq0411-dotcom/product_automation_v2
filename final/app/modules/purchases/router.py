from datetime import datetime
import json
from fastapi import APIRouter,Depends,HTTPException
from app.db.supabase import select,insert,update
from app.modules.operations_common import current_user_id
from app.modules.purchases.schema import PurchaseCreate,PurchaseUpdate
from app.modules.activity_logs.service import create_activity_log
router=APIRouter()


def _validate_for_payment(order:dict,purchase:dict|None)->list[str]:
    errors=[]
    if order.get('payment_status')!='PAID': errors.append('구매자 결제가 완료되지 않았습니다.')
    if order.get('status') in {'CANCELLED','CANCEL_REQUESTED','RETURN_REQUESTED','EXCHANGE_REQUESTED','REFUNDED'}: errors.append('취소·반품·교환 처리 중인 주문입니다.')
    if not order.get('recipient'): errors.append('수취인 이름이 없습니다.')
    if not order.get('phone'): errors.append('수취인 연락처가 없습니다.')
    if not order.get('address'): errors.append('배송 주소가 없습니다.')
    if not order.get('postal_code'): errors.append('우편번호가 없습니다.')
    if not (purchase and (purchase.get('supplier_url') or order.get('source_url'))): errors.append('공급처 상품 URL이 없습니다.')
    if purchase and float(purchase.get('amount') or 0)>float(order.get('sale_price') or 0): errors.append('공급처 결제금액이 구매자 결제금액보다 큽니다.')
    return errors
@router.get("/")
async def list_rows(user_id:str=Depends(current_user_id)):
    rows=await select("purchase_orders",{"user_id":f"eq.{user_id}","order":"created_at.desc"}); orders=await select("orders",{"user_id":f"eq.{user_id}"}); om={o['id']:o for o in orders}; return {"ok":True,"purchases":[{**r,"order":om.get(r['order_id'])} for r in rows]}
@router.post("/")
async def create_row(data:PurchaseCreate,user_id:str=Depends(current_user_id)):
    orders=await select("orders",{"id":f"eq.{data.order_id}","user_id":f"eq.{user_id}"});
    if not orders: raise HTTPException(404,"주문을 찾을 수 없습니다.")
    try: rows=await insert("purchase_orders",{"user_id":user_id,**data.model_dump()})
    except Exception: raise HTTPException(400,"이미 발주가 생성된 주문입니다.")
    await update("orders",{"id":f"eq.{data.order_id}","user_id":f"eq.{user_id}"},{"status":"READY","updated_at":datetime.now().isoformat()}); await create_activity_log(user_id,"purchase","발주 준비","order",data.order_id,orders[0].get('order_no')); return {"ok":True,"purchase":rows[0]}


@router.post("/prepare/{order_id}", summary="원클릭 발주 결제 직전 준비")
async def prepare_payment(order_id:str,user_id:str=Depends(current_user_id)):
    orders=await select("orders",{"id":f"eq.{order_id}","user_id":f"eq.{user_id}","limit":"1"})
    if not orders: raise HTTPException(404,"주문을 찾을 수 없습니다.")
    order=orders[0]
    found=await select("purchase_orders",{"order_id":f"eq.{order_id}","user_id":f"eq.{user_id}","limit":"1"})
    purchase=found[0] if found else None
    if not purchase:
        rows=await insert("purchase_orders",{"user_id":user_id,"order_id":order_id,"supplier_name":order.get('supplier_name'),"supplier_url":order.get('source_url'),"amount":0,"status":"READY"})
        purchase=rows[0]
    errors=_validate_for_payment(order,purchase)
    now=datetime.now().isoformat()
    payload={
        "order_no":order.get('order_no'),"product_name":order.get('product_name'),"option_text":order.get('option_text'),
        "quantity":order.get('quantity'),"recipient":order.get('recipient'),"phone":order.get('phone'),
        "postal_code":order.get('postal_code'),"address":order.get('address'),"detail_address":order.get('detail_address'),
        "delivery_memo":order.get('delivery_memo'),
    }
    status="BLOCKED" if errors else "READY_TO_PAY"
    rows=await update("purchase_orders",{"id":f'eq.{purchase["id"]}',"user_id":f"eq.{user_id}"},{
        "status":status,"validation_status":"FAILED" if errors else "PASSED","prepared_payload":json.dumps(payload,ensure_ascii=False),
        "prepared_at":now,"checkout_url":purchase.get('supplier_url') or order.get('source_url'),"updated_at":now,
    })
    await update("orders",{"id":f"eq.{order_id}","user_id":f"eq.{user_id}"},{"status":"PAYMENT_BLOCKED" if errors else "PAYMENT_READY","updated_at":now})
    await create_activity_log(user_id,"purchase","원클릭 발주 준비","order",order_id,order.get('order_no'),status)
    return {"ok":not errors,"ready":not errors,"errors":errors,"purchase":rows[0],"autofill":payload,
        "notice":"공급처 공식 API 또는 전용 연동 모듈이 연결되면 주문서 자동입력 후 결제 직전 화면을 엽니다."}
@router.patch("/{purchase_id}")
async def patch_row(purchase_id:str,data:PurchaseUpdate,user_id:str=Depends(current_user_id)):
    rows=await update("purchase_orders",{"id":f"eq.{purchase_id}","user_id":f"eq.{user_id}"},{**data.model_dump(exclude_unset=True),"updated_at":datetime.now().isoformat()});
    if not rows: raise HTTPException(404,"발주를 찾을 수 없습니다.")
    if rows[0].get('status')=='PAID': await update("orders",{"id":f"eq.{rows[0]['order_id']}","user_id":f"eq.{user_id}"},{"status":"ORDERED","updated_at":datetime.now().isoformat()});
    await create_activity_log(user_id,"purchase","발주 상태 변경","purchase",purchase_id,None,rows[0].get('status')); return {"ok":True,"purchase":rows[0]}
