# NAVER Commerce API 자동 설정

- 네이버 내 스토어 애플리케이션 자격증명을 최초 실행 시 자동 적용합니다.
- 최초 `실행.bat` 실행 시 평문 부트스트랩은 프로젝트 밖 사용자 로컬 설정으로 이동되고 프로젝트에서 삭제됩니다.
- Windows 저장 위치: `%LOCALAPPDATA%\B2B_SaaS\secrets\credentials.env`
- 이후 새 프로젝트 ZIP으로 교체해도 같은 PC에서는 자격증명을 다시 입력할 필요가 없습니다.
- 프로젝트 `.env`, 브라우저, SQLite DB에는 네이버 시크릿을 저장하지 않습니다.
- `NAVER_COMMERCE_TOKEN_TYPE=SELF`를 사용하며 `account_id`는 보내지 않습니다.
- 최초 정상 실행 후 다운로드한 설정용 ZIP 원본은 별도 보관하지 않는 것을 권장합니다.
