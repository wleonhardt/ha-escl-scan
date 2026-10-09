# Phase 2 capability and upload validation

Status: implementation, hosted validation and live API/job verification complete;
physical requirements subsequently confirmed on scan v0.8.2 / print v0.7.2.
Original implementation: scan v0.7.0 and print v0.6.0, 2026-10-08.

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
Capability XML is bounded to 1 MiB. The initial Phase 2 change was backend-only;
subsequent user-feedback card fixes are recorded below.

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
duplex scan. The then-current print API advertised all three binding modes,
PDF/JPEG/PNG and 999 device copies (the integration caps requests at 99).
The compatibility rollout later corrected that API's octet-stream inference:
this HP explicitly supports PDF/JPEG, not PNG.
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

## User-feedback card fixes — scan v0.7.1 / print v0.6.1

Installed as a follow-up to the Phase 2 backend work. The scan card reads fresh,
entity-scoped capabilities for its existing two-sided label: Automatic duplex
or Two passes required. Unknown/stale/older backends retain cautious wording.
Requests coalesce, use bounded caching/backoff, and abort on target change or
native disconnect. The HP's live response correctly yields Two passes required.

Download PDF replaces Scan on completion and remains through the server's idle
reset. Authenticated fetch failures keep the retry action, expired PDFs restore
Scan with guidance, and stale responses cannot overwrite a new scan or target.
Successful handoff to the browser restores Scan; actual save-dialog decisions
are not observable. This is card-instance retention, not persistent history.
The print card clears the submitted filename when job tracking ends, including
immediate completion; old updates cannot affect a new staged file or job.

Validation: scan 182 Python / 42 card tests, print 180 Python / 29 card tests,
Ruff in both, print compileall, npm ci and diff whitespace checks pass (433 tests).
Regression coverage includes capability schemas/targets/staleness/failures,
coalescing and cache expiry, native disconnect, download retries/invalid bodies,
expired files, idle retention, late responses, consumed-result deduplication,
print completion snapshots and late prior-job updates.
All six hosted checks passed for scan `d3ca268` and print `c945729`.

Both sensors were idle for installation. Backup:
`/config/.document-card-backups/before-card-fixes-v071-v061-20261008.tar.gz`.
Copied card/manifest changes only and reloaded both entries (200,
require_restart=false). Deployed card hashes match local files. After a fresh
browser reload, exactly one resource per card is registered and loaded:
`/escl_scan/card-f10c82bb7e7e.js` and `/ipp_print/card-00e35129a20e.js`.
Both real dashboard cards load without Configuration error.

Used the installed components in an isolated browser fixture on real HA,
with device submissions blocked and the capability read using real auth.
Simulated print completion cleared the filename; a scan completion followed by
idle retained Download PDF. Clicking the real button downloaded the one-page
Phase 2 test PDF as `card-download-verification.pdf`; byte count 2061 and SHA-256
`0d909118730fc3a42850077e010d90944d83f8cd869975cfcc36413ec6fe8276`
matched the source, then the action returned to Scan. This verifies browser
handoff using a fixture response, not a newly produced physical scan.
Paired layouts at 320/390/768px had no horizontal overflow, matching 202px outer
card heights and 44px action targets. Dark-theme screenshots at 320/390px pass.
The user subsequently confirmed the physical phone flow: Download PDF works
and the action returns to Scan. This closes the phone download check. The
earlier four-sheet print count/orientation confirmation and HACS release tags
remain pending; no additional physical print or scan was submitted by the agent
for these UI checks.


## Physical gate closure on the current candidate

On 2026-10-08 the user confirmed long-edge output from job 368 and exactly two
short-edge duplex sheets from job 370, each FRONT/BACK upright when flipped like
a notepad. Job 370 used copies=2 and completed 4/4 impressions. These later tests
close the copy-count and binding acceptance requirements on print 0.7.2; they do
not retroactively assert inspection of the original jobs 365–367. Phone download,
Options fit and Back navigation are also confirmed. Release tags remain pending.
See [paired validation](compatibility-validation-2026-10-08.md).
