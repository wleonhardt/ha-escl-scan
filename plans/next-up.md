# Next up

## Queue
- Active: Phase 5 native Tile and optional Mushroom features, scan 0.11.0 /
  print 0.10.0. Minimum/current host runtime checks and 572 tests pass; installed.
  Both releases and all hosted checks pass. Physical Android acceptance remains. Standalone cards stay supported.
  [Phase 5 validation](shared-card-phase-5-validation.md).
  [Canonical phased plan](shared-card-rollout-2026-10-08.md).
- External coverage remains separate: automatic duplex scanning, additional
  vendor/bridge hardware and assistive-technology device acceptance.
  Minimum-HA native feature hosting passed in Phase 5.
  [Compatibility validation](compatibility-validation-2026-10-08.md).
- HACS store icon: shows once hacs/frontend#937 (brands-proxy support) ships;
  nothing to do on our side.
- Live-test still open: zeroconf discovery flow only (needs the entry removed;
  single_config_entry aborts otherwise).

- Awaiting reporter feedback on #5 (v0.4.4/v0.4.5 on Epson ET-4950 / WF-4830).

## Backlog / nice-to-have
- Reconfigure flow for host/creds (options flow currently edits them).
- Per-scan override for rotate_duplex_backs (service field / card toggle).
- Add reviewed card languages using the English catalog and documented workflow.
- Card: persistent scan history/download access across dashboard reloads.
  The mounted card now retains its latest result until download or a newer scan.
- Community forum thread + device compatibility reports.

## Done
- 2026-10-09 — HP Phase 4 physical acceptance passed: print job 371, manual
  duplex scan `a49d87b88844`, reload and real browser reconnect during the back
  pause, four-page PDF order/orientation/hash checks, and real HP shutdown plus
  automatic recovery. Warnings clear, polling returns to 60 seconds and both jobs
  remain idle without replay. Print 0.9.1 fixes provisional progress totals found
  in the real job; final pair is scan 0.10.0 / print 0.9.1, with 560 tests passing.
  [Live-test record](phase-4-hp-live-tests-2026-10-09.md).
- 2026-10-09 — Phase 4 released and installed as scan 0.10.0 / print 0.9.0.
  Pushed job recovery, scoped delayed replies, honest counters/outcomes, native
  protocol connection sensors and vendored presentation core v2. Dashboard uses
  the new native connection tiles. 559 tests, all hosted checks and both release
  workflows pass. Read-only HP status plus isolated 320/390px two-tab recovery
  checks pass; no physical job submitted. [Validation](shared-card-phase-4-validation.md).
- 2026-10-08 — Phase 3 completed, released and installed as scan 0.9.0 /
  print 0.8.0: shared English localization, readable editors, correct defaults,
  cleared optional overrides and keyboard/accessibility polish. 527 tests pass;
  native editors and narrow/long-label dialogs verified in HA 2026.9.4.
  Both release workflows and all six hosted checks passed.
  [Validation](shared-card-phase-3-validation.md).
- 2026-10-08 — Remaining HP print acceptance passed on print 0.7.2 / scan 0.8.2.
  User confirmed two copies and short-edge duplex orientation from job 370;
  the printer reported 4/4 impressions and the filename cleared. Physical
  release gates for the available HP are closed. Final Phase 3 editor/string
  audit and release tags remain; external scanner/bridge checks stay separate.
- 2026-10-08 — Paired mobile Back fix installed as scan 0.8.2 / print 0.7.2.
  Options now participates in HA dialog navigation; cached cards cannot reopen
  settings inline after leaving the view. 512 paired tests pass. Live browser
  Back/Forward/Done verified; user confirmed the Back fix on the physical phone.
  [Validation](compatibility-validation-2026-10-08.md).
- 2026-10-08 — Card feedback fixes installed as scan v0.7.1 / print v0.6.1.
  Fresh capability labels, retained Download PDF primary action and finished
  print filename cleanup. All 433 tests pass; live HP capability wording,
  isolated browser download and narrow paired layouts verified. User confirmed
  Download PDF works on the phone and the action returns to Scan. Earlier
  physical print matrix confirmation remains pending.
  [Details](shared-card-phase-2-validation.md).
- 2026-10-08 — First paired UI release: scan v0.6.0 / print v0.5.0. Compact
  Two-sided switch, explicit staged printing, common theme styling and Sections
  sizing. Live reload found and fixed recovery leaving HA's owned element as an
  error card, which could reappear beside the working card. Both cards now use
  the wrapper's load path. Live desktop and physical phone load correctly.
  Scan 166 Python / 36 card tests; print 135 Python / 29 card tests; hosted
  validation and release workflows pass. [Details](shared-card-phase-1-validation.md).
- 2026-10-08 — v0.5.2: restore dashboard resource registration alongside extra
  module loading after a phone continued to show Configuration error despite
  clearing cache. A fresh desktop/mobile-width browser loads correctly;
  physical phone confirmation was pending until v0.6.0. The print card had a dashboard
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
