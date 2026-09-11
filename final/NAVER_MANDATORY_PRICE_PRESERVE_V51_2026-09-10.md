# NAVER mandatory option price preserve V51

- Root cause fixed: a dependent mandatory-option timeout no longer discards main option labels and +/- prices already collected.
- Main, dependent and additional option phases now fail independently and preserve every completed phase.
- Partial dependent variants are retained when the time budget is reached.
- Repairs an invalid add-on group name (such as the product title) by matching its values to the meaningful passive group name (such as `도래류`).
- Adds a UI safeguard that never displays the product title as an add-on group name.
- Keeps V50's isolated internal option-price reader and all existing core sourcing behavior.
- Extension and heartbeat version: 2.38.0.
