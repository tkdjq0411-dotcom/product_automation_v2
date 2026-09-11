from datetime import datetime
from fastapi import APIRouter,Depends,HTTPException
from app.db.supabase import select,insert,update
from app.modules.operations_common import current_user_id
from app.modules.automation.schema import RuleUpdate
from app.modules.products.service import all_product_pricing_analysis_service, update_product_service
from app.modules.activity_logs.service import create_activity_log
router=APIRouter()

def b(v): return 1 if v else 0
@router.get('/rules')
async def rules(user_id:str=Depends(current_user_id)):
    products=await select('products',{'user_id':f'eq.{user_id}','order':'created_at.desc'})
    rr=await select('price_automation_rules',{'user_id':f'eq.{user_id}'})
    tt=await select('price_trackers',{'user_id':f'eq.{user_id}'})
    pricing=await all_product_pricing_analysis_service(user_id)
    rm={x['product_id']:x for x in rr}; tm={x['product_id']:x for x in tt}; pm={x['product_id']:x for x in pricing}
    out=[]
    for prod in products:
        r=rm.get(prod['id']) or {'enabled':1,'undercut_amount':100,'auto_stop':1,'auto_resume':1}
        t=tm.get(prod['id']) or {}; floor=float(pm.get(prod['id'],{}).get('minimum_sellable_price') or 0); comp=t.get('competitor_price')
        target=None if comp is None else max(floor,float(comp)-float(r.get('undercut_amount') or 0))
        action='WAIT' if comp is None else ('STOP' if float(comp)<floor else 'ADJUST')
        out.append({'product':prod,'rule':r,'tracker':t,'minimum_sellable_price':floor,'target_price':target,'action':action})
    return {'ok':True,'rules':out}
@router.patch('/rules/{product_id}')
async def save_rule(product_id:str,data:RuleUpdate,user_id:str=Depends(current_user_id)):
    prods=await select('products',{'id':f'eq.{product_id}','user_id':f'eq.{user_id}'})
    if not prods: raise HTTPException(404,'상품을 찾을 수 없습니다.')
    payload=data.model_dump(exclude_unset=True)
    for k in ('enabled','auto_stop','auto_resume'):
        if k in payload: payload[k]=b(payload[k])
    payload['updated_at']=datetime.now().isoformat()
    rows=await select('price_automation_rules',{'user_id':f'eq.{user_id}','product_id':f'eq.{product_id}'})
    out=await update('price_automation_rules',{'id':f'eq.{rows[0]["id"]}'},payload) if rows else await insert('price_automation_rules',{'user_id':user_id,'product_id':product_id,**payload})
    return {'ok':True,'rule':out[0]}
@router.post('/run')
async def run_all(user_id:str=Depends(current_user_id)):
    products=await select('products',{'user_id':f'eq.{user_id}'})
    rr=await select('price_automation_rules',{'user_id':f'eq.{user_id}'})
    tt=await select('price_trackers',{'user_id':f'eq.{user_id}'})
    pricing=await all_product_pricing_analysis_service(user_id)
    rm={x['product_id']:x for x in rr}; tm={x['product_id']:x for x in tt}; pm={x['product_id']:x for x in pricing}
    results=[]
    for prod in products:
        r=rm.get(prod['id']) or {'enabled':1,'undercut_amount':100,'auto_stop':1,'auto_resume':1}
        if not int(r.get('enabled',1)): continue
        t=tm.get(prod['id']); comp=t.get('competitor_price') if t else None
        if comp is None: continue
        floor=float(pm.get(prod['id'],{}).get('minimum_sellable_price') or 0); old=float(prod.get('selling_price') or 0); comp=float(comp)
        action='NONE'; new=old; reason='변경 없음'
        if comp < floor and int(r.get('auto_stop',1)):
            await update('products',{'id':f'eq.{prod["id"]}','user_id':f'eq.{user_id}'},{'status':'STOP','status_reason':'경쟁 최저가가 최저 판매 가능가 미만'})
            action='STOP'; reason='경쟁가가 수익 안전선 미만'
        elif comp >= floor:
            target=max(floor,comp-float(r.get('undercut_amount') or 0))
            if abs(target-old)>=1 or (prod.get('status')=='STOP' and int(r.get('auto_resume',1))):
                updated=await update_product_service(user_id,prod['id'],{'selling_price':target}); new=float(updated.get('selling_price') or target); action='PRICE_CHANGE'; reason='경쟁가 기준 자동 조정'
        if action!='NONE':
            await insert('price_history',{'user_id':user_id,'product_id':prod['id'],'competitor_price':comp,'old_price':old,'new_price':new,'minimum_sellable_price':floor,'action':action,'reason':reason})
            await create_activity_log(user_id,'automation','가격 자동화','product',prod['id'],prod.get('name'),f'{action}: {old} → {new}')
            results.append({'product_id':prod['id'],'name':prod.get('name'),'action':action,'old_price':old,'new_price':new,'floor':floor,'competitor_price':comp})
    return {'ok':True,'changed':len(results),'results':results}
@router.get('/history')
async def history(user_id:str=Depends(current_user_id)):
    rows=await select('price_history',{'user_id':f'eq.{user_id}','order':'created_at.desc','limit':'200'}); return {'ok':True,'history':rows}
