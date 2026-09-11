# 2026-09-07 V4 손익분기점 / 권장판매가

## 구현
- 현재 계산엔진 기준 손익분기점 역산
- 수수료/VAT를 판매가 연동 비용으로 반영
- SELL 순이익 기준 가격 역산
- SELL 마진율 기준 가격 역산
- 두 기준 중 더 높은 값을 권장판매가로 자동 선택
- 권장판매가까지 부족 금액 계산
- 현재 판매가의 권장가 충족 여부
- 상품별 가격분석 API
- 전체 상품 가격분석 API
- 웹 손익분기점/권장판매가 표
- 사용자별 데이터 분리
- 역산 불가능한 수수료+VAT 비율 보호
- 기존 인증/공급처/상품/계산/SELL-HOLD-STOP/재고/대시보드/로그 회귀 유지

## 기준식
- base_cost = 구매가 + 국제배송비 + 국내배송비
- variable_rate = 수수료율 + VAT율
- 손익분기점 = base_cost / (1 - variable_rate)
- 순이익 기준 가격 = (base_cost + 2,000) / (1 - variable_rate)
- 마진율 기준 가격 = base_cost / (1 - variable_rate - 0.05)
- 권장판매가 = max(순이익 기준 가격, 마진율 기준 가격)

## 자동검증
- 가격분석/격리/회귀 테스트 33/33 PASS
- Python compile PASS
- JavaScript syntax PASS
- /, /health, /docs, /web/ HTTP 200

사용자 직접 테스트 및 승인 전까지 2026-09-07 일정은 미완료.
