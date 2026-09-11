# Naver real-browser capture fallback

- Naver error/system pages are no longer accepted as partial product data.
- Shared UI placeholder images such as `sp_u_skip.png` are filtered.
- Added a local Chrome extension fallback for third-party Naver SmartStore pages.
- The extension reads the DOM and common hydrated page-state objects from the normal user Chrome page and sends them only to `127.0.0.1:8000`.
- B2B can poll the local capture and replace the blocked server result with the real browser result.
- No CAPTCHA/access-control bypass is implemented; the normal product page must be visible to the user in Chrome.
