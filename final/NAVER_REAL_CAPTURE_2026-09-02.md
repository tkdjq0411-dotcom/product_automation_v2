# Naver real URL sourcing capture

- HTTP HTML alone is not treated as success.
- Windows Playwright runs in a separate worker process.
- Worker prefers installed stable Chrome and falls back to bundled Chromium.
- Captures product-related JSON/XHR responses that the page itself legitimately receives.
- Reads common in-page JSON states (`__NEXT_DATA__`, `__APOLLO_STATE__`, etc.).
- Parses those payloads for title, price, currency, options, images, availability and source product ID.
- Naver error/access-restriction documents are never saved as products.
- No CAPTCHA or access-control bypass is implemented.
