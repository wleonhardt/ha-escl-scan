# Phase 4 validation — 2026-10-09

Released and installed: **scan 0.10.0 / print 0.9.0**. Phase 4 is complete.
The visible Two-sided layout is preserved. Localization remains translation-ready
English; additional reviewed languages are still separate work.

## Implementation and automated evidence

- Scan: 225 Python tests and 64 card tests pass; Ruff passes.
- Print: 217 Python tests and 53 card tests pass; Ruff and compileall pass.
- Total: **559 tests**. Card dependencies installed with npm ci. Both local core
  synchronization checks pass and the vendored core sources are byte-identical.
- Both release heads passed all six hosted checks: hassfest, HACS, Python compile,
  Ruff, card and Python tests. Both tag release workflows succeeded and published
  non-draft, non-prerelease HACS releases.
- Scan release commit: `31a6c55e930eb1d354560e42cac1ccabf219b967`.
  Print release commit: `3ba0ce97fde0957d7e009559192b2aec74c6d882`.
- Regressions cover pushed external jobs, two cards/remount, local staged-file
  preservation, missing sensors, reused job numbers with submission timestamps,
  delayed cancel bodies, cancel requests across progress updates, frozen targets,
  scan navigation/start/back-side/download races, zero/unknown/sheet counters,
  HA disconnection, stale availability, safe long error text, polling coalescing,
  timeout/backoff/recovery/unload and explicit target validation. Existing old API,
  protocol, duplex privacy, cleanup and resource-registration checks still pass.

## Live installation and browser checks

Both job sensors were idle before installation. Backed up the two integrations,
resource registry and dashboard to
`/config/.document-card-backups/before-phase4-v0100-v090-20261009.tar.gz`.
The active dashboard storage file is `.storage/lovelace.lovelace`.
Installed the complete components and restarted HA 2026.9.4. The final small
print-card cancel guard was copied and its entry reloaded successfully (200,
no further restart required).

Both entries load. Each native Connection entity reports `on` with a fresh
successful protocol check, independently of each job sensor's `idle` state:

- eSCL: `binary_sensor.hp_color_laserjet_mfp_m283fdw_connection`
- IPP: `binary_sensor.hp_color_laserjet_mfp_m283fdw_connection_2`

Replaced only the stale/inverted legacy offline card and summary with two native
Tile cards, named Scanner and Printer; each opens its own connection information.
Preserved the page-count chips, task cards, titles, navigation and Two-sided UI.
The shorter names fit narrow tiles without truncation.

BrowserOS neo checks in two independent tabs at 320 and 390 px:

- Both real cards load without Configuration error; healthy connection warnings
  stay hidden, and only the current hashed module for each card loads after refresh.
- Isolated fixtures use mocked transport/state attached below the HA app context;
  they never replace real HA state or save a test dashboard. Two print instances
  agree on pushed processing/completion, a remount recovers the job, and reconnect
  restores terminal state. Scan retains manual-back instructions and counts.
- HA disconnection disables primary/cancel actions and shows reconnection guidance.
  Failed device checks show power/connection guidance separately from job outcomes.
- Narrow cards, manual-back controls and warnings have no horizontal overflow.
  Long error details remain literal text. Scan Options measures 356 px inside a
  390 px viewport without overflow; Back closes it and restores focus, and Forward
  does not reopen it. Existing automated Options tests pass for both cards.
- Removed all temporary fixtures by reloading. No test print, scan, cancel or
  back-pass request was sent to the physical device during this phase.

## Asset and rollback record

The shared core stays inline in the one card asset per integration. No additional
runtime asset, framework, global shared element name or build dependency was added.
Canonical source and update procedure: `shared/card-core.js` / `shared/README.md`.

| Asset | SHA-256 |
| --- | --- |
| Scan card | `7b7f76e00ad68d7921c2175cd7f4d1ea1521d7533d368c0a108c0d1621f2f30d` |
| Print card | `2d4afd379259bcdc5e6aa8de437550b17c32d2cad08c368697621faba8cc49a0` |
| Shared core v2 | `e6cbdf446323ebea9bc436d30040375b2fbecb3dff5b5a8e3525b920059500e5` |

Installed card hashes match source. Final resources are
`/escl_scan/card-7b7f76e00ad6.js` and `/ipp_print/card-2d4afd379259.js`, one each.
Startup can initially load an old bootstrap URL; a subsequent dashboard refresh
loads only the registered current URLs. Existing resource tests cover stale/duplicate
cleanup and old URL replacement. A live rollback was not performed; the prior
scan 0.9.0 / print 0.8.0 release pair and complete backup remain available.

## Limits and next gate

This recovers jobs still tracked by the running integration, not unrelated jobs
submitted directly to a device or jobs lost across an HA/integration restart.
Durable scan results and activity remain Phase 6. Live disconnection/job state
transitions were simulated; real IPP/eSCL reachability was checked read-only.
No fresh physical-phone or assistive-technology acceptance is claimed here.
Prior HP physical acceptance remains recorded in the compatibility validation.

Phase 5 is next: native Tile and optional current Mushroom Template features,
while retaining standalone cards. Verify declared minimum/current HA native-host
support and Android registration before recommending migration. Automatic-duplex
scanner hardware and additional vendors/bridges remain external coverage limits.
