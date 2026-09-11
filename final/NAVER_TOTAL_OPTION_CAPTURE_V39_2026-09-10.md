# NAVER TOTAL OPTION CAPTURE V39 — 2026-09-10

Baseline: V38 Fixed Top Capture
Extension version: 2.26.0

## Changes
- Keep the main SmartStore page locked at the top purchase area. No `scrollIntoView` and no page-level option hunting.
- Allow programmatic reading/clicking of purchase-option controls that are below the current viewport, without scrolling the page. This lets the helper reach all genuine additional-option groups such as 도래류/채비류/봉돌류/튜닝류/미끼류/기타.
- Preserve V37/V38 shopper-action protection: 장바구니, 구매하기, 선물하기, 찜하기, 톡톡문의, 리뷰/구매평 are never activated by the collector.
- Add dependent mandatory-option mapping. The helper now iterates every first-level option value, re-reads the second-level option list after that parent is selected, and stores parent -> child variants.
- DOM-derived dependent variants are preferred for B2B display/ordering mapping; passive network variants remain as fallback RAW data.
- Option price deltas and sold-out labels remain preserved.

## Expected example
- 옵션 1 / 채비선택
  - 델리리그 2세대 -> its own 하위 옵션 목록
  - 델리리그 비비톤 -> its own 하위 옵션 목록 (+600원 / 품절 포함)
- 추가 옵션
  - 도래류
  - 채비류
  - 봉돌류
  - 튜닝류
  - 미끼류
  - 기타

## Validation
- `node --check chrome_extension/naver_source_helper/capture.js` PASS
- `node --check chrome_extension/naver_source_helper/background.js` PASS
- `python -m compileall -q app` PASS
