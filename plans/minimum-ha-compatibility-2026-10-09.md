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

Prepared as Scan 0.12.4 / Print 0.11.5. Hosted CI and release results follow.
The live installation stays Scan 0.12.3 / Print 0.11.4 during this isolated task.
