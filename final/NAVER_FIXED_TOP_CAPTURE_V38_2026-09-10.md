# NAVER FIXED TOP CAPTURE V38

- Baseline: V37.
- Keeps the SmartStore page fixed at the top purchase panel during an explicit B2B capture.
- Removes all option `scrollIntoView()` calls.
- Rejects option clicks outside the current top purchase viewport.
- Restores scroll to top if SmartStore focus/dropdown behavior attempts to move the page.
- Existing shopper-action click guard remains unchanged.
- Product, image, price, shipping, option-price, additional-option and dedup logic are otherwise preserved.
- Extension version: 2.25.0.
