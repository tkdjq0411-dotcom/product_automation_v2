# 2026-09-11 V4 CSV / Excel 대량 처리

## 구현
- CSV(.csv), Excel(.xlsx) 상품 대량 등록
- UTF-8/UTF-8 BOM/CP949 CSV 지원
- 한 번에 최대 5,000행
- 각 행을 기존 상품 등록 서비스로 처리하여 계산엔진, SELL/HOLD/STOP, 로그가 그대로 적용
- 오류 행만 실패 처리하고 정상 행은 유지
- 오류 행 번호/상품명/SKU/사유 반환 및 화면 표시
- 중복 SKU/잘못된 값/필수 상품명 누락 검증
- CSV/Excel 업로드 양식 다운로드
- 현재 사용자 상품 CSV/Excel 내보내기
- 내보내기에 계산 결과, VAT, 순이익, 마진율, 상태 포함
- 사용자별 데이터 격리
- DB 스키마 변경 없음
- requirements: openpyxl, python-multipart 추가

## 검증
- CSV/Excel/부분성공/오류행/내보내기/격리/기존기능 회귀 31/31 PASS
- Python compile PASS
- JavaScript syntax PASS
- /, /health, /docs, /web/ HTTP 200

사용자 직접 테스트 및 승인 전까지 2026-09-11 일정은 미완료.
