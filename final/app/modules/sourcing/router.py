from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from app.db.supabase import select,insert,update,delete
from app.modules.operations_common import current_user_id
from app.modules.sourcing.schema import SourcingCreate,SourcingUpdate,URLImportRequest
from app.modules.sourcing.collectors import collect_product
from app.modules.activity_logs.service import create_activity_log
from app.modules.suppliers.service import create_supplier_service
router=APIRouter()

# Chrome helper connection diagnostics (ephemeral, local-only).
_HELPER_STATUS = {"last_seen": 0.0, "version": None, "last_event": None, "last_error": None}

@router.post("/browser-helper-heartbeat")
async def browser_helper_heartbeat(request: Request):
    import time
    body = await request.json()
    _HELPER_STATUS["last_seen"] = time.time()
    _HELPER_STATUS["version"] = str(body.get("version") or "").strip() or None
    _HELPER_STATUS["last_event"] = str(body.get("event") or "heartbeat").strip()
    _HELPER_STATUS["last_error"] = str(body.get("error") or "").strip() or None
    return {"ok": True}

@router.get("/browser-helper-status")
async def browser_helper_status():
    import time
    age = time.time() - float(_HELPER_STATUS.get("last_seen") or 0)
    connected = bool(_HELPER_STATUS.get("last_seen")) and age <= 120
    return {
        "ok": True,
        "connected": connected,
        "age_seconds": round(age, 1) if _HELPER_STATUS.get("last_seen") else None,
        "version": _HELPER_STATUS.get("version"),
        "last_event": _HELPER_STATUS.get("last_event"),
        "last_error": _HELPER_STATUS.get("last_error"),
    }

# Local Chrome helper capture endpoint. Capture data is ephemeral and keyed by product URL.
@router.post("/browser-capture")
async def browser_capture(request: Request):
    from app.modules.sourcing.browser_capture import save_capture
    body=await request.json()
    url=str(body.get("url") or "").strip()
    if not url:
        raise HTTPException(400,"url required")
    try:
        preview=save_capture(url, str(body.get("html") or ""), str(body.get("title") or ""), body.get("state"))
    except ValueError as exc:
        raise HTTPException(400,str(exc)) from exc
    return {"ok":True,"preview":preview}

@router.get("/browser-capture-status")
async def browser_capture_status(url: str):
    from app.modules.sourcing.browser_capture import get_capture
    return {"ok":True,"preview":get_capture(url)}


@router.get("/")
async def list_items(user_id:str=Depends(current_user_id)):
    rows=await select("sourcing_items",{"user_id":f"eq.{user_id}","order":"created_at.desc"}); return {"ok":True,"items":rows}

@router.post("/import-url")
async def import_url(data:URLImportRequest,user_id:str=Depends(current_user_id)):
    try:
        from app.modules.sourcing.browser_capture import get_capture
        captured=get_capture(data.url)
        if captured:
            item=captured
            item["extension_required"]=False
            item["import_message"]="Chrome 도우미가 실제 네이버 상품 화면에서 수집한 값입니다."
        else:
            item=await collect_product(data.url)
            if str(item.get("platform") or "").startswith("NAVER") and item.get("import_status") != "OK":
                item["extension_required"]=True
                item["import_message"]=(item.get("import_message") or "") + " · Chrome 도우미로 실페이지 자동수집을 시도합니다."
    except ValueError as exc:
        raise HTTPException(400,str(exc)) from exc
    except Exception as exc:
        raise HTTPException(502,"상품 페이지를 자동으로 분석하지 못했습니다. 공식 API가 필요한 사이트일 수 있습니다.") from exc
    # Match an existing supplier by stable store URL/name, but do not create records until the user saves.
    supplier_id = None
    suppliers = await select("suppliers", {"user_id": f"eq.{user_id}"})
    for supplier in suppliers:
        if item.get("supplier_store_url") and supplier.get("store_url") == item.get("supplier_store_url"):
            supplier_id = supplier.get("id"); break
        if item.get("supplier_name") and str(supplier.get("name") or "").casefold() == str(item.get("supplier_name")).casefold():
            supplier_id = supplier.get("id"); break
    item["matched_supplier_id"] = supplier_id
    await create_activity_log(user_id,"sourcing","URL 자동분석","sourcing",None,item.get("product_name") or item.get("platform"),data.url)
    return {"ok":True,"preview":item}

@router.post("/")
async def create_item(data:SourcingCreate,user_id:str=Depends(current_user_id)):
    values=data.model_dump()
    supplier_name=(values.pop("supplier_name",None) or "").strip() or None
    supplier_id=values.get("supplier_id")
    if not supplier_id and supplier_name:
        existing=await select("suppliers", {"user_id": f"eq.{user_id}"})
        for s in existing:
            if values.get("supplier_store_url") and s.get("store_url")==values.get("supplier_store_url"):
                supplier_id=s.get("id"); break
            if str(s.get("name") or "").casefold()==supplier_name.casefold():
                supplier_id=s.get("id"); break
        if not supplier_id:
            supplier=await create_supplier_service(user_id,{
                "name":supplier_name,
                "memo":"URL 자동소싱으로 생성된 공급처",
                "source_platform":values.get("source_platform"),
                "store_name":values.get("supplier_store_name"),
                "store_url":values.get("supplier_store_url"),
            })
            supplier_id=supplier.get("id")
    values["supplier_id"]=supplier_id
    payload={"user_id":user_id,**values,"imported_at":datetime.now().isoformat() if values.get("source_url") else None}
    rows=await insert("sourcing_items",payload); item=rows[0]; await create_activity_log(user_id,"sourcing","등록","sourcing",item["id"],item["product_name"],item.get("source_url")); return {"ok":True,"item":item}

@router.patch("/{item_id}")
async def patch_item(item_id:str,data:SourcingUpdate,user_id:str=Depends(current_user_id)):
    rows=await update("sourcing_items",{"id":f"eq.{item_id}","user_id":f"eq.{user_id}"},{**data.model_dump(exclude_unset=True),"updated_at":datetime.now().isoformat()});
    if not rows: raise HTTPException(404,"소싱 항목을 찾을 수 없습니다.")
    return {"ok":True,"item":rows[0]}

@router.delete("/{item_id}")
async def remove_item(item_id:str,user_id:str=Depends(current_user_id)):
    rows=await delete("sourcing_items",{"id":f"eq.{item_id}","user_id":f"eq.{user_id}"});
    if not rows: raise HTTPException(404,"소싱 항목을 찾을 수 없습니다.")
    await create_activity_log(user_id,"sourcing","삭제","sourcing",item_id,rows[0].get("product_name")); return {"ok":True}

