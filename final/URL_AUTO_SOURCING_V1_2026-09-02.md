# URL 자동 소싱 V1 — 2026-09-02

## 목표
현재 프로젝트는 재고를 직접 보유하지 않는 판매자용 B2B 운영 자동화 SaaS다. 자체 재고수량/입고/출고/창고관리는 범위에서 제외하고 공급처 상품의 판매가능/품절 상태를 추적한다.

## 이번 구현
- 상품 소싱 화면을 URL 우선 흐름으로 변경
- 상품 URL 1개 붙여넣기 → 서버 자동분석 → 확인/수정 → 저장
- 플랫폼 자동 식별: Alibaba, AliExpress, Taobao, Tmall, 1688, Naver/SmartStore, Coupang, 11st, Gmarket, Auction, Amazon, eBay, 기타 일반 쇼핑몰
- JSON-LD Product / Open Graph / HTML meta 공개데이터 파서
- 상품명, 가격, 통화, 대표이미지, 공개 옵션, 상품번호, 판매가능/품절 상태 자동 추출 시도
- 소싱 DB에 플랫폼/원본 상품번호/통화/가져오기 상태/가져온 시각 저장
- URL fetch SSRF 방어: http/https만 허용, 로컬·사설망 차단, 리다이렉트마다 재검증
- CAPTCHA/로그인/접근제한 페이지는 우회하지 않고 API_REQUIRED 상태로 안내

## 중요한 범위
모든 오픈마켓의 모든 URL에서 동일한 정보가 100% 추출된다고 보장할 수 없다. 플랫폼별로 로그인, JavaScript 동적 렌더링, CAPTCHA, API 권한 및 약관 제한이 다르다. V1은 공개 상품 메타데이터를 공통 방식으로 최대한 가져오는 기반이며, 제한되는 플랫폼은 공식 API/제휴 API 어댑터를 붙이는 방식으로 확장한다.

## 테스트
- Python compileall PASS
- JavaScript node --check PASS
- SQLite sourcing migration PASS
- JSON-LD/OpenGraph 파서 샘플 PASS
- 회원가입/로그인/소싱 저장/조회 FLOW PASS
