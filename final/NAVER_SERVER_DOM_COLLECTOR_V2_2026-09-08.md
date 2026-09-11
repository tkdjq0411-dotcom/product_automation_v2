# Naver Server DOM Collector V2

- Chrome extension dependency removed from the sourcing flow.
- Server-side Playwright now reads the rendered Naver product UI directly.
- Exact sourcing mapping: product title, store, final displayed price, shipping fee, gallery-only images, all visible option groups, availability.
- Gallery extraction is limited to the product header/gallery and respects visible x/y gallery count when present.
- Options are opened/read interactively in the server-side browser, up to 30 option groups.
- Missing price/shipping values stay blank in the confirmation form instead of appearing as 0.
- No CAPTCHA/login/access-control bypass and no fabricated fallback values.
- Existing product/supplier/order/purchase/shipping functions are preserved.

Validation:
- Python compile PASS
- app/web/app.js syntax PASS
- direct rendered-state 1-7 mapping regression test PASS
- Live Naver marketplace request could not be run in this container because browser binaries/network are not available here; final PASS still requires the user's real Naver URL test.
