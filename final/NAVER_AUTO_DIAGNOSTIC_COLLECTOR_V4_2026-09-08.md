# Naver Auto Diagnostic Collector V4

## Fixed root regression
The server Playwright extraction block in `browser_worker.py` had been serialized into one physical Python comment line with literal `\\n` tokens. As a result, the rendered-DOM collector never executed and the server silently fell back to incomplete HTTP metadata. This explains the repeated URL-slug supplier values and missing title/price/images/options.

## V4 changes
- Restored the Playwright rendered-DOM extraction block to executable Python/JavaScript.
- Corrected escaped JavaScript regex tokens inside the Playwright evaluator.
- Added structured automatic diagnostics for browser launch, navigation, DOM extraction, network capture and completion.
- Browser-worker failures are returned to the parent collector instead of being silently discarded.
- Naver URL slugs such as `mililabkorea` are no longer presented as verified store names when browser rendering did not verify the visible store label.
- Missing values are never fabricated.
- No Chrome extension is required.

## Validation
- Python compileall: PASS
- browser_worker.py compile: PASS
- rendered DOM JavaScript syntax (`node --check`): PASS
- frontend app.js syntax: PASS
- automatic diagnostic / URL-slug rejection unit check: PASS
- local environment browser-launch failure correctly classified as structured `launch_browser` diagnostic: PASS

Real Naver marketplace PASS is not declared until the user runs different real Naver product URLs on the target Windows environment and the 1-7 sourcing fields are verified.
