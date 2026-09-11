# NAVER NETWORK RECOVERY V6 — 2026-09-08

네이버 상품소싱 서버 Collector의 PARTIAL 구간 보강.

- 기존 성공 경로(상품명/상점명/대표이미지 DOM 수집) 유지
- Playwright가 실제 상품 페이지를 여는 동안 브라우저가 정상 수신한 JSON/XHR 응답을 분석
- 가격은 final/benefit/discount/sale 계열의 명시적 가격 필드만 인정
- 배송비는 delivery/shipping fee 계열의 명시적 필드만 인정하며 0은 실제 무료배송 데이터일 때만 허용
- 상품 이미지 배열과 옵션 그룹을 네트워크 응답에서 복구
- DOM 값 우선, 네트워크 값은 비어 있는 필드만 보완
- URL slug를 상점 표시명으로 사용하지 않음
- 누락값을 임의 생성하지 않음
- 네트워크 복구 결과를 collector diagnostics에 기록

검증: Python compile PASS, synthetic network recovery regression PASS.
실제 네이버 PASS는 사용자 실페이지 교차 테스트 후 결정.
