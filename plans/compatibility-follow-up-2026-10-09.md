# Rollout closeout and compatibility follow-up

Status: main dashboard promoted; available-HP compatibility follow-up complete.
Scan 0.12.1 / Print 0.11.1 released, installed and verified after restart.
Additional vendor/bridge hardware and automatic-duplex ADF acceptance remain open.
The original six-phase rollout is complete. This follow-up is explicitly
requested by the user and does not silently include multi-scanner support,
new transports/authentication, converters, presets or new translations.

## Main dashboard

Moved the accepted native Tile Scan/Print pair and its device heading into
`/lovelace/printer`. Retained one Vertical stack per tile for independent growth,
all original connection tiles, page/jam chips, navigation, theme and other views.
The preview remains available. No integration update or restart was required.
Dashboard backup: `/config/.document-card-backups/before-native-main-20261009.json`.
Saved/read-back configuration matches the reviewed candidate. Real host checks
at 320/390/768 px pass for each disclosure independently, both open, and closing;
a fresh main-dashboard load also passes.

## Compatibility scope and gates

1. Discover actual HP `_uscan`, `_uscans`, `_ipp` and `_ipps` advertisements.
   Test first-time confirmation and duplicate detection using an isolated HA
   registry/configuration, with read-only device probes. Do not remove or modify
   production entries, submit jobs or alter device network settings. Distinguish
   received LAN advertisements, flow acceptance and endpoint reachability.
2. Reproduce card-mod's Options warning, identify its origin and assess a narrow
   fix against HA's public dialog contract. Verify both Options dialogs, Back,
   closure and focus, with/without card-mod and on minimum/current HA as needed.
3. Provide a structured device report and compatibility matrix. Distinguish
   synthetic fixtures, read-only probes and physical output acceptance. Only
   implement vendor workarounds after a representative failure is reproduced.
4. Keep external physical checks explicit: automatic-duplex ADF, additional
   vendors, AirSane/ipp-usb and multi-device hardware need devices/reporters.
   Prepare the reporting path here; contacting reporters requires authorization.

Implementation changes require focused regressions, all repository checks,
version/changelog updates and hosted CI before release/install. Documentation
and dashboard-only work need no integration version or tag. Record evidence and
remaining limits below as the checks finish.

## Discovery findings and fixes

Actual HP DNS-SD advertisements were received on the LAN for HTTP eSCL/8080,
HTTPS eSCL/443, IPP/631 and IPPS/631. The resource paths are `eSCL` and `ipp/print`.
No saved production connection setting was used to manufacture these records.

The isolated HA 2026.9.4 flow registry reproduced two failures: the secure HP
endpoints reject the default cipher negotiation; Print retained its failed
confirmation, while Scan created a configured entry despite an unusable endpoint.
Both secure endpoints passed read-only probes when the existing legacy cipher
option was explicitly enabled. Plain discovery endpoints passed with defaults.

Scan 0.12.1 shares the manual setup probe with discovery, closes clients on all
paths and rechecks the single-scanner limit after awaiting I/O. Failed discovery
stays on the form. Both integrations expose the existing legacy cipher option
on secure discovery confirmation, initially off. TLS/port/path remain as
advertised; no automatic fallback or global SSL policy change is introduced.
The user must choose the compatibility setting before another probe uses it.

All four live advertisement cases pass in the isolated config-entry flow:
confirmation, stored endpoint, read-only device response, rediscovery rejection
and exactly one entry. Secure cases first prove a default failure creates no
entry, then explicitly retry with legacy ciphers. Integration setup was stubbed
in this fixture to avoid registering another running coordinator; these are
flow-level runtime checks, not a second fully onboarded HA installation. Actual
LAN delivery and endpoint I/O are live; production entries, UUIDs, devices,
network settings and jobs were left alone. Raw identifying captures stay outside
Git. Ordinary tests remain socket-blocked and use patched network boundaries.

## card-mod finding and fix

Reproduced `TypeError: this.requestUpdate is not a function` with installed
card-mod 4.2.1 after opening Options. Its
[dialog hook](https://github.com/thomasloven/lovelace-card-mod/blob/master/src/patch/ha-dialog.ts)
wraps every `show-dialog` host and assumes Lit update methods plus a shadow root.
Our plain HTMLElement routing host has no asynchronous rendering or visible
surface; its panel remains in the owning card for theme and navigation handling.

Shared core v5 provides an empty shadow root and already-completed synchronous
update hooks on that small host. card-mod can inspect it without throwing and
finds no HA dialog shell to restyle. No Lit dependency, private card-mod registry
mutation, window error suppression or change to other custom cards is involved.
The new regression reproduces the failure on the previous module and verifies
opening, HA closure, stale parameters and focus after the fix in both repositories.

Exact candidate modules loaded under isolated names coexist with the installed
core v4 modules. On the real HA/card-mod 4.2.1 host, Scan and Print Options render,
card-mod confirms it patched each candidate, no errors are captured, and Back
closes each panel. The visible panel still lives in its original card shadow root.

## Reporting and validation

Both compatibility guides now distinguish completed HP physical acceptance from
synthetic vendor coverage, read-only bridge probes and unavailable hardware.
New device-report issue forms collect firmware, transport/bridge, setup options,
actual operations and reviewed diagnostics, including successful reports. No
reporter was contacted and no unsupported hardware support is claimed.

Required local checks pass: Scan 243 Python + 78 card; Print 231 Python + 65 card
(617 total), npm ci, Ruff and Print compileall. JSON/translations, issue/example
YAML and shared-core parity are checked. Live discovery adds four separate HP
flow checks. Fixed an existing unquoted colon in Print's bug-report YAML while
validating the reporting forms.

## Delivery and installed verification

- Code commits: Scan `3ad824a`, Print `96effa3`. All six hosted checks pass in
  each repository: [Scan validation](https://github.com/wleonhardt/ha-escl-scan/actions/runs/37982517673),
  [Print validation](https://github.com/wleonhardt/ha-ipp-print/actions/runs/37982518449).
- Published [Scan 0.12.1](https://github.com/wleonhardt/ha-escl-scan/releases/tag/v0.12.1)
  and [Print 0.11.1](https://github.com/wleonhardt/ha-ipp-print/releases/tag/v0.11.1)
  through successful tag-triggered release workflows.
- Installed the tracked release sources with rollback archive
  `/config/.document-card-backups/before-compat-v0121-v0111-20261009.tar.gz`.
  HA configuration check passed; both jobs were idle before the core restart.
  HA remains 2026.9.4. Both entries return `loaded` and both devices `reachable`.
- Installed manifests and full card hashes match the releases. Active resources
  are `/escl_scan/card-a5a7bef90d84.js` and `/ipp_print/card-d5f2508ef4af.js`;
  resource IDs are preserved. Both native features render on a fresh main page.
- With installed card-mod 4.2.1 wrapping each real dialog host, Options opens,
  Back closes and focus returns to its button for both cards. No captured errors
  or rejected promises. At 390 px both dialogs are 356 px wide. Independent
  disclosure expansion passes again at 320/390/768 px without moved controls,
  stretched neighbors or horizontal overflow.
- Latest scan `8812dcdc7880` and print job 373 retain their metadata and expiry.
  The authenticated PDF still returns 200, 540,520 bytes and SHA-256
  `26f4d5cf31f802c94c5808e18de42eba9e2cefac8db4028854d0771f0c8c0313`.
  No scan or print was submitted during this follow-up.
- Removed the temporary candidate modules from HA; no candidate tag/config was
  saved in either dashboard. Main migration and preview remain intact.

## Next evidence needed

Use the new device report forms to collect reproducible cases from automatic
duplex scanners, other printer/scanner vendors and AirSane/ipp-usb installations.
Turn redacted captures into focused regression fixtures before adding a vendor
workaround. Physical output acceptance still requires the relevant device.
The user confirmed the dashboard looks good after installation. Multi-scanner
routing is explicitly deferred to the backlog by the user's 2026-10-09 decision.
The recommended next focus is the bounded diagnostics and real-device fixture
work in the [scope decision](decisions/2026-10-08-compatibility-follow-ons.md).

## Epson report review — 2026-10-09

Read the complete body and comment history of
[issue #5](https://github.com/wleonhardt/ha-escl-scan/issues/5). The issue is closed.
The WF-4830 reporter [confirmed success on October 8](https://github.com/wleonhardt/ha-escl-scan/issues/5#issuecomment-6069504848);
the queue incorrectly still marked that confirmation as pending. The reply does
not specify installed release, firmware, orientation or batch length. The ET-4950
report describes success after manually correcting the duplex height but has no
subsequent acceptance of a released fix. Neither report includes a full capture.

All three ET-4950 observations already have corresponding changes:

- Duplex region: 0.4.4 separated the duplex maximum (2550 × 3510) from the
  simplex maximum (2550 × 4200). Current selection passes the duplex region
  through the tracked scan into job creation; Letter and A4 fit. Oversized custom
  duplex regions are rejected before a job is created.
- Inverted backs: 0.4.5 added the existing opt-in rotation option. Current code
  rotates alternate pages after assembling the complete PDF and preserves
  metadata. The option remains off by default; no model-wide assumption is made.
- Long batches: current document requests have no total-transfer timeout, use a
  900-second socket-read stall limit and bound temporary-response retries to
  900 seconds. Control requests retain their short timeout. The report supplies
  no response trace establishing a remaining problem with this policy.

Added a provenance-labelled report fragment with only the reported simplex
maximums and duplex fields; root/Adf wrappers are explicit synthetic scaffolding.
It is not a full Epson capability capture. New coordinator regressions cover full
simplex, full duplex, Letter/A4 duplex and rejection of a simplex-sized custom
duplex area. Existing automatic-duplex rotation coverage now also exercises
separate one-page downloads, so rotation cannot restart at each chunk boundary.

No additional runtime defect was reproduced or vendor workaround justified.
Only tests and documentation change; Scan remains 0.12.1 with no new setting,
dependency, release tag or HA restart. No physical job or reporter message is
needed for this review. Further ET-4950 work needs released-version diagnostics
and an exact failing operation; orientation/long-batch acceptance needs the
device or explicit reporter results.

Validation: 249 Python tests and 78 card tests pass (327 total), plus Ruff,
compileall, npm ci and diff whitespace checks. An isolated process restoring the
original simplex-for-duplex region bug fails exactly the two relevant new cases
(full duplex and oversized custom duplex), while the other three region cases
pass. No tracked runtime file was modified by that check. Hosted checks run on
the pushed test/documentation commit.

## Scanner control-response hardening — 2026-10-09

The user approved reproducing and fixing scanner response-size gaps, without new
settings or dependencies. Scope is control replies only. PDF storage safeguards,
print upload concurrency and additional scanner diagnostics remain proposals.

Four local aiohttp regressions failed against 0.12.1: direct JobInfo accepted a
valid XML body over 1 MiB; idle recovery accepted oversized Idle status; cleanup
used that oversized status to delete a fixture's stale job; and scan-start error
handling read the whole oversized body before truncating the displayed string.
These are controlled local fixtures, not claims that the HP sent oversized data.

One private asynchronous reader now applies the existing 1 MiB limit to all
control bodies consumed by the scanner client. It counts decompressed bytes
during streaming, with no reliance on Content-Length, and runs inside the
existing response contexts. Main status/capability reads reuse it, eliminating
their duplicate loops. JobInfo, idle recovery, cleanup status and creation error
reads use it too. Error details still stop at 200 characters; unknown charsets or
invalid character data cannot obscure the HTTP failure.

Oversized status cannot confirm Idle or authorize deletion; cleanup remains
restricted to an idle scanner and skips terminal jobs. HTTP 409 guidance, bounded
503 recovery, tolerant XML parsing, HP JobInfo fallback, cancellation and retry
rules remain intact. Successful scan creation still reads Location without
consuming a response body. Document downloads keep their separate stream path.

Focused checks cover the four original failures, exact 1 MiB acceptance and
one-byte overflow for fixed, chunked and gzip job replies, unfinished error/job
bodies, cancellation, and immediate follow-up status using a single connection
slot. A 2 MiB document still streams intact. Small error responses retain their
readable charset-aware 200-character detail. All 69 scanner-client tests pass.

Validation: all 268 Python tests and 78 card tests pass (346 total), plus Ruff,
compileall, npm ci and diff whitespace checks. The patched client also reads
Idle status, capabilities and an existing terminal job from the actual HP.
No physical scan/print job was created and no scanner job was deleted. Oversize,
compression and interrupted-response checks ran only against local fixtures.
Released and installed as Scan 0.12.2 (Print stays 0.11.3):

- Source commit `9d0e9d66dcaeb76586b3bc1aa4d7fddb4ced4217`;
  [all hosted checks passed](https://github.com/wleonhardt/ha-escl-scan/actions/runs/38005319588).
- [Release workflow passed](https://github.com/wleonhardt/ha-escl-scan/actions/runs/38005442316)
  and published [v0.12.2](https://github.com/wleonhardt/ha-escl-scan/releases/tag/v0.12.2).
- Installed the tracked release files after backing up the existing component to
  `/config/.document-card-backups/before-control-limits-v0122-20261009.tar.gz`.
  Source/manifest/card hashes match the release; card content is unchanged.
- `ha core check` passed. Restarted with both job sensors idle; HA stays 2026.9.4.
  Both integrations load, both devices report reachable, scanner capabilities
  are fresh, and downloaded diagnostics report Scan 0.12.2.
- After refresh/restart, each native feature renders once. Latest scan
  `eb6a6af1b516` and recent print job 373 match the pre-restart records exactly.
  The retained scan downloads as HTTP 200, `application/pdf`, 152,766 bytes with
  a PDF header. A newer user scan appeared during release preparation, so the
  final idle baseline was refreshed before restarting. This task submitted no
  physical jobs and deleted none.

## Scanner storage safeguards — 2026-10-09

The user approved the proposed next task: reproduce oversized downloads,
low-space/write failures and interrupted scans, then add lean safeguards. Print
upload concurrency and scanner diagnostics remain separate proposals.

Five initial regressions failed against 0.12.2: over-budget bundled PDF,
separate-document batch and manual two-pass scan all completed; a zero-free-space
fixture still created a scanner job; and scratch cleanup skipped unlink when
close raised ENOSPC. The close test exercises the cleanup helper directly, not
an observed HP failure. A later fixture also showed an unusable storage path
could still create a job before the write failed. All faults are local fixtures;
no production disk was filled and no scanner fault was induced.

Use a fixed 1 GiB cumulative document budget per logical scan, retaining the
counter across both manual passes. Count each image's larger original/converted
size so compression cannot bypass the total. Each generated PDF is independently
bounded during writes (merge, conversion, back rotation and duplex interleave).
The limit leaves room for ordinary large color batches while bounding an endless
response. This is a document budget, not a claim that temporary disk use or PDF
parser memory stays below 1 GiB. Assembly can hold inputs and output together.

Keep 256 MiB of free-space headroom as a best-effort HA safeguard. Check in the
executor before each scanner job and before new files; recheck at most every
MiB of file growth, including generated output. Tiny PDF-object writes reuse
that check. Other writers can race a space check, so actual ENOSPC/EDQUOT still
produce an actionable failure. A canceled preflight cannot create a late job.
Copy destinations get a full-file free-space check before copying and a final
headroom check before atomic publication. A failed optional copy leaves the
completed private PDF available under the existing policy.

Explicitly close the download generator when writing fails or is canceled;
cleanup still unlinks scratch files when close raises. Storage-limit/full-disk
errors during requested back rotation fail the scan rather than publishing an
unrotated result as successful. Existing TTL, previous-result metadata, job
ownership/deletion, manual resume, scan settings and dependencies stay intact.
No runtime framework, additional configuration or automatic job retry is added.

Validation: 295 Python tests and 78 card tests pass (373 total), plus Ruff,
compileall, npm ci and diff checks. The 27 new cases cover the original gaps,
exact/one-byte-over boundaries, per-batch image expansion, generated-PDF bounds,
mid-download space loss, immediate stream closure, ENOSPC/EDQUOT in all writing
stages, explicit recovery, cancellation/shutdown/disconnection, manual back-pass
preflight and optional-copy failure. Previous result bytes/metadata remain
intact. Live storage has about 52 GiB available; no production fault was induced.
Released and installed as Scan 0.12.3 (Print stays 0.11.3):

- Source commit `a149eeb887cd2697011bea102f0a5dcdb85fc2c5`;
  [all hosted checks passed](https://github.com/wleonhardt/ha-escl-scan/actions/runs/38012885032).
- [Release workflow passed](https://github.com/wleonhardt/ha-escl-scan/actions/runs/38012969601)
  and published [v0.12.3](https://github.com/wleonhardt/ha-escl-scan/releases/tag/v0.12.3).
- Rollback archive:
  `/config/.document-card-backups/before-storage-v0123-20261009.tar.gz`.
  Installed tracked release files; coordinator/manifest/card hashes match.
  Card content is unchanged. HA configuration check passed before restart.
- Both job sensors were idle before restart. HA stays 2026.9.4; both integration
  entries load, both devices report reachable, and scanner capabilities are fresh.
  Downloaded diagnostics confirm Scan 0.12.3; each native card feature renders once.
- Latest scan `eb6a6af1b516` and recent print job 373 match the pre-restart records
  exactly after refresh/restart. The scan was already expired before installation
  and retains its original expiry/no download link. Available-result preservation
  is verified in isolated tests; this is not a claim of a fresh physical scan.
  No physical job or synthetic production disk failure was sent.
