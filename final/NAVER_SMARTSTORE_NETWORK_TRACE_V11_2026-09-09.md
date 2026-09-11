# NAVER SmartStore Network Trace V11

- Brand Store extraction path preserved.
- SmartStore browser collection now blocks service-worker caching so product responses are observable by the server browser.
- Records Naver response metadata automatically and retains response bodies only when they are tied to the requested product ID or a product-related endpoint.
- For opaque SmartStore endpoints, the exact `/products/{id}` value in the response body is used as the anchor.
- If the SmartStore SPA shell does not expose the requested product after the initial load, the same public URL is retried once in the same server browser context.
- Diagnostics include `smartstore_product_seen`, `product_anchored_blob_count`, and a bounded Naver response trace.
- No login/CAPTCHA/access-control bypass is used. Missing data remains missing rather than fabricated.
