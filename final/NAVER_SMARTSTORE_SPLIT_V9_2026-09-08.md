# NAVER SmartStore Split V9

- 브랜드스토어와 일반 SmartStore 수집 전략 분리
- PACIENCIA 등 브랜드스토어에서 성공한 기존 경로 보존
- SmartStore에서 JSON-LD Product → OG 메타 → 실제 상품 DOM 순으로 상품명 탐색
- SmartStore JSON-LD offers 가격 및 상품 이미지 보조 수집
- 네이버 공통 UI를 상품 데이터에서 강제 제외:
  - 비밀번호 표시/삭제, 스마트봇 상담, 고객센터, 언어선택
  - 한국어/English/中文/日本語/Tiếng Việt
- `UNSUPPORTED-네이버`, `네이버-네이버`, URL slug 공급처 생성 차단
- SmartStore 옵션은 구매영역의 실제 옵션 컨트롤만 후보로 인정
- 실패한 필드는 가짜값으로 채우지 않고 미수집 유지

네이버 전체 PASS 아님. 실제 여러 SmartStore/BrandStore URL 교차검증 필요.
