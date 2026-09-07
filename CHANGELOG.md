# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/); versions follow SemVer and
match `custom_components/escl_scan/manifest.json`.

## [Unreleased]

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

[Unreleased]: https://github.com/wleonhardt/ha-escl-scan/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/wleonhardt/ha-escl-scan/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/wleonhardt/ha-escl-scan/compare/v0.1.7...v0.3.0
[0.2.0]: https://github.com/wleonhardt/ha-escl-scan/compare/v0.1.7...v0.3.0
[0.1.7]: https://github.com/wleonhardt/ha-escl-scan/releases/tag/v0.1.7
