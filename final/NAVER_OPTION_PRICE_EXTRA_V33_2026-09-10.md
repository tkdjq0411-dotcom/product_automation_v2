# NAVER OPTION PRICE / EXTRA OPTION V33

- Explicit B2B import now verifies the actual visible Naver purchase controls every time.
- Visible DOM option labels take priority for display, preserving +/- option price text.
- Passive network/state data remains stored as RAW/fallback data and is not shown as duplicate UI groups.
- Additional option count follows the actual visible additional-option controls when available.
- Internal network group names such as supplementProducts / standardCombinations are hidden from display.
- Leading/trailing parser underscores are removed only for display; meaningful internal underscores remain.
- Option price deltas are parsed into `value_details[].price_delta` when the sourcing form is saved.
- Additional-option section stays hidden when no real additional options are found.
- Chrome helper version: 2.20.0.
