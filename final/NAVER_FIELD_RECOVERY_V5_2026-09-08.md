# NAVER FIELD RECOVERY V5

- Server-side Playwright only; no end-user extension.
- Scroll/wait pass to mount lazy purchase UI.
- Price: visible purchase area first, then verified structured product price. Never fabricate 0.
- Shipping: only explicit free/paid shipping text; missing remains missing.
- Images: visible gallery image currentSrc/src/srcset candidates, filtered to Naver product CDN.
- Options: expanded trigger matching, scroll-to-trigger and click/read groups.
- Rendered DOM is authoritative for Naver numeric fields.
- Naver remains PARTIAL until cross-store real URL tests pass.
