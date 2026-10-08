# 2026-10-08 — Automatic duplex with manual fallback

User requested automatic detection with a manual two-pass fallback. This
supersedes the silent simplex downgrade in the 2026-09-06 capabilities decision.

- Two-sided requests on Feeder use automatic duplex only when capabilities
  advertise it. Unsupported or unavailable capabilities select manual duplex.
  Platen requests remain one-sided.
- Preserve `duplex` as the hardware-request flag; expose `duplex_mode`,
  `scan_phase`, and `front_pages` for the logical two-sided workflow.
- One tracked scan and driver own both jobs. After validating fronts and the
  device's final state, release the first job and await explicit user readiness.
  Reserve the integration while waiting; allow cancellation and shutdown.
- Reload the backs first sheet first (default), or select last sheet first
  when flipping the whole stack reverses its order. The resume service/API
  accepts `reverse_back_order`; require equal counts and reverse only the back
  pass when selected, then interleave F1,B1,F2,B2. No page-order inference or
  OCR is implied. This explicit choice was requested after the first live test.
- Resume only an awaiting scan with an idle scanner and paper loaded. Reject
  duplicate/stale resume requests. Waiting expires after 15 minutes.
- Store fronts privately; no completed event, download, or folder copy until
  both passes succeed. Executor operations and cancellation retain the existing
  lifecycle guarantees. Clear every intermediate file on all exit paths.
- Add an authenticated resume endpoint/service and a Two-sided card control.
  Automatic scanner failures stay explicit failures; never retry a consumed
  duplex batch as manual without the user's loading interaction.
- Printed test fixture: three Letter sheets/six sides, long-edge binding,
  IDs 1F/1B/2F/2B/3F/3B. HP M283fdw requires the manual workflow.

## Validation

- 158 Python tests, 24 card tests, Ruff and diff checks pass. Coverage includes
  bundled PDFs, exact interleaving, rotation, mismatched counts, private fronts,
  cancel/timeout/shutdown while waiting, cancel/shutdown during the second POST,
  concurrent resume/cancel, loaded/idle feeder checks, HTTP/service behavior,
  stale resumes, and card response/state races. Both back orders are checked
  with rotation and unknown capabilities; the card retains order after a
  resume error and resets it for the next scan. Resume API types are strict.
- Printed fixture with CUPS job 127: completed, six impressions on three
  physical Letter sheets, color, long-edge duplex, one copy, 100% scale.
- Installed v0.5.0 on HA 2026.9.4 after configuration validation and restart;
  backup: `/config/.escl-live-test/escl-before-v050.tar`. Hosted validation
  run 37808495090 passed.
- Live HP M283fdw manual scan `5a61d11d6cb4`: fronts 12:29:22–12:30:10 EDT,
  explicit reload pause, backs 12:40:05–12:40:53. State/progress went
  pending → processing (1,2,3) → awaiting-back-sides → pending → processing
  (4,5,6) → completed. Partial download returned 409; only private `.fronts`
  existed before resume, with no folder copy. Final scratch file cleanup passed
  and scanner returned Idle.
- Six-page PDF, 3,833,053 bytes; storage, media copy, authenticated download,
  and local inspection copy SHA-256 all match:
  `f826644822c8757ecbf43b338703519b874f59f3b06d04077b732f8cc10738c3`.
  Actual card Open scan click opened six thumbnails with isolated opener.
- All six scanned sides are upright with visible corner marks, readable small
  text and color/line patches. Letter sheets occupy Legal-size pages because
  the HP's maximum ADF region is used. Light reverse-side show-through is
  visible on the printed paper.
- Reload fed backs 3B,2B,1B instead of the instructed 1B,2B,3B. Actual output
  is 1F,3B,2F,2B,3F,1B: interleaving preserves input order, but physical pairs
  do not match. A back-order choice would support flipping the whole stack;
  this prompted the explicit back-order choice verified below.
- Back-order update committed as 4cb0ff8; hosted validation 37811279681 passed.
  Repeated front attempt `7b593a90a58b` consumed an extra sheet 1; user confirmed
  the stack was mishandled. Canceled while awaiting backs; private scratch files
  disappeared and no final download or folder copy was published.
- Retry `67ceef6755a1` consumed fronts 1F,2F,3F followed by backs 3B,2B,1B in
  the same first device job (scanner itself reports six). Likely reloaded
  before the first job closed; canceled this attempt too. Card/README now
  explicitly tell users to wait for the reload prompt before flipping.
- Card-only installation plus entry reload exposed stale frontend module
  registration: both old/new content hashes remained in extra module URLs,
  and the old module could register the custom element first. Setup now keeps
  routes registered but removes old module URLs before adding the current URL.
  Regression test verifies changed hashes, restoring an earlier hash without
  duplicate routes, and preservation of unrelated card modules.

## Successful paired hardware verification

- Installed final code e8e1e5e on HA 2026.9.4; core configuration check/restart
  succeeded, installed source hashes match the checkout, and hosted validation
  run 37814129989 passed all jobs. Fresh dashboard loads only
  `/escl_scan/card-0752992e08b6.js` and displays the wait-before-flipping guidance.
- Scan `6b4941c5a349` at 300 dpi RGB: fronts 14:11:24–14:12:11 EDT, exactly
  1F,2F,3F upright; paused before the user flipped/reloaded the whole stack.
  Selected Last sheet first in the actual card control and resumed at 14:17:06.
  Backs completed at 14:17:44, with progress 4→5→6 and
  `reverse_back_order=true`. Sensor returned Idle at 14:17:52.
- Rendered and visually checked all six final pages: **1F,1B,2F,2B,3F,3B**,
  all upright with four corner marks, readable small text and color/line
  patches. No missing or duplicated side. Legal-size 612×1008 page boxes and
  paper show-through remain the known device/fixture limitations.
- Final PDF: 3,854,953 bytes. Storage, media copy, authenticated HTTP download
  (200), and local inspection file have identical SHA-256:
  `2c98f207b8e98c7e8f532b5fcda6a2733670fb3737a82fdda20868414af12a28`.
  Only the final PDF remains in scan storage; no scan scratch files remain.
  The actual Open scan link opened a PDF viewer with six thumbnails and
  `window.opener === null`.
- Fixture header/IDs retain v0.4.7 because sheets were printed before the new
  feature; the tested integration is v0.5.0. Automatic duplex selection is
  covered by automated tests; this simplex-only HP cannot verify an automatic
  duplex hardware pass.
