from datetime import datetime
from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import Response
from app.modules.auth.service import get_current_user_id
from app.modules.bulk_products.service import (
    import_products_service, export_csv_service, export_xlsx_service,
    template_csv, template_xlsx,
)

router=APIRouter()

@router.post("/import", summary="CSV/Excel 상품 대량 등록")
async def bulk_import(file: UploadFile=File(...), user_id: str=Depends(get_current_user_id)):
    result=await import_products_service(user_id,file.filename or "",await file.read())
    return {"ok":True,**result}

@router.get("/export.csv", summary="상품 CSV 내보내기")
async def export_csv(user_id: str=Depends(get_current_user_id)):
    name=f'products_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    return Response(await export_csv_service(user_id),media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition":f'attachment; filename="{name}"'})

@router.get("/export.xlsx", summary="상품 Excel 내보내기")
async def export_xlsx(user_id: str=Depends(get_current_user_id)):
    name=f'products_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    return Response(await export_xlsx_service(user_id),media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition":f'attachment; filename="{name}"'})

@router.get("/template.csv", summary="CSV 업로드 양식")
async def csv_template(user_id: str=Depends(get_current_user_id)):
    return Response(template_csv(),media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition":'attachment; filename="product_import_template.csv"'})

@router.get("/template.xlsx", summary="Excel 업로드 양식")
async def xlsx_template(user_id: str=Depends(get_current_user_id)):
    return Response(template_xlsx(),media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition":'attachment; filename="product_import_template.xlsx"'})
