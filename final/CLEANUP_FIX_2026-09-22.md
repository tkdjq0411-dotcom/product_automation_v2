# B2B SaaS 정리/문제 수정 1차

기준본: 2026-09-22 FINAL MVP

## 수정
- 사용자 입력 문자열을 HTML에 그대로 삽입하던 화면 출력부 이스케이프 처리
  - 상품명/SKU
  - 공급처명/메모
  - 활동 로그
  - 대량등록 오류 내용
  - 관리자 이메일 등
- 이미지 링크 href 출력 시 HTML attribute 이스케이프 및 noopener 적용
- 로그인 직후 요금제/사용량 자동 조회 누락 수정
- 상품 등록/삭제 및 대량등록 후 상품 사용량 즉시 갱신
- 로그인 후 독립 화면 데이터를 병렬 로딩하도록 변경
- 병렬 API 요청 시 로딩 표시가 먼저 꺼지는 문제를 요청 카운터 방식으로 수정

## 검증
- Backend 핵심 회귀 19/19 PASS
- XSS escape 테스트 PASS
- JavaScript syntax PASS
- Python compile PASS
