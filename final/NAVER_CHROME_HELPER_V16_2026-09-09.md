# NAVER CHROME HELPER V16

- Chrome helper version: 2.4.0
- Normal Naver browsing is now fully idle: no automatic capture, gallery movement, option opening, review/popup interaction, or MutationObserver capture.
- Helper runs only when B2B 상품 소싱의 URL 가져오기가 explicitly opens a URL marked with `__b2b_capture=1`.
- The marker is removed before the original source URL is sent back to B2B.
- Extension icon click no longer triggers page manipulation.
- Existing V15 sourcing/price/shipping/gallery/options logic is preserved and executes only during an explicit import.
