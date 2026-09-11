# NAVER mandatory option price final V45

- Baseline: V44 purchase-price accuracy.
- Keeps all V44 sourcing behavior intact.
- Adds a geometry-based option-row resolver for mandatory and dependent options.
- Reconstructs buyer-visible option label + sibling +/- price even when Naver renders them in separate DOM nodes.
- Uses three layers for option delta: row DOM text -> sibling/geometry price -> passive network/state enrichment.
- Does not alter page-wide scrolling, shopper-action protection, product title, purchase price, shipping, image or additional-option dedup behavior.
- Extension version: 2.32.0.
