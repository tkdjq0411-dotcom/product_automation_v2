# 2026-09-09 V4 리스크 분석

## 목적
SELL/HOLD/STOP과 SELL SCORE를 변경하지 않고 상품의 위험요소를 별도로 표시합니다.

## 리스크
- 판매가 0원: HIGH
- 순이익 0원 이하: HIGH
- 순이익 2,000원 미만: MEDIUM
- 마진율 5% 미만: MEDIUM, 0% 이하 HIGH
- 권장판매가 미달: MEDIUM
- 재고 0개: HIGH
- 현재재고가 최소재고 이하: MEDIUM

하나라도 HIGH가 있으면 상품 위험도 HIGH, HIGH 없이 MEDIUM만 있으면 MEDIUM,
위험요소가 없으면 LOW입니다.

## 구현
- 독립 리스크 엔진
- 전체/상품별/요약 리스크 API
- HIGH 우선 정렬
- 통합 대시보드 리스크 요약 및 고위험 상품 연동
- 웹 리스크 요약/상품별 위험요소 표
- 사용자 데이터 격리
- DB 스키마 변경 없음
- 기존 SELL SCORE/SELL-HOLD-STOP/가격분석/재고 기능 유지

## 검증
- 리스크/재고경계/격리/기존기능 회귀 33/33 PASS
- Python compile PASS
- JavaScript syntax PASS
- /, /health, /docs, /web/ HTTP 200

사용자 직접 테스트 및 승인 전까지 2026-09-09 일정은 미완료.
