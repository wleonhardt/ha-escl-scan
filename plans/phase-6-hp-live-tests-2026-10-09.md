# Phase 6 HP retention live test — 2026-10-09

Status: passed, including physical phone acceptance. Installed pair:
scan 0.12.0 / print 0.11.0, HA 2026.9.4. No code changes were needed.

## Print baseline

The user confirmed Letter paper ready. Generated and visually checked a
single-page Letter PDF, `phase6-hp-retention-test.pdf` (2310 bytes), recognition
code `HP-P6-20261009`. Staged that file in the real native Print workflow and
submitted once: one copy, one-sided, automatic tray/default color and quality.

HP job **373**: submitted `2026-10-09T19:04:23.298639+00:00`, completed
`2026-10-09T19:04:35.898258+00:00`, reported one impression and
`job-completed-successfully`. Activity expiry is
`2026-10-16T19:04:23.298639+00:00`. The filename cleared and the card returned
to Choose file. Sensor returned to idle.

After a full dashboard reload, Recent activity showed the same completed record.
Compared every metadata field (ignoring object key order): ID, filename,
submission/finish/expiry, state, count and unit all unchanged. The private Store
exists with mode 0600 under `.storage/ipp_print.activity.<entry_id>`.

Scan Options prepared through the real controls: Feeder, Letter, 300 DPI,
integration-default color, Two-sided off. Back closed Options. The user confirmed
the labeled print was correct and the feeder detected it before scan submission.

## Scan and refresh

Submitted scan **8812dcdc7880** once through the real native Scan button at
`2026-10-09T19:08:28.946504+00:00`. The HP completed one color page at 300 DPI
at `2026-10-09T19:08:46.923129+00:00`. Letter PDF: 612 x 792 pt, **540,520 bytes**.
Rendered and visually inspected: upright, legible, recognition code
`HP-P6-20261009`, all page edges present.

Latest record filename: `scan-20261009-150829-feeder-8812dcdc7880.pdf`.
Expiry: **2026-10-09T20:08:46.320755+00:00** (4:08 PM local). The earlier file
mtime deadline correctly wins over completion time; restart did not extend it.
SHA-256 before refresh and restart:
`26f4d5cf31f802c94c5808e18de42eba9e2cefac8db4028854d0771f0c8c0313`.

The authenticated HTTP download, private retained PDF and configured `/media`
copy all have that hash. Anonymous HTTP returned 401. Metadata Store mode is
0600. The main Download PDF action saved the file and returned to Scan; Latest
scan retained its independent download action.

After a full reload, both job sensors remained idle. Compared every latest-scan
and print-activity field with the baseline: identical. Authenticated PDF still
returned 200 with the same bytes/hash; Latest scan Download was enabled and the
main actions remained Scan / Choose file. Both expanded sections were visible
at 390px without horizontal overflow.

## Home Assistant restart

Confirmed both jobs idle immediately before the explicitly requested full HA
restart. Restart completed successfully. After a fresh dashboard load, captured
at `2026-10-09T19:12:05.228Z`:

- The exact same scan and print metadata returned, including original finish
  timestamps and expiry deadlines. Print activity still contained exactly one job.
- Authenticated PDF returned 200, 540,520 bytes and the identical SHA-256.
  Anonymous access still returned 401 (the expected HTTP auth warning was logged).
- Both job sensors remained idle with null active IDs and reachable connections.
  No jobs were replayed or reconstructed as active work.
- Clicked Download PDF within the restored Latest scan section. The browser
  saved a second copy; its bytes/hash match the first actual browser download.
  Feedback said the PDF was handed to the browser, the main action stayed Scan,
  and the retained download remained available.

Browser downloads reside at:
`/Users/william/Downloads/scan-20261009-150829-feeder-8812dcdc7880.pdf`
and the same basename with ` (1)` before `.pdf`. The browser download helper's
initial ref click timed out without invoking the primary button; a DOM click
on the actual button succeeded. No retry submitted a scan or print.

The user refreshed on their physical phone after restart and confirmed:
**both records appear and Download PDF works**. Phase 6 HP physical acceptance
is closed. No additional print or scan is needed for this retention check.

Local verification rerun during the print: scan 240 Python / 77 card tests;
print 229 Python / 64 card tests. Both npm ci, Ruff and print compileall pass.
No code changes were needed for the completed checks.
