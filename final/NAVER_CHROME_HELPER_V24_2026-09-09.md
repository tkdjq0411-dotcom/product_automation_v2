# NAVER CHROME HELPER V24

- V22 known-good active rendering path restored.
- V23 hidden/inactive helper-tab strategy removed because Naver did not fully render product data in background tabs.
- Capture tab is opened only for explicit B2B import, then automatically returns to the B2B tab and closes after successful delivery.
- Product title: OG/title first, exact store suffix removed only.
- Price: purchase price candidates exclude shipping/points/coupon text; structured price fallback retained.
- Gallery: main image + thumbnail rail + 1/N counter traversal.
- V22 option/additional-option module preserved unchanged (up to 30 groups).
- Extension version 2.12.0.
