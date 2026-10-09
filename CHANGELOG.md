# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/); versions follow SemVer and
match `custom_components/escl_scan/manifest.json`.

## [0.12.0] - 2026-10-09

### Added
- Standalone Sections cards default to automatic rows for expanding activity.
- Add a collapsed **Latest scan** section with authenticated PDF download after
  dashboard reloads and Home Assistant restarts. The primary completion action
  still returns to Scan after download.
- Persist only the latest successful result metadata, respecting the existing
  PDF retention deadline. Missing and expired files show guidance; incomplete
  duplex fronts, failed jobs and canceled scans are never published.
- Reconcile files on startup, purge and download; reject symlinks and keep
  downloads available while the scanner is offline. No document archive is added.

## [0.11.2] - 2026-10-09

### Fixed
- Align the Scan/Print headings, Two-sided switches, helper text and actions
  in paired native cards. Put the scanner's feeder hint below the switch row,
  reserve the same two-line status space, and collapse empty warning rows.
  Long content can still expand without fixed card heights or host CSS overrides.

### Documentation
- Device naming guidance: use a friendly heading for a paired device, or name
  each separate card. Document the current single-scanner limit explicitly.

## [0.11.1] - 2026-10-09

### Fixed
- Intermittent native Tile/Mushroom “Configuration error” on a fresh dashboard
  load when a late scoped custom-element polyfill replaces the browser registry.
  Restore missing registrations for the card, feature, editors and Options
  dialog while preserving existing constructors, selected settings and files.
  Recovery uses load/navigation events without continuous polling or DOM scans.

## [0.11.0] - 2026-10-09

### Added
- Optional `custom:escl-scan-feature` for native Tile and current Mushroom Template
  cards. The host owns the title/surface; the feature reuses the existing workflow,
  visible Two-sided switch, Options dialog, progress and recovery behavior.
- Native feature picker, visual defaults editor and paired examples. Modern host
  context and legacy entity delivery are supported; unrelated/area-only hosts
  and inline placement show configuration guidance without device actions.

### Changed
- Shared presentation core v3 includes the native host adapter without additional
  assets or dependencies. Existing standalone card configurations remain supported.
- A feature follows only its parent's job sensor. Changing that sensor discards
  staged files and detaches old replies; control gestures do not trigger host actions.

## [0.10.0] - 2026-10-09

### Added
- A native Connection binary sensor per device, independent of job state, with
  last-check/last-success timestamps. Read-only protocol checks run once a minute,
  back off to five minutes after failures, and stop cleanly on unload.
- Shared, versioned presentation core for both document cards: localization,
  Options dialogs, base styles and expandable error guidance. CI detects drift;
  each integration still ships one complete card asset without a build step.

### Changed
- Cards explain stale/failed device checks separately from job outcomes and
  disable device actions while disconnected from Home Assistant.

### Fixed
- Scope start, cancel, manual-back and download replies to the selected scanner
  and request generation. Delayed replies cannot overwrite a newer scan or
  survive navigation; active scans keep their original target.
- Explicit scan-sensor routing validates the integration before device I/O;
  existing API clients may continue omitting the single scanner target.
- Reject non-protocol and oversized ScannerStatus responses before reporting
  reachability, while retaining namespace-tolerant eSCL parsing.

## [Unreleased]

## [0.9.0] - 2026-10-08

### Added
- Translation-ready English catalog for the card and visual editor, with Home
  Assistant language selection, regional/base/English fallback, placeholders
  and plural forms. No extra download, build step or dependency. Additional
  languages will be added after review.

### Changed
- Readable editor choices and help explain automatic source, Glass, Grayscale,
  integration-default resolution and full scan area without changing API values.
- Name the Options button by task, focus the dialog heading without opening the
  phone keyboard, and associate settings guidance with controls. Avoid repeated
  announcements of unchanged status; preserve focused inputs on updates.

### Fixed
- Editor defaults now match actual card behavior without changing saved config
  on open. Clearing optional resolution removes its override instead of saving
  an invalid value.

### Included since the previous HACS release (0.6.0)
- Capability-aware source/color/resolution/paper Options; automatic/manual duplex
  wording; retained Download PDF action; clearer busy/empty-feeder errors and
  mobile Back navigation. Existing card types and YAML remain supported.
- Complete eSCL profile matching, bounded JPEG/PNG-to-PDF acquisition, custom
  scan regions, bridge resource paths, discovery reconciliation, safe diagnostics
  and scoped vendor recovery. See 0.7.x/0.8.x entries below for details.
- HP M283fdw live checks cover Letter color/grayscale scans, downloaded PDF
  integrity and two-sheet manual duplex ordering/orientation. Automatic duplex
  scanning and other scanner/bridge hardware remain outside this physical test.

## [0.8.2] - 2026-10-08

### Fixed
- Close Options through Home Assistant's dialog navigation so Back dismisses
  settings before leaving the dashboard. Reset the native dialog when the card
  is removed, preventing an inline settings panel after returning to the page.
- Keep native dismissals, Done and Escape synchronized with the Options button
  and preserve selected settings when the same card reconnects.

## [0.8.1] - 2026-10-08

### Fixed
- Explain scanner-side start conflicts using a bounded status read: tell users
  to load an empty feeder or check a busy device instead of displaying raw 409.
  Unknown status keeps general guidance; no automatic retry or job deletion.

## [0.8.0] - 2026-10-08

### Added
- Match source, color, transfer format and resolution within complete eSCL profiles,
  including bounded named references and intersecting square resolution ranges.
- Prefer native PDF; convert advertised JPEG/PNG scans to PDF in executor work
  with 50 MiB encoded/40 MP decoded limits, physical dimensions and cancellation cleanup.
- Select full area, Letter, A4 or custom regions with advertised bounds and feeder alignment.
- Shared Options dialog for source, color, resolution and paper size; optional
  Two-sided placement inside Options, stable focus and settings frozen during a job.
- Advanced scanner resource path for software bridges; discovery UUID aliases
  preserve serial-based IDs across address changes. One scanner remains supported.

### Fixed
- Add scoped Brother feeder delays, Xerox B205/B215 404/410 recovery and Ricoh
  status-before-load handling with bounded retries. Other devices retain their behavior.
- Redact filenames, URLs, connection paths and device identities in diagnostics.
- Keep incomplete capability summaries unknown and allow selected options to reset
  to defaults during capability outages.
- Preserve selected profile/format/region across manual duplex passes. Reject
  known incompatible settings and oversized images before consuming paper when possible.

## [0.7.1] - 2026-10-08

### Changed
- Use fresh scanner capabilities to label two-sided scans as Automatic duplex
  or Two passes required; unknown/older backends retain cautious wording.
- Make Download PDF the primary action after completion, retaining it across
  the server's idle reset until the PDF is handed to the browser. Failed
  downloads remain retryable; expired files offer Scan again. Results remain
  local to the mounted card and a newer scan replaces the previous result.

## [0.7.0] - 2026-10-08

### Added
- Authenticated, entity-scoped capability API available without an active scan:
  bounded identity, per-source and duplex resolutions/colors, automatic/manual
  duplex support, request fields and integration limits.
- Shared cache policy: 15-minute lifetime, five-minute failure backoff, serialized
  reads, bounded fetch time and explicit fresh/stale/unknown metadata.

### Fixed
- Validate known unsupported source/color choices before creating a job, while
  preserving permissive behavior when vendors omit capability fields.
- Do not borrow another source's DPI list when automatic-duplex modes are unknown.
- Freeze scan region across manual front/back passes, including capability refresh.
- Limit scanner capability responses to 1 MiB before XML parsing.

## [0.6.0] - 2026-10-08

### Changed
- Replace Scan Duplex with a compact, labelled Two-sided switch and one Scan
  action. Changing the switch never starts a scan; job controls lock while active.
- Match the sister print card with neutral theme surfaces, native icons, readable
  text, real buttons, keyboard focus and matching Sections sizing. Long conflict
  messages expand from a summary to recovery guidance.
- Default title is Scan. Existing explicit titles and card types remain valid.

### Added
- Boolean `duplex` card default and visual editor field (default false). The
  switch explicitly overrides the integration duplex default; enabled scans use
  the feeder with the existing automatic/manual fallback.
- Shared card contract, paired fixtures and direct Sections dashboard example.

### Fixed
- Recover slow-loading cards through Home Assistant's card wrapper so later
  state updates cannot reinsert a stale Configuration error beside the card.
- Editing a title/default no longer resets active scan controls before a sensor
  update arrives. Apply a changed duplex default after the current scan finishes.
- Show unavailable scan state instead of an idle source hint.

## [0.5.2] - 2026-10-08

### Fixed
- Register the scan card as a dashboard resource as well as an extra module,
  so mobile clients can load it when their app shell stays open across updates.
- Update the resource in place, remove stale duplicates, and serialize reloads.
  YAML dashboards and resource failures retain extra module loading.

## [0.5.1] - 2026-10-08

### Changed
- Larger, more prominent **Scan Duplex** button, with a 48px minimum height.
- Scan conflicts now explain whether another scan is running, backs need to
  be scanned, or the previous scan is finishing, and tell users what to do.
  Busy and empty feeders get separate back-side resume messages. Missing or
  older 409 response bodies also show friendly guidance instead of HTTP codes.

## [0.5.0] - 2026-10-08

### Fixed
- Integration reloads load only the current card module, preventing a cached
  older module from registering first and hiding updated controls.

### Added
- Two-sided feeder scans detect automatic duplex support. Simplex scanners
  and scanners with unavailable capabilities use a manual two-pass workflow:
  scan fronts, reload backs, then scan backs. The reload step accepts first
  sheet first or last sheet first (flipped stack). The final
  PDF interleaves front/back pages and requires equal counts.
- Card controls for **Scan both sides** and **Scan back sides**, plus reload
  instructions, back-order selection, and progress across both passes. Front
  pass messages remind users to wait for the reload prompt before flipping.
- `escl_scan.scan_backs` service and authenticated `/api/escl_scan/scan_backs`
  endpoint; `awaiting-back-sides` state, `duplex_mode`, `scan_phase`, and
  `front_pages`, and `reverse_back_order` attributes. The resume service/API
  accepts optional boolean `reverse_back_order` (default false).
- Fronts remain private until both passes succeed. Waiting can be canceled
  and expires after 15 minutes; cancellation/shutdown clean up both jobs and
  intermediate files. Folder copies and completed downloads are published
  only after the final combined PDF succeeds.

## [0.4.7] - 2026-10-08

### Fixed
- Accept scanner job addresses and redirects with an explicit default port
  (`:80` for HTTP or `:443` for HTTPS). HP scanners return these addresses;
  v0.4.6 incorrectly rejected them. Other hosts, protocols, ports, and URLs
  containing credentials remain blocked.

## [0.4.6] - 2026-10-08

### Fixed
- Cancellation cannot revive a pending job or leave a stalled document driver
  running. New scans wait for previous job/file cleanup; shutdown also waits
  for source detection and retention workers and deletes its own device job.
- Home Assistant stop and failed setup also close the client and clean up jobs.
- Executor writes finish before canceled tasks clean up their files. Interrupted
  scans close scratch files and remove unfinished output.
- Truncated, corrupt, empty, or interrupted document batches fail explicitly
  instead of reporting a partial PDF as a completed scan. Exhausted document
  retries are errors rather than end-of-batch signals.
- Failed/aborted scans are not copied into watched folders. Cancellation is
  rejected once folder publication begins; failed copies remove scratch files.
- Scanner URLs preserve ports that differ from the selected protocol default
  and support IPv6. Job URLs must belong to the scanner's ScanJobs endpoint,
  and redirects cannot send credentials to another origin.
- DPI selection respects flatbed, simplex ADF, and duplex ADF resolutions.
  Polling surfaces pause/resume and interrupts device-canceled or aborted jobs.
- Whitespace-only XML reason wrappers, escaped/duplicate job URIs, and the
  vendor spelling `Cancelled` are parsed correctly.
- Diagnostic exports redact capability identifiers, filesystem paths, and
  exception text, in addition to connection credentials.
- Scan-start HTTP requests reject malformed JSON and boolean/out-of-range DPI;
  download path checks run outside the event loop.
- Card HTTP responses cannot overwrite newer terminal sensor states. Repeated
  start/cancel taps are guarded; attribute/entity changes refresh the display.
  Healed cards receive HA state immediately.
- Open scan reserves its preview tab during the click gesture, isolates its
  opener, and limits authenticated downloads to the integration's file endpoint.
- Duplex rotation preserves document metadata and reads file size off-loop.

### Changed
- PDF parsing uses file handles to avoid redundant whole-file memory copies;
  merge inputs close after each document is imported.
- Unavailable capabilities probes back off for five minutes, then retry.
- Card tests close their browser fixtures, eliminating timer-related test delays.

## [0.4.5] - 2026-10-08

### Added
- Option *Rotate duplex back sides 180°* for ADFs that feed back sides
  reversed (#5).

### Changed
- Document download stall timeout and 503 retry budget raised to 900 s so
  large ADF batches on slow devices no longer fail with `no document
  returned from scanner` (#5).

## [0.4.4] - 2026-10-08

### Fixed
- Duplex Feeder scans used the simplex ADF size limit and failed with
  `409` on devices whose duplex limit is smaller (e.g. Epson ET-4950).
  Duplex jobs now use `AdfDuplexInputCaps` (#5).

## [0.4.3] - 2026-09-07

### Fixed
- HP MFPs answer 404 for `GET /eSCL/ScanJobs/{uuid}` and only report job
  state inside `ScannerStatus/Jobs`. JobInfo now falls back to that list, so
  these devices get live page progress, `state_reasons`
  (`JobCompletedSuccessfully`, …), the final Aborted check, and correct
  "job still alive" detection when NextDocument answers 503 between sheets.
- Page count no longer doubles when the device counter and the document pull
  both count the same page; the assembled PDF's page count is authoritative.
- 503 purge skips jobs the device already lists as finished (HP keeps them
  as history).

## [0.4.2] - 2026-09-07

Live-tested against an HP Color LaserJet MFP M283fdw on HA 2026.9.1.

### Fixed
- Starting a scan right after a cancel failed with "scanner busy": HP MFPs
  answer 503 and report *Processing* for a few seconds while the cancelled
  job winds down. `create_job` now waits (up to 15 s) for the device to go
  Idle before purging stale jobs and retrying; only a device that stays busy
  is reported as busy.
- Zeroconf: TXT keys are matched case-insensitively (HP advertises `uuid`,
  not `UUID`), so discovered HP devices get their UUID as unique id.

### Added
- jsdom test suite for the Lovelace card (`npm run test:card`) in CI: start /
  cancel / 409, hass-setter progress rendering incl. the latched "Open scan"
  link, renamed-sensor auto-detection, error-card healing, editor events.

## [0.4.1] - 2026-09-06

### Fixed
- Options flow crashed on Home Assistant 2024.8–2024.11: `self.config_entry`
  only exists on `OptionsFlow` from 2024.12. Minimum supported version is now
  2024.12 (declared in `hacs.json`).

### Changed
- Legacy cipher option uses `SECLEVEL=1` instead of `SECLEVEL=0`: still admits
  the non-PFS AES suites some HP MFPs need, without export/NULL-grade suites.
- `hacs.json`: `hide_default_branch`, so HACS offers only tagged releases.
- CI: `node --check` on the card.

## [0.4.0] - 2026-09-06

### Added
- Zeroconf/mDNS discovery (`_uscan._tcp`, `_uscans._tcp`): scanners show up
  under *Discovered*; the TXT `rs` resource path is honoured for devices
  that don't serve `/eSCL`.
- `escl_scan.start` (with response) and `escl_scan.cancel` services, plus a
  `button.<scanner>_scan_now` entity, so automations and stock cards can
  trigger scans without the REST API.
- Translated sensor states and entity names (`translation_key`), icons.
- *Copy to folder* option: every finished scan is atomically copied to a
  directory of your choice (Paperless-ngx consume folder), validated against
  `allowlist_external_dirs`. New `file_path` / `copied_to` attributes.
- Diagnostics download (capabilities, scans, redacted entry data).
- Card is available in the dashboard card picker with a visual editor
  (title, sensor entity) and a preview.
- `ScannerCapabilities` is read at setup: device page shows the real make,
  model and serial; the config entry's unique id is the serial/UUID (survives
  DHCP changes); the scan region is the reported bed size per source (A4 and
  Legal are no longer cropped to Letter); a requested DPI snaps to the nearest
  supported resolution.
- Duplex scanning for Feeder scans on duplex-capable ADFs: `duplex` in the
  start body and a "scan both sides by default" option.
- Card `entity:` option; the card also auto-detects a renamed scan sensor.

### Fixed
- Creating a job while another client is scanning no longer deletes that
  client's job; the start fails with "scanner busy" instead.
- Per-page ADF scanners that answer 503 between sheets no longer get their
  batch truncated: NextDocument retries while JobInfo reports the job alive.
- Failed/canceled scans are dropped from memory after the retention TTL.

### Removed
- `pages_total` attribute (was never populated).

## [0.3.0] - 2026-09-06

### Added
- Multi-document ADF scans are merged into a single PDF (issue #1). Scanners
  that return one PDF per page are now handled; bundle-mode scanners keep the
  single-file fast path. Adds a `pypdf` requirement.
- `pages_done` reports the real page count of the resulting PDF for
  bundle-mode scanners.

### Changed
- Test suite (pytest + `pytest-homeassistant-custom-component`) and ruff lint
  run in CI alongside hassfest and HACS validation.
- Card colours follow the active HA theme; `single_config_entry` declared;
  sensor grouped under a device.

## [0.2.0] - 2026-07-20

### Fixed
- Second "Scan now" tap during a running scan no longer kills the running
  job; the start endpoint returns `409` instead.
- Entry reload/unload cancels in-flight driver, poll, and hold tasks and
  closes the HTTP session (no orphaned tasks after options changes).
- Scan output streams straight to disk; the PDF is never buffered in RAM
  (large ADF batches no longer risk OOM on small hosts).
- TTL purge no longer mutates coordinator state from an executor thread.
- A periodic sweep purges expired scan files even when no new scan runs.
- Card title updates live in the dashboard editor.
- Options flow validates port/DPI/TTL ranges and masks the password field.

### Changed
- One shared aiohttp session and SSL context per scanner instead of one per
  request.
- Card renders from the `hass` object Lovelace pushes; no more
  `state_changed` firehose subscription. Scans started from another device
  are reflected too.
- Card loads solely via `add_extra_js_url`; stale Lovelace resource entries
  from older versions are reaped once.
- Heal observer for the Lovelace `whenDefined` race disconnects after 12 s.

## [0.1.7] - 2026-05-24

Last release before the stability review. See GitHub releases for earlier
history.

[Unreleased]: https://github.com/wleonhardt/ha-escl-scan/compare/v0.5.2...HEAD
[0.5.2]: https://github.com/wleonhardt/ha-escl-scan/compare/v0.5.1...v0.5.2
[0.4.3]: https://github.com/wleonhardt/ha-escl-scan/compare/v0.4.2...v0.4.3
[0.4.2]: https://github.com/wleonhardt/ha-escl-scan/compare/v0.4.1...v0.4.2
[0.4.1]: https://github.com/wleonhardt/ha-escl-scan/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/wleonhardt/ha-escl-scan/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/wleonhardt/ha-escl-scan/compare/v0.1.7...v0.3.0
[0.2.0]: https://github.com/wleonhardt/ha-escl-scan/compare/v0.1.7...v0.3.0
[0.1.7]: https://github.com/wleonhardt/ha-escl-scan/releases/tag/v0.1.7
