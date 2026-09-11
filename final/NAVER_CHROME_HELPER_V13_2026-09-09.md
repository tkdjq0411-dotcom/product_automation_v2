# NAVER Chrome Helper V13

- Chrome helper protocol version 2.1.0
- Added helper heartbeat/status endpoints.
- B2B sourcing UI visibly distinguishes SERVER vs CHROME_HELPER.
- Shows helper connected/disconnected, version, last event, and capture delivery status.
- Extension triggers capture both via content script and tabs.onUpdated; background can inject capture.js if the content script was missed.
- Existing server collector remains as fallback.
- No hardcoded product/store values.
