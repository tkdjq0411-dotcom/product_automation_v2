from datetime import datetime
from fastapi import APIRouter,Depends,HTTPException
from app.db.supabase import select,insert,update
from app.modules.operations_common import current_user_id
from app.modules.price_tracking.schema import TrackerUpdate
from app.modules.products.service import all_product_pricing_analysis_service
from app.modules.activity_logs.service import create_activity_log
router=APIRouter()
@router.get("/")
async def list_rows(user_id:str=Depends(current_user_id)):
    products=await select("products",{"user_id":f"eq.{user_id}","order":"created_at.desc"}); trackers=await select("price_trackers",{"user_id":f"eq.{user_id}"}); tm={t['product_id']:t for t in trackers}; pricing=await all_product_pricing_analysis_service(user_id); pm={p['product_id']:p for p in pricing}
    out=[]
    for p in products:
        t=tm.get(p['id']); floor=pm.get(p['id'],{}).get('minimum_sellable_price',0); comp=t.get('competitor_price') if t else None; rec='SELL' if comp is None or float(comp)>=float(floor or 0) else 'STOP'
        out.append({"product":p,"tracker":t,"minimum_sellable_price":floor,"recommendation":rec})
    return {"ok":True,"tracking":out}
@router.patch("/{product_id}")
async def patch_row(product_id:str,data:TrackerUpdate,user_id:str=Depends(current_user_id)):
    prods=await select("products",{"id":f"eq.{product_id}","user_id":f"eq.{user_id}"});
    if not prods: raise HTTPException(404,"상품을 찾을 수 없습니다.")
    existing=await select("price_trackers",{"product_id":f"eq.{product_id}","user_id":f"eq.{user_id}"}); payload=data.model_dump(exclude_unset=True);
    if 'tracking_enabled' in payload: payload['tracking_enabled']=1 if payload['tracking_enabled'] else 0
    payload.update({"last_checked_at":datetime.now().isoformat(),"updated_at":datetime.now().isoformat()})
    rows=await update("price_trackers",{"id":f"eq.{existing[0]['id']}"},payload) if existing else await insert("price_trackers",{"user_id":user_id,"product_id":product_id,"created_at":datetime.now().isoformat(),**payload})
    await create_activity_log(user_id,"price","경쟁가 확인","product",product_id,prods[0].get('name'),str(payload.get('competitor_price'))); return {"ok":True,"tracker":rows[0]}
