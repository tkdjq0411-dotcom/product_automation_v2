# Naver SmartStore Frame Recovery V10

- Brand Store extraction path preserved.
- Ordinary SmartStore now inspects Naver child frames when the top document only exposes common NAVER UI.
- Child-frame product title/store/price/shipping/image/options are used only to fill missing main-document fields.
- Exact product-id inline state inside child frames is added to the existing product-anchored parser.
- Response capture now also accepts an HTML response when its URL is explicitly anchored to the requested product id.
- No URL slug is promoted to a visible store name.
- No Chrome extension is required for this path.
- Existing common-UI rejection remains active.
