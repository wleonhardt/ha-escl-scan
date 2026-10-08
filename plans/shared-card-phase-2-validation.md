# Phase 2 capability and upload validation

Status: implementation, hosted validation and live API/job verification complete;
physical output confirmation pending. Scan v0.7.0 and print v0.6.0, 2026-10-08.

## Implementation

Both integrations expose an authenticated entity-scoped capabilities view,
including schema version, resolved sensor, compact identity, supported options,
integration limits and fresh/stale/unknown cache metadata. The cache modules
are identical and independent, with a 15-minute success TTL, five-minute
failure backoff, 15-second fetch bound and serialized on-demand reads.
No capability polling or job-sensor recorder churn was added.

Print uploads accept optional copies and sides through the existing shared
submission path. Both service/upload reject coerced or invalid copy counts,
unsupported advertised settings and malformed multipart fields. Explicit sides
require fresh paper defaults and never submit after a failed read.
Existing omitted-field requests retain their behavior.

Scan keeps resolution/color profiles separate by source and automatic-duplex
mode, rejects known unsupported sources/colors, and freezes the scan region
through manual front/back passes. Missing vendor data remains permissive.
Capability XML is bounded to 1 MiB. No frontend card changes in this phase.

## Automated checks

- Scan: 182 Python tests, 36 card tests after npm ci, Ruff and hosted validation.
- Print: 180 Python tests, 29 card tests after npm ci, compileall, Ruff and hosted
  validation.
- Added coverage for concurrent reads, TTL expiry, stale retention/recovery,
  failure backoff, timeout, unload, authentication/read-only users, target
  routing, source-specific profiles, region stability across passes, bounded
  XML, all binding modes, copy validation and duplicate/oversized metadata.
- All six hosted checks passed for scan `dd81231` and print `8f49c85`.

## Live verification

Previous installed pair: scan v0.6.0 / print v0.5.0. Backed up integrations and
dashboard resources/configuration to
`/config/.document-card-backups/before-phase2-v070-v060-20261008.tar.gz`.
Both job sensors were idle before installation. Deployed Python module hashes
matched repository files; HA 2026.9.4 restarted successfully with both updates.

Live capability responses returned 200 with the expected entities and schema.
The HP advertises glass DPI 75/150/200/300/600/1200 and feeder DPI
75/150/200/300, color/gray on both, manual duplex scanning and no automatic
duplex scan. Print advertises all three binding modes, PDF/JPEG/PNG and
999 device copies (the integration still caps requests at 99).
Four simultaneous reads of each endpoint returned identical fetch/attempt
timestamps, while explicit sides jobs refreshed print metadata.

Eight real multipart rejections passed without starting a job: copies 0,
fractional, boolean text, over-limit; invalid sides; duplicate copies; unknown
field; unknown sensor. Both job sensors stayed idle after these checks.

The physical print matrix uses four sheets:

| Test | Request | Expected output |
| --- | --- | --- |
| A | One-page PDF; copies=2; one-sided | Job 365 completed, 2/2 impressions; expected two identical sheets with blank backs |
| B | Two-page PDF; copies=1; two-sided-long-edge | Job 366 completed, 2/2 impressions; expected one sheet with book-turn orientation |
| C | Two-page PDF; copies=1; two-sided-short-edge | Job 367 completed, 2/2 impressions; expected one sheet with notepad-flip orientation |

PDF pages were rendered and visually checked before submission.
All three submissions returned 200 and distinct job IDs; each was submitted
exactly once, followed through processing to completed, with 2/2 impressions
and job-completed-successfully. Physical sheet count/orientation confirmation
is pending; protocol completion alone does not prove the paper layout.

## Remaining limits

Automatic-duplex scanning needs another scanner; the HP feeder is simplex.
Multiple-printer routing and unavailable-device behavior have automated coverage;
no second physical printer is available. Settings controls ship in Phase 3.
