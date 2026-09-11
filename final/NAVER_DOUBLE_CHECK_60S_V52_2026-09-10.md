# NAVER mandatory option double-check and 60-second budget V52

- Mandatory option controls are always opened twice, restoring the user-observed verification behavior.
- When pass 1 has only names and pass 2 has +/- prices, the priced values replace the name-only duplicates.
- A failed second pass preserves the first pass instead of deleting it.
- Raises the option-work hard limit from 22 seconds to 60 seconds for products with many values.
- Raises the B2B result wait window to 75 seconds so a valid 60-second capture is not abandoned early.
- Keeps V51 timeout preservation, add-on prices, add-on group-name repair and all existing safety guards.
- Extension and heartbeat version: 2.39.0.
