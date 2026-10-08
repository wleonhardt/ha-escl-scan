# Next up

## Queue
- HACS store icon: shows once hacs/frontend#937 (brands-proxy support) ships;
  nothing to do on our side.
- Live-test still open: zeroconf discovery flow only (needs the entry removed;
  single_config_entry aborts otherwise).

- Awaiting reporter feedback on #5 (v0.4.4/v0.4.5 on Epson ET-4950 / WF-4830).

## Backlog / nice-to-have
- Image-mode (JPEG) scans converted to PDF (needs Pillow/img2pdf).
- Reconfigure flow for host/creds (options flow currently edits them).
- Per-scan override for rotate_duplex_backs (service field / card toggle).
- Card: localisation of status strings.
- Card: keep the most recent completed scan accessible beyond the 30-second
  result latch, or add a scan history/download control.
- Paper size/scan-region selection: HP's maximum ADF region produces Legal-size
  PDFs with extra white space when scanning Letter sheets.
- Community forum thread + device compatibility reports.

## Done
- 2026-10-08 — v0.5.2: restore dashboard resource registration alongside extra
  module loading after a phone continued to show Configuration error despite
  clearing cache. A fresh desktop/mobile-width browser loads correctly;
  physical phone confirmation is pending. The print card had a dashboard
  resource while the scan card did not. Sync loads storage first, updates one
  resource in place, removes stale duplicates, serializes reloads, and selects
  the latest loaded entry after waiting. YAML/error paths keep extra modules.
  Validation: 166 Python tests, 30 card tests, and ruff pass; real HA resource
  collection preserves its ID and updates its URL on integration reload.
- 2026-10-08 — v0.5.1 card polish: larger Scan Duplex control (48px minimum
  height) and actionable conflict guidance for running scans, waiting backs,
  finishing scans, empty/busy feeders, and missing/older 409 response bodies.
  No scan lifecycle changes; existing busy guards remain enforced. Validation:
  161 Python tests, 30 card tests, and ruff pass.
- 2026-10-08 — Automatic duplex detection plus a manual two-pass fallback
  implemented for v0.5.0. Card controls, resume API/service, private front-side
  storage, matched-count interleaving, cancellation/shutdown, and reload
  timeout covered by 158 Python tests and 24 card tests. Three double-sided
  test sheets printed (six labeled sides). Live HP manual scan verified
  1F,1B,2F,2B,3F,3B, all upright, using Last sheet first for a flipped stack.
  Progress 1→2→3→reload pause→4→5→6; storage/copy/download hashes match and
  isolated six-page preview opens. Added wait-before-flipping guidance and
  fixed stale card module registration on integration reload. Local and
  hosted checks green; automatic duplex hardware testing needs another scanner.
  See `decisions/2026-10-08-manual-duplex.md`.
- 2026-10-08 — Full code review: lifecycle/cancellation, PDF integrity,
  retention races, URL/auth bounds, diagnostics, and card fixes released as
  v0.4.6. Live HP test caught explicit-default-port origin equality; fixed and
  released v0.4.7. HA 2026.9.4 dashboard retry: 3-page color ADF at 300 dpi,
  progress 1→2→3, busy guard 409, folder copy/download hashes match, PDF preview
  opens with isolated opener. Local and hosted checks green. See
  `code-review-2026-10-08.md` for results and remaining physical/UX limits.
- 2026-10-08 — #5: v0.4.4 duplex region from AdfDuplexInputCaps; v0.4.5 rotate-back-sides
  option + 900 s download stall/retry budget (fixed, not configurable).
- 2026-09-12 — ADF live test on v0.4.3: progress 1→2→3 with `JobScanning`,
  completed 3 pages = PDF pages, copy-to-folder OK. Live progress on HP confirmed.
- 2026-09-07 — ADF live test: 3 sheets → one bundle PDF, 3 pages, copied. Found:
  HP 404s GET ScanJobs/{uuid}; JobInfo only in ScannerStatus/Jobs (no progress
  before v0.4.3). Fixed + page double-count fixed. Card verified by William in
  the dashboard. Released v0.4.3.
- 2026-09-07 — live test on HA 2026.9.1 + HP Color LaserJet MFP M283fdw
  (10.11.30.190, http/80): capabilities (serial VNBKN7J35T, platen 2550x3508,
  ADF 2550x4200 simplex, DPI 75–1200), DPI snap 275→300 / 250→200, service
  start/cancel, button, busy guard (clean over WS; HA REST maps
  ServiceValidationError to 500 — core behaviour), copy-to-folder to
  /media/escl_scan, file view 404/200. Found + fixed: post-cancel "scanner
  busy" (wait-for-idle), HP lowercase `uuid` TXT key. Released v0.4.2.
- 2026-09-06 — v0.4.1: min HA 2024.12 (plain `OptionsFlow.config_entry` only
  exists from 2024.12; 2024.8–2024.11 crashed the options flow),
  `hide_default_branch`, SECLEVEL=1, card `node --check` in CI. Cross-checked
  against the ha-ipp-print review; card already diffs pushed `hass` (no
  admin-only `subscribe_trigger`), README/brand/changelog/release flow done.
- 2026-09-06 — v0.4.0 work: capabilities (bed size, duplex, DPI snap, device
  info, serial unique_id), zeroconf, services + button, copy-to-folder,
  diagnostics, card editor, purge scoping, NextDocument retry, view tests.
  See `plans/decisions/2026-09-06-capabilities-and-brands.md`.
- 2026-09-06 — v0.3.0 finally pushed + released (was 7 commits unpushed);
  CHANGELOG, release workflow, issue templates, dependabot.
- 2026-07-20 — stability review + phased fixes (P1–P4) landed, v0.2.0. See `stability-review-2026-07-20.md`.
- 2026-07-20 — test suite (37 tests) + ruff wired into CI.
