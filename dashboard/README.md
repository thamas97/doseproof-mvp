# Implementation responsibility

Thabani owns the evidence dashboard served by the read-only API service. Fetch actual saved data. Include empty, stale, PENDING and UNVERIFIED states. Do not embed fake PASS values or treatment command buttons.

`index.html`, `app.js` and `style.css` now query only the local evidence API.
The page shows saved A/B/plant observations, source freshness, the narrow saved
sensor/model finding, original receipts and validation errors. It polls every
two seconds with bounded requests, safely inserts source strings as text and
labels historical results separately from current source freshness. No chart,
approval assurance or equipment-fault verdict is simulated for presentation.
