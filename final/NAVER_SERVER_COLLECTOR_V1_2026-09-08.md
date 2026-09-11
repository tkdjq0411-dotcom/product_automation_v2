# Naver Server Collector V1
- Chrome extension dependency removed from sourcing flow.
- UI is URL -> server collection -> preview only.
- Naver collector isolated under app/modules/sourcing/collectors/naver.py.
- Missing values are never fabricated; incomplete fields are explicitly reported.
- Existing product/supplier/order/purchase/shipping functions are preserved.
- PASS is intentionally NOT declared until real Naver URLs are verified on the user's network.
