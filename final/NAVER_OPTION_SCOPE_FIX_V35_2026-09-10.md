# Naver Option Scope Fix V35

- Extension 2.22.0
- Fixes viewport-baseline bug that caused ordinary page text to be mistaken for option rows after scroll.
- Restricts fallback option extraction to newly appeared text geometrically aligned with the opened dropdown.
- Collapses nested duplicate combobox candidates.
- Freezes the actual additional-option control list before opening dropdowns, preventing fake additional option 3/4/5 groups.
- Keeps option +/- prices in the visible option label and internal price_delta data without rendering a second duplicate price badge.
- Keeps RAW network/state data as fallback; does not discard source data.
