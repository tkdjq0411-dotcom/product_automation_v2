# 2026-09-16 보안 / 데이터 검증 강화

기존 기능/DB 구조를 유지한 최소 변경입니다.

- 회원가입 이메일 정규화 및 형식/길이 검증
- 로그인 이메일 대소문자/공백 정규화
- 인증 헤더 길이 제한 및 Bearer 파싱 강화
- 기존 토큰 서명/만료/로그아웃 검증 유지
- 상품 숫자 NaN/Infinity/음수/과대값 차단
- SKU/검색어/URL 길이 제한
- 이미지 URL은 http/https만 허용
- 계산 입력 NaN/Infinity/범위 및 tax_type 검증
- 재고 수량/최소재고 상한 검증
- 검색/필터/정렬 파라미터 경계 검증
- CSV/XLSX 업로드 10MB 제한 + 기존 5000행 제한 유지
- 사용자 간 상품/재고/공급처 접근 격리 재검증
- 관리자 API 일반 사용자 차단 재검증
- API 응답에서 password_hash 미노출 재검증

검증:
- 보안/비정상 입력/권한/격리 48/48 PASS
- 기존 기능 전체 회귀 33/33 PASS
- Python compile PASS
- JavaScript syntax PASS
- /, /health, /docs, /web/ 200

사용자 직접 테스트 승인 전까지 미완료.
