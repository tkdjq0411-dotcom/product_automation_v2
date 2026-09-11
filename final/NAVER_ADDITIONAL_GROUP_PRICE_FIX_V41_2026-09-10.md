# Naver Additional Group + Price Fix V41

- Extension version: 2.28.0
- Baseline: V40 capture recovery.
- Preserve the V40 timeout, top purchase-panel lock, protected shopper-action clicks, dependent mandatory options, images, price, shipping, and RAW network/state data.
- Additional options are normalized by value-set identity. Near-identical internal aliases such as `추가옵션5` are merged into the real buyer-visible group name such as `도래류`.
- Synthetic mega-groups that are unions of multiple real add-on dropdowns are hidden from the B2B display while RAW data remains preserved.
- Mandatory option groups cannot be duplicated as additional-option groups.
- Checkbox/radio add-on rows now read the whole buyer-visible row so a price rendered in a sibling span, e.g. `(+4,500원)`, is retained.
- B2B options JSON now stores `additional_value_details` with parsed `price_delta` for add-ons as well as normal options.
