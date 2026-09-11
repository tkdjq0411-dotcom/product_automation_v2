# V34 option price capture fix

- Keeps V33 sourcing / option / additional-option architecture unchanged.
- Reads each Naver option popup row as a complete buyer-visible row so nested +/- price spans are not dropped.
- If the visible DOM label still lacks the delta, enriches it from passive network/state option values or variant additional_price by matching the same option text.
- Preserves zero-price/default options without adding a fake price.
- Existing additional-option deduplication and display cleanup are unchanged.
- Chrome helper version: 2.21.0.
