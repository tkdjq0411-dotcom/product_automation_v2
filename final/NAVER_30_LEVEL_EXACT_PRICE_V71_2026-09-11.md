# NAVER V71 — exact current price + dependent options up to 30 groups

- Purchase price: reads the current number from the parent of `span.blind` whose text is exactly `상품 가격`; no hard-coded price.
- Mandatory options: reads `pcs.optselect` groups up to 30 groups.
- Dependent options: selects each parent value and re-reads the next generated group recursively, up to 30 levels.
- Option labels preserve buyer-visible `(+/- N원)` text and stock status when present.
- Additional options remain isolated from mandatory options via `pcs.addedoptselect`.
- Safety ceiling for generated dependent combinations: 50,000 variants; interactive hard timeout: 10 minutes.
