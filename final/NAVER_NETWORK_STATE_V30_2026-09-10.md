# NAVER Chrome Helper V30 — Network/State Collector

- Baseline: V29 dynamic option UI.
- Core product name/price/shipping/supplier logic preserved.
- New passive MAIN-world hook captures SmartStore fetch/XHR JSON at document_start without clicking or scrolling.
- Current product ID is used to scope captured state.
- Product gallery URLs and mandatory/additional option groups are extracted from hydrated/network state first.
- Existing gallery carousel and interactive option reader are fallback only.
- UI renders only actual collected option groups; no empty slots.
- Normal Naver browsing is not moved or clicked by the new network hook.
- Chrome helper version: 2.17.0.
