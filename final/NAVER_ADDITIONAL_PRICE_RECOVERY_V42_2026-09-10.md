# NAVER ADDITIONAL PRICE RECOVERY V42 — 2026-09-10

- Baseline: V41.
- Preserves real additional-option grouping/dedup behavior.
- Recovers buyer-visible +/- add-on prices from sibling/ancestor DOM rows while dropdown is open.
- Adds a second passive-network fallback for supplemental-product payloads whose add-on amount is stored as price/salePrice/etc. rather than addPrice.
- Does not restore internal duplicate groups to the UI.
- Keeps page-scroll lock, protected shopper-action blocking, dependent mandatory-option capture, and timeout recovery unchanged.
- Chrome helper version: 2.29.0.
