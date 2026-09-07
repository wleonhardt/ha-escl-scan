# Next up

## Queue
- HACS store icon: shows once hacs/frontend#937 (brands-proxy support) ships;
  nothing to do on our side.
- Live-test still open: ADF batch *with live progress* (v0.4.3 fallback; needs
  paper in the feeder) and the zeroconf discovery flow (needs the entry
  removed; single_config_entry aborts otherwise).

## Backlog / nice-to-have
- Image-mode (JPEG) scans converted to PDF (needs Pillow/img2pdf).
- Reconfigure flow for host/creds (options flow currently edits them).
- Card: localisation of status strings.
- Community forum thread + device compatibility reports.

## Done
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
