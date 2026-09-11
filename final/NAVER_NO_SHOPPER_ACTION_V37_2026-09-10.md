# Naver Helper V37 — Shopper Action Safety Guard

- Extension version: 2.24.0
- Blocks shopper actions during explicit B2B capture: cart, purchase, buy-now, gift, wishlist, TalkTalk/inquiry, review/rating.
- Guard operates in capture phase for pointerdown/mousedown/mouseup/click so accidental selector matches cannot activate page handlers.
- Added a second refusal check before every helper-triggered click path (option trigger, dependent-option unlock, gallery next).
- Guard is installed only while a B2B capture is running and is removed immediately after capture finishes.
- Existing option, option-price, additional-option dedup and network/state collection logic remains unchanged.
