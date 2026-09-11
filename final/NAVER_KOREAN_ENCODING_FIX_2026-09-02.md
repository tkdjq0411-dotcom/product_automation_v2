# 네이버 한글 인코딩 수정

- Windows Playwright worker와 FastAPI 프로세스 사이 JSON 전달을 UTF-8로 강제
- HTTP 응답을 Content-Type charset / UTF-8 / CP949 / EUC-KR 후보로 안전하게 디코딩
- 흔한 UTF-8 mojibake 복구 로직 추가
- U+FFFD(�) 등 복구 불가능한 깨진 문자열은 상품명/설명/옵션으로 저장하지 않음
- HTTP 200 여부와 상품 수집 성공 여부는 계속 분리
- 실데이터가 없는 경우 가짜 값 생성 없음
