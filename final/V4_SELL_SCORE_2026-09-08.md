# 2026-09-08 V4 SELL SCORE

## 점수 기준
- 총 100점
- 순이익 50점: 순이익 2,000원에서 50점 만점
- 마진율 50점: 마진율 5%에서 50점 만점
- 판매가 0원 또는 순이익 0원 이하는 0점
- 각 항목은 기준 초과 시 50점에서 상한

## 구현
- 중앙 SELL SCORE 계산 모듈
- 상품별 SELL SCORE API
- A/B/C/D 등급 제거: 점수는 상품 간 판매 우선순위 비교용
- 전체 상품 SELL SCORE API 및 점수 내림차순 정렬
- 순이익/마진 세부점수 제공
- 기존 상품 분석 대시보드 item에 SELL SCORE 연동
- 웹 SELL SCORE 순위표
- 상품 수정 시 최신 계산값으로 점수 즉시 재산정
- 사용자별 데이터 격리
- DB 스키마 변경 없음

## 자동검증
- 최초 SELL SCORE 자동검증 33/33 PASS
- 등급 제거 수정 후 집중 회귀검사 PASS
- Python compile PASS
- JavaScript syntax PASS
- /, /health, /docs, /web/ HTTP 200

사용자 직접 테스트 및 승인 전까지 2026-09-08 일정은 미완료.
