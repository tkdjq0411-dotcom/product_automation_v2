import csv,io
from fastapi import APIRouter,Depends
from fastapi.responses import StreamingResponse
from app.db.supabase import select
from app.modules.operations_common import current_user_id
router=APIRouter()
@router.get('/summary')
async def summary(user_id:str=Depends(current_user_id)):
    products=await select('products',{'user_id':f'eq.{user_id}'}); orders=await select('orders',{'user_id':f'eq.{user_id}'}); purchases=await select('purchase_orders',{'user_id':f'eq.{user_id}'}); shipments=await select('shipments',{'user_id':f'eq.{user_id}'})
    revenue=sum(float(o.get('sale_price') or 0) for o in orders if o.get('status')!='CANCELLED'); expected=sum(float(o.get('expected_profit') or 0) for o in orders if o.get('status')!='CANCELLED'); purchase=sum(float(x.get('amount') or 0) for x in purchases if x.get('status')=='PAID')
    return {'ok':True,'product_count':len(products),'sell_count':sum(1 for x in products if x.get('status')=='SELL'),'stop_count':sum(1 for x in products if x.get('status')!='SELL'),'order_count':len(orders),'revenue':revenue,'expected_profit':expected,'paid_purchase_amount':purchase,'shipping_count':len(shipments),'delivered_count':sum(1 for x in shipments if x.get('status')=='DELIVERED')}
@router.get('/orders.csv')
async def orders_csv(user_id:str=Depends(current_user_id)):
    rows=await select('orders',{'user_id':f'eq.{user_id}','order':'created_at.desc'}); s=io.StringIO(); w=csv.writer(s); w.writerow(['channel','order_no','product_name','option','quantity','sale_price','recipient','phone','address','status','expected_profit','created_at'])
    for o in rows:w.writerow([o.get('channel'),o.get('order_no'),o.get('product_name'),o.get('option_text'),o.get('quantity'),o.get('sale_price'),o.get('recipient'),o.get('phone'),(o.get('address') or '')+' '+(o.get('detail_address') or ''),o.get('status'),o.get('expected_profit'),o.get('created_at')])
    data=('\ufeff'+s.getvalue()).encode('utf-8'); return StreamingResponse(iter([data]),media_type='text/csv',headers={'Content-Disposition':'attachment; filename=orders_report.csv'})
