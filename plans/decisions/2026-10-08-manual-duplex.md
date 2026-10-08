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
- Reload the backs in the same sheet order as the fronts. Require equal counts,
  then interleave F1,B1,F2,B2. No page-order inference or OCR is implied.
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

- 153 Python tests, 24 card tests, Ruff and diff checks pass. Coverage includes
  bundled PDFs, exact interleaving, rotation, mismatched counts, private fronts,
  cancel/timeout/shutdown while waiting, cancel/shutdown during the second POST,
  concurrent resume/cancel, loaded/idle feeder checks, HTTP/service behavior,
  stale resumes, and card response/state races.
- Printed fixture with CUPS job 127: completed, six impressions on three
  physical Letter sheets, color, long-edge duplex, one copy, 100% scale.
- Runtime backup/release and manual hardware test pending.
