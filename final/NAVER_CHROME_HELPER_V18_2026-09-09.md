# NAVER CHROME HELPER V18

- Chrome helper version 2.6.0.
- Fixes V17 trigger regression where helper heartbeat connected but capture never started (`worker_loaded` only).
- Removes openerTabId dependency.
- Adds `bridge.js` on the local B2B page. The B2B import button sends an explicit capture command to the extension; only then does the extension open and arm a Naver product tab.
- Ordinary Naver browsing stays idle: no automatic image movement, dropdown opening, review opening, or capture.
- Existing field extraction logic is preserved; this revision focuses on reliable explicit triggering.
