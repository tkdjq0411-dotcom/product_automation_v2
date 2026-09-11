# NAVER Commerce API - live own-store connection

## What changed
- Added local secret setup helper: `네이버_API_설정.bat`
- Own-store applications are forced to OAuth token type `SELF` and never send `account_id`.
- Token request explicitly uses `application/x-www-form-urlencoded`.
- Added process-local token cache and one refresh/retry on HTTP 401.
- Improved 401/403 diagnostics (key/token vs API group/IP/store permission).
- Existing NAVER integration card can run a real `/v1/seller/account` request.
- Added backend diagnostics for own-store account and a known origin product number.

## Local setup
1. Run `네이버_API_설정.bat`.
2. Paste the Application ID from Commerce API Center.
3. Paste the Application Secret (hidden input).
4. Restart the B2B server.
5. In Settings > channel integrations, NAVER should show `API 준비`.
6. Click `API 연결 테스트`.

Secrets remain in the local `.env` only. Do not paste the Application Secret into chat or screenshots.
