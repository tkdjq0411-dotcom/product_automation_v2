# NAVER dedicated option price collector V50

- Clean baseline: V45. Failed V46-V49 experimental capture changes are not included.
- Leaves the existing title, purchase-price, shipping, image, option, dependent-option and add-on collector intact.
- Adds one isolated MAIN-world module that reads only explicit real option surcharge fields from Naver's already-loaded JSON/state/network responses.
- Never invents a price, never derives it from coupons/points/shipping, and never clicks an option or shopper action.
- Matches confirmed surcharge values back to the existing option labels.
- Forces each explicit Naver import to wait for a new capture instead of reusing a recent stale preview.
- Extension and heartbeat version: 2.37.0.
