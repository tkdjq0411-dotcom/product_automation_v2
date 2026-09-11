# 2026-09-03 V2 SELL / HOLD / STOP

## 3단계 판정
- SELL: 순이익 2,000원 이상 AND 마진율 5% 이상
- HOLD: 순이익은 0원 초과지만 순이익 2,000원 또는 마진율 5% SELL 기준에 미달
- STOP: 판매가 0원 또는 순이익 0원 이하

## 구현
- 기존 9/2 SELL/STOP 기준 모듈을 확장하여 3단계 판정
- 상품 등록/수정 즉시 SELL/HOLD/STOP 자동판정
- SELL ↔ HOLD ↔ STOP 상태 변경 로그
- 개별/전체 재계산 3단계 지원
- 대시보드 SELL/HOLD/STOP 개별 집계
- HOLD 배지 및 대시보드 표시
- 판정 기준 API에 HOLD/STOP 의미 포함
- 사용자별 상품/로그 분리 유지
- 기존 인증/공급처/상품/계산엔진 회귀 유지

## 자동 검증
- 단위/통합/전환/회귀 테스트 47/47 PASS
- Python compile PASS
- JavaScript syntax PASS
- /, /health, /docs, /web/ HTTP 200

사용자 직접 테스트 및 승인 전까지 2026-09-03 일정은 미완료.
