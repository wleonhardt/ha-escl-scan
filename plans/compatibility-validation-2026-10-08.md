# Compatibility rollout validation

Installed candidates: scan 0.8.1 / print 0.7.0. The live test installed scan 0.8.0
first, then fixed a scanner-side 409 explanation in 0.8.1. Release tags remain
pending physical acceptance. The implementation-only checks below preceded
installation; live evidence is recorded separately at the end.

## Automated checks

- Scan: 209 Python tests, 46 card tests; Ruff passes.
- Print: 206 Python tests, 35 card tests; Ruff and compileall pass.
- Both npm dependencies installed with npm ci; JSON/service definitions parse;
  diff whitespace checks clean. Hosted validation is checked on the pushed heads.
- Total: 496 tests. Fixtures distinguish a redacted live HP capability capture
  from synthetic devices. Tests include profile references/ranges/combinations,
  image conversion dimensions and manual-duplex order, conversion cancellation,
  origin/port restrictions, recovery exhaustion/deadlines, IPP collection bounds,
  read-only version negotiation, preflight rejection, queue identity and UI races.

## Read-only device and bridge probes

- HP M283fdw eSCL: both source profiles parse; color/gray at 300 DPI select native
  PDF with the extension. Simplex feeder remains independent of duplex printing.
- HP direct IPP: PDF settings query and Validate-Job for one copy/one-sided with
  default paper pass. Advertises PDF/JPEG (not PNG), 25 media keywords, four media
  sources, auto/auto-monochrome/monochrome/color and qualities 3/4.
- Found a live compatibility regression before delivery: requesting
  media-col-database returned Content-Length 938053 and stalled after 226902
  bytes within the read budget. Removed that expansion from routine reads.
  The smaller queries and preflight then passed. No response-bound increases.
- Local CUPS queue to HP: format-specific PDF settings parse, including typed
  collections; Validate-Job succeeds. This does not verify physical conversion
  output or remote HA network reachability to the local queue.
- HP tray preflight initially rejected media-size-name inside media-col (0x040b).
  The printer advertises media-size, not media-size-name. Encode PWG paper keywords
  as exact hundredths-of-millimeter dimensions in the nested collection. Both auto
  and tray-1 now pass PDF + Letter + monochrome + normal-quality preflight.
- No physical print or scan jobs were submitted by these probes.

## Browser verification

BrowserOS Neo isolated local fixture with simulated APIs: paired narrow/wide cards,
light/dark themes and native Options dialogs checked visually. Controls remain
inside the card/dialog width; Escape returns focus to Options. The modal avoids
expanding a fixed-height Sections tile. Native icons are supplied by HA in the real
host; this standalone fixture stubs the host surface. This is not phone hardware or
an installed-version check.

## Physical and external gates

1. Phase 2 two-copy and short-edge output confirmation remains outstanding.
   New job 368 closes the long-edge physical check on the current candidate.
2. Passed on the installed candidate: Letter scan, two-sheet manual duplex batch,
   selected-options print, output dimensions/order/orientation, Download PDF,
   filename clearing and no extra jobs on the tested rejection paths. See below.
3. Automatic-duplex ADF requires different hardware; this HP scans one side only.
4. Brother/Xerox/Ricoh quirks, image-only hardware, AirSane and ipp-usb require
   actual device/bridge runs before claiming physical support.
5. Native hosting/history remain in later shared-card phases. Native WSD, new
   authentication and embedded rendering have separate evidence-gated proposals.

Rollback when installation is undertaken: back up both deployed integrations and
Lovelace resources first; restore the prior pair and restart HA if setup fails.
Retain the existing card/entity IDs and document the actual installed hashes.

Hosted scan validation caught Pillow redeclaration: it is already a Home Assistant
core dependency and custom manifests must not list it. Removed the redundant
requirement and retained conversion tests; no extra dependency installation is needed.

The minimum supported HA 2024.12 already declares Pillow 11.0.0 in its
[core dependencies](https://github.com/home-assistant/core/blob/2024.12.0/pyproject.toml).
Browser mobile emulation at 390 px verified both 165 px cards without horizontal
overflow; the options dialog measured 352 px and also had no horizontal overflow.
Final outage regressions preserve explicit print settings and permit resetting
selected scan/print fields to defaults while capabilities are unavailable.

## Delivery

- Scan implementation head `a0f2e46`: [all six checks passed](https://github.com/wleonhardt/ha-escl-scan/actions/runs/37868285339).
- Print implementation head `74878df`: [all six checks passed](https://github.com/wleonhardt/ha-ipp-print/actions/runs/37868134913).
- Both main branches pushed. Local checks total 496 passing tests. Documentation
  follow-ups do not alter these implementation trees. Print worktree clean; the
  pre-existing, untracked scan `output/` directory was left untouched.
- At the implementation handoff, no tags, HA restart or installation had been
  performed. The subsequent installation and tests are recorded below.

## Live acceptance — 2026-10-08

- Both job sensors idle before deployment. Backed up both integrations and
  Lovelace storage to
  `/config/.document-card-backups/before-compat-v080-v070-20261008.tar.gz`.
  HA 2026.9.4 configuration check and restart succeeded; all 39 deployed files
  matched the repository hashes. Both integration entries loaded.
- Exactly one resource per card: `/escl_scan/card-2716a5a11730.js` and
  `/ipp_print/card-8cdfc3b1fa87.js`. Both real dashboard cards and Options dialogs
  work at desktop and 390 px emulated phone width. User subsequently confirmed
  that both Options dialogs fit and work on the physical phone.
- Fresh authenticated capability reads passed for both integrations. HP reports
  PDF/JPEG printing, Letter ready, automatic duplex printing and manual duplex
  scanning. Source selection updates scan DPI choices to the feeder's range.
- Real card print job 368: PDF, copies=1, long-edge duplex, Letter, tray=auto,
  monochrome, normal quality. HP briefly reported printer-stopped; user confirmed
  the printer requested paper-size verification. After confirmation, job completed
  with 2/2 impressions and no warning. User confirmed one double-sided sheet,
  front/back upright when turned like a book. Card filename cleared and Choose
  file returned. No duplicate submission.
- First explicit feeder scan was rejected with device HTTP 409. Read-only status
  reported Idle/ScannerAdfEmpty; user reseated the sheet and status then reported
  ScannerAdfLoaded. This exposed raw device errors in terminal scan results.
  Scan 0.8.1 adds one bounded status read after 409, giving empty-feeder, busy,
  or unknown-state guidance without retrying or deleting jobs. Six regressions
  pass, including missing status, status timeout and glass-source conflicts.
  Updated scan checks: 215 Python/46 card, Ruff; pair total 502 tests.
  Installed the fix and restarted; deployed scanner hash matches the repository.
- Separate dashboard issue: its Printer offline conditional tests the offline
  binary sensor for `off`, and its summary uses an unavailable legacy HP status
  entity. Native IPP status is idle and direct requests succeed. Recorded without
  modifying unrelated dashboard configuration.
- Single-page scan `57095322b5d4`: explicit feeder/Letter/grayscale/300 DPI passed.
  Download PDF remained through the idle reset; clicking it saved 462382 bytes
  and restored Scan. Inspected PDF: one upright page, 612 x 792 pt, one grayscale
  2550 x 3300 image (300 DPI). Download, private storage and configured folder
  copy SHA-256 all match:
  `1c4366ad94d1a30d43b84a6262e675dd1c786955ff9ac50c753964968ea071d9`.
  Scan fix hosted validation passed on `f82b0d5`, run 37871132059.
- Color duplex print job 369: one copy, Letter, automatic tray, normal quality,
  long-edge; completed with 4/4 impressions. Created and visually checked two
  numbered sheets (1F/1B and 2F/2B), then used those physical sheets for scanning.
- Manual duplex scan `f1014e2196bf`: Letter/color/300 DPI. Fronts 1F then 2F,
  backs 2B then 1B with Last sheet first selected. Two fronts triggered the
  reload prompt; four pages completed without changing settings. PDF inspection
  confirms 1F,1B,2F,2B, all upright, each 612 x 792 pt with an RGB 2550 x 3300
  image. Download PDF restored Scan. Download/storage/folder-copy SHA-256 match:
  `7dddaa161f5765002fc9d2fdd1cb65207b50db06a5dbc17e301b27ca62dd4dee`
  (2173010 bytes). Paper show-through is visible in the scanned images.
- While waiting for backs, a second start returned 409 with actionable resume/
  cancel guidance and the same scan stayed active. The unfinished PDF endpoint
  returned 409. No new job and no intermediate document disclosure.
- Final installed-version regression: confirmed Idle/ScannerAdfEmpty, submitted
  one deliberate empty-feeder start and observed the card message, "The feeder
  is empty. Load the pages until the scanner detects them, then try again."
  No document created. Both job sensors returned to idle. The fix is committed
  and pushed, with all six hosted checks green. No release tags created.
