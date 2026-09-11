from fastapi import APIRouter,Depends
from app.db.supabase import select,insert
from app.modules.operations_common import current_user_id
from app.modules.ai_content.schema import DraftCreate
from app.modules.activity_logs.service import create_activity_log
router=APIRouter()
@router.get("/")
async def list_drafts(user_id:str=Depends(current_user_id)):
    rows=await select("ai_drafts",{"user_id":f"eq.{user_id}","order":"created_at.desc"}); return {"ok":True,"drafts":rows}
@router.post("/draft")
async def create_draft(data:DraftCreate,user_id:str=Depends(current_user_id)):
    name=data.source_name.strip(); title=f"{name} | 실사용 중심 핵심 구성"; description=f"[상세페이지 초안]\n{name}을 찾는 고객이 핵심 정보를 빠르게 이해할 수 있도록 구성했습니다.\n\n1. 상품 핵심 정보\n- 제품명: {name}\n- 옵션/구성은 실제 공급처 정보를 기준으로 최종 확인\n\n2. 구매 포인트\n- 필요한 정보를 한 화면에서 확인\n- 옵션과 구성의 혼동을 줄이는 설명\n- 구매 전 체크사항을 명확하게 안내\n\n3. FAQ\nQ. 옵션은 어떻게 선택하나요?\nA. 판매 페이지의 옵션 구성을 확인해 주세요.\nQ. 배송 일정은 어떻게 확인하나요?\nA. 주문 후 등록되는 운송장 정보로 확인할 수 있습니다.\n\n※ 실제 판매 전 공급처 사양·인증·표시사항을 반드시 검수하세요."; keywords=", ".join([name,"온라인판매","상품추천","구매가이드","빠른배송","실사용"]); selling_points="• 핵심 사양을 빠르게 확인\n• 옵션/구성 정리\n• 구매 전 확인사항 안내\n• 채널 등록용 제목/키워드 초안 제공"
    rows=await insert("ai_drafts",{"user_id":user_id,"product_id":data.product_id,"source_name":name,"title":title,"description":description,"keywords":keywords,"selling_points":selling_points}); await create_activity_log(user_id,"ai","상품 초안 생성","ai_draft",rows[0]['id'],name); return {"ok":True,"draft":rows[0],"mode":"local_template"}
