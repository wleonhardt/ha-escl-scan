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

- 157 Python tests, 24 card tests, Ruff and diff checks pass. Coverage includes
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
  paired hardware verification and release tag remain pending.
