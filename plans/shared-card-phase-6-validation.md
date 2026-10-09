# Phase 6 validation — 2026-10-09

Status: implementation complete; release and deployment validation in progress.
Release pair: scan 0.12.0 / print 0.11.0, shared presentation core v4.
The preceding alignment revision was accepted by the user on the phone, including Back.

## Behavior and storage

One successful scan result survives idle, dashboard reload and HA restart while
its existing PDF is retained. Download stays authenticated, including for
non-admin users; no upload/document copy is introduced. Fixed expiry cannot be
extended by restart, touching the file, or increasing the retention setting.
Missing/expired files lose their action. Manual fronts, failed and canceled
jobs never become the latest result. Earlier orphan files are not backfilled.

Print stores at most ten outcomes per entry for seven days from submission.
Only metadata is saved, without documents or reprint. Interrupted tracking
restores as unknown, without inventing a finish time, replaying/canceling jobs
or resuming polls. Both attributes are excluded from Recorder. Entry removal
removes its own metadata Store. See the [storage decision](decisions/2026-10-09-durable-results.md).

Both cards have collapsed, matching activity disclosures beneath their normal
actions. Downloading an older PDF preserves a newer scan; target changes,
detach and latest-result replacement discard obsolete replies. The fresh primary
Download still returns to Scan, while Latest scan remains independently usable.
New standalone Sections cards default to auto rows; fixed-height existing cards
need Rows: Auto to accommodate expanded content. Examples are updated.

## Automated and runtime evidence

- Scan: 240 Python + 76 card tests; print: 229 Python + 64 card tests. **609 tests**.
- Both npm ci/card suites, Ruff, shared-core parity and print compileall pass.
- Coverage includes restart, idle, expiry, tighter TTL, touched files, purge,
  missing/symlink files, corrupt metadata, private fronts, failed/canceled scans,
  reused print IDs, separate printer entries, stale downloads and text safety.
- Real HTTP tests: restored PDF works with a read-only HA user's token; the same
  URL rejects anonymous requests with 401. No admin websocket dependency.
- Actual HA 2024.12.5 Store runtime (isolated temporary directory) saves/restores
  both final modules. Its Store options and Recorder exclusion APIs are compatible.
  This is storage API coverage, not a device test on minimum HA.
- Current HA 2026.9.4: isolated native Tile and Mushroom fixtures at 320/390/768px;
  collapsed alignment, expanded long names and outcomes, dark/light theme
  variables, 44px summary/download targets, keyboard disclosure and Options/Back
  with focus return. No horizontal overflow or device requests from these fixtures.
- Isolated JS checks: scan alone, print alone, both new, new scan/old print
  0.10.3 and old scan 0.11.2/new print all initialize normally.

## Release and live installation

Pending hosted checks, tags, installation and startup verification.
No physical print/scan has been submitted for this phase. The first new result
will populate the production sections; pre-upgrade jobs are not reconstructed.
