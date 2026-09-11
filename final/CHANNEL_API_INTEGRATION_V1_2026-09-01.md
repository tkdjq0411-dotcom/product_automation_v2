# 판매채널 API 연동 V1

## 구현
- 네이버 커머스API OAuth2 Client Credentials 인증 클라이언트
- 네이버 bcrypt + Base64 전자서명 생성
- 네이버 계정 API 연결 테스트
- 쿠팡 HMAC-SHA256 Authorization 생성
- 쿠팡 Open API 호출 클라이언트
- 쿠팡 주문 API 기반 연결 테스트
- 설정 화면에서 자격증명 준비 여부 표시
- 실제 Access/Secret 값은 브라우저나 SQLite에 저장하지 않음
- `.env.example` 제공

## 실제 키 입력 후 사용
1. `.env.example`을 참고하여 프로젝트의 `.env`에 실제 키 입력
2. 서버 재시작
3. 설정 > 판매 채널 연결에서 `API 연결 테스트`

## 다음 단계
- 네이버 변경 주문 조회 → 상세 주문 조회 → 내부 orders 저장
- 쿠팡 발주서 목록 조회 → 내부 orders 저장
- 중복 주문 방지 및 재동기화
- 송장/발송 상태 채널 역동기화
