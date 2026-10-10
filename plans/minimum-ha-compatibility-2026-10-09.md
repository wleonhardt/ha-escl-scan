# Minimum Home Assistant backend compatibility — 2026-10-09

## Scope

The user requested isolated verification of both integrations against their
advertised minimum, fixes for reproduced incompatibilities, and a persistent CI
check with no new settings or runtime dependencies. HACS declares **2024.12.0**
in both repositories. Earlier Phase 5 testing of 2024.12.5 covered frontend
hosting only; this task exercises real backend APIs with simulated devices.

## Reproduction and fixes

- **Scan 0.12.3:** importing `config_flow` fails with `ModuleNotFoundError` for
  `homeassistant.helpers.service_info.zeroconf`, preventing setup/discovery on
  2024.12.0. Scan 0.12.4 falls back to the original HA component export, matching
  Print's existing compatibility pattern. Modern HA uses the current import.
- **Print 0.11.4:** entity/device-targeted `print_file` calls raise `TypeError`
  because the old `async_extract_config_entry_ids` requires an explicit `hass`.
  Three existing service-routing regressions reproduced this. Print 0.11.5
  selects the actual helper signature once at import; routing remains delegated
  to HA. No exception-driven fallback, print retry or alternate target rules.
- Additional failures belonged to newer-only test assumptions: service-call
  constructors, device registry lookups and Lovelace's data shape. Tests now
  use the applicable real API on each version. Concurrent Print setup goes
  through HA's real setup/platform lifecycle so teardown owns its callbacks.
  The Scan resource-failure unit test uses HA's real URL manager without
  unnecessarily starting an HTTP listener. No assertions are skipped or marked
  expected failures for the minimum version.

## Isolated environment and CI

- Python 3.12, HA 2024.12.0, matching test harness 0.13.190, bundled aiohttp
  3.11.9, frontend 20241127.4 and zeroconf 0.136.2. Scan additionally tests its
  declared pypdf lower bound, **4.0.0**.
- Minimum test requirements pin pycares 4.5.0. The older aiodns dependency range
  otherwise admits pycares 5.1.0, whose persistent shutdown thread fails the
  historical harness's cleanup checks. This is a test environment constraint;
  neither integration adds or changes a runtime requirement.
- A separate `Minimum HA compatibility` job in each validation workflow runs
  the existing full Python suite. It asserts that installed HA equals the
  version in `hacs.json`, preventing the test environment silently drifting
  away from the advertised floor. Normal newer-HA and card checks remain.
- No custom HA shim, separate compatibility framework or new test library.
  Core setup, services, HTTP routes, capability/diagnostics handling, resource
  registration, unload and durable-result tests all run on actual old HA APIs.
  Device I/O is mocked or targets local stand-in servers; production HA and the
  HP are not accessed. Temporary configs, state and environments are isolated.

## Local verification

- Minimum HA: Scan **295** Python tests; Print **292** Python tests pass.
- Existing newer environments: Scan **295** on HA 2026.9.4 / Python 3.14;
  Print **292** on HA 2026.2.3 / Python 3.13 pass.
- Scan **78** and Print **65** card tests pass after clean dependency installs.
  Both dependency audits report zero vulnerabilities. Ruff, compilation and
  workflow/manifest syntax checks pass.
- Historical test dependencies emit deprecation warnings; no integration test
  is skipped to obtain these results. These checks do not certify physical
  output on every old-core/device pairing or additional vendor hardware.

## Delivery

- Scan source `9ea5b2b99a36790df42d909738f3f086f9685a19` passed all seven
  [hosted checks](https://github.com/wleonhardt/ha-escl-scan/actions/runs/38019023347),
  including the clean minimum-version job. The successful
  [release workflow](https://github.com/wleonhardt/ha-escl-scan/actions/runs/38019157143)
  published [Scan 0.12.4](https://github.com/wleonhardt/ha-escl-scan/releases/tag/v0.12.4).
- Print source `23ffee788c88dc35447448889316deb8acd59432` passed all seven
  [hosted checks](https://github.com/wleonhardt/ha-ipp-print/actions/runs/38019032694),
  including the clean minimum-version job. The successful
  [release workflow](https://github.com/wleonhardt/ha-ipp-print/actions/runs/38019157707)
  published [Print 0.11.5](https://github.com/wleonhardt/ha-ipp-print/releases/tag/v0.11.5).
- Minimum-version verification is now part of every normal validation run,
  including the existing weekly schedule. No additional automation was created.
- No production files, dashboard configuration or device settings were changed;
  no live HA upgrade/restart or device job was performed. The live installation
  stays Scan 0.12.3 / Print 0.11.4. This task's isolated acceptance is complete.

## HACS installation and dashboard acceptance — 2026-10-10

The user subsequently requested the latest HACS versions on the live instance
and verification of the card setup. This is separate from the isolated tests
above.

- Both integrations were present on disk but HACS reported `installed: false`
  and no installed version. Refreshed their repository metadata, then used
  HACS's own `hacs/repository/download` operation to install stable Scan 0.12.4
  and Print 0.11.5. No manual component copy or HACS storage edit was used.
- Backed up both component directories, the main dashboard, resources and
  HACS tracking files to
  `/config/.document-card-backups/before-hacs-latest-20261010-complete.tar.gz`.
  All 25 Scan and 20 Print shipped files match their release-tag SHA-256 hashes.
- Both devices were idle before the single restart. `ha core check` passed.
  After restart, diagnostics report Scan 0.12.4 / Print 0.11.5, both entries
  are loaded, and both HP connections are reachable. HA stays on 2026.9.4.
- HACS now reports both repositories installed, matching latest versions,
  with no pending update or restart. The new `update.escl_scan_update` and
  `update.ipp_print_update` entities both report up to date; beta and automatic
  updates remain disabled.
- Read-only eSCL and JPEG-specific IPP capability lookups return fresh results.
  Latest scan and recent print activity match the pre-restart snapshots
  exactly. The scan was already expired before the update; no download claim
  is made for that expired file. No physical scan or print job was submitted.
- Main `/lovelace/printer` and preview `/lovelace/native-documents` configs
  already bind the native features to the correct sensors, with one built-in
  Vertical stack per card. Each integration has exactly one current resource:
  `/escl_scan/card-a5a7bef90d84.js` and `/ipp_print/card-d5f2508ef4af.js`.
  No dashboard/resource edits were needed.
- Fresh main dashboard at 390 × 844 renders one Scan and one Print feature,
  no error card, aligned compact switches/actions and the device heading.
  Scan/Print Options fit, and browser Back closes each without leaving the
  dashboard. Expanding Scan changes its feature height from 216 to 420 px
  while Print stays 216 px; expanding Print changes it to 416 px while Scan
  stays 216 px. Both disclosures were left collapsed.

Live installation acceptance is complete. The release test/CI results above
remain applicable: this follow-up changes deployment and records only.
