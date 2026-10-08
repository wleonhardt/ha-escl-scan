# Code review — 2026-10-08

Scope: integration, eSCL client/parsers, scan lifecycle, HTTP views, services,
configuration flows, entities, diagnostics, Lovelace card/editor, tests, and
validation/release workflows. Reviewed from clean HEAD `d9e474e`.

Status: concrete defects patched locally; version prepared as **0.4.6**.
No commit, push, release, or physical scanner job was requested/performed.

## Highest-priority findings fixed

1. **Cancellation could revive a scan.** Cancel during `create_job` marked the
   scan canceled, but a late Location response overwrote its state with
   processing. Cancellation now wins; the response is retained solely to delete
   our own job. An in-flight POST during shutdown is also allowed to resolve
   before cleanup, bounded by the client's existing request timeout.
2. **Cancellation could wait on a stalled document for 900 seconds.** It relied
   on DELETE changing the next download response. It now interrupts the local
   driver after the job URL is known. Terminal state is set before any await,
   preventing completion from beating cancellation while DELETE is pending.
3. **A new start could race previous cleanup.** A terminal current scan did not
   mean its driver had finished writing/deleting. Driver tasks now reserve the
   scanner until cleanup finishes, including pending canceled jobs.
4. **Cancellation leaked scratch files/descriptors and raced executor writes.**
   `CancelledError` bypassed the document-stream cleanup; canceled awaits did
   not stop worker threads. File operations are shielded and awaited before
   cleanup, writers close in `finally`, and interrupted outputs are removed.
5. **Periodic retention could delete a newly started scan's scratch files.**
   Checking idle before awaiting an executor was insufficient. Retention and
   startup cleanup now share a lock; shutdown tracks/waits for purge workers so
   an old coordinator cannot delete files from a reloaded coordinator.
6. **Incomplete batches were reported as success.** Network/read/write/open
   errors after a valid first page, or a truncated later part, previously
   silently produced fewer pages. Such batches now fail explicitly. Exhausting
   the NextDocument retry deadline raises an error rather than signaling EOF.
7. **Malformed PDFs passed the single-document path.** Header/EOF markers alone
   were sufficient even if page-tree parsing failed. Single and merged documents
   must now contain a readable, nonempty page tree. pypdf retains its tolerant
   default parsing rather than imposing strict PDF conformance.
8. **Aborted scans could be delivered to Paperless or another watched folder.**
   Copying occurred before the final JobInfo check. Publication now follows
   validation/final device-state checking, and failed/aborted outputs are not
   published. Publication is a commit point: cancellation is rejected once a
   consumer could receive the file. Failed copies remove their temporary files.
9. **Home Assistant stop/setup failures leaked resources.** Unload was handled,
   but normal HA shutdown had no coordinator stop hook, and a later setup
   exception could leave a client/coordinator behind. Both now clean up.
10. **Untrusted job URLs/redirects could escape the scanner origin.** Absolute
    Location/JobUri values were used with a session carrying Basic Auth. URLs
    must now remain under the scanner's ScanJobs endpoint; redirects may remain
    within its origin but cannot move to another origin or supply credentials.
    A two-server regression verifies the external server receives no request.

Primary code: `coordinator.py`, `scanner.py`, and `__init__.py`; corresponding
tests exercise real loopback HTTP servers, controlled async races, and blocked
executor workers.

## Other correctness fixes

- **Wrong port/invalid IPv6:** HTTP port 443 and HTTPS port 80 were silently
  discarded; raw IPv6 hosts lacked brackets. Origins now use yarl URL building.
  NextDocument path construction also preserves job query parameters.
- **DPI chosen from another source:** the capabilities parser pooled flatbed,
  simplex, and duplex resolutions. Snapping now uses the selected source/mode;
  absent source-specific discrete values do not borrow another source's list.
  Invalid dimensions and non-square/negative discrete resolutions are ignored.
- **Paused/aborted jobs hidden:** polling updated counters/reasons but never
  changed processing to processing-stopped. Pause/resume is now reflected and
  emits state events; device cancel/abort interrupts stalled streaming.
- **XML edge cases:** whitespace-only reason wrappers now fall back to child
  text; JobUri extraction uses parsed XML, trimming whitespace, decoding escaped
  characters, and deduplicating URIs; `Cancelled` is terminal throughout.
- **Diagnostic privacy:** serial/UUID identifiers, copy destination, output
  paths, and exception text are redacted in addition to entry credentials.
- **HTTP validation:** malformed/non-object start JSON no longer triggers a
  default scan; boolean DPI is rejected; DPI bounds match services/options.
  Empty-body starts remain supported. File existence checks run off-loop.
- **Card response races:** late start/cancel responses cannot overwrite an
  earlier terminal sensor update. Repeated start/cancel taps are guarded;
  malformed successful start responses produce an error.
- **Card stale display:** meaningful attributes and entity identity participate
  in deduplication; changing the selected sensor refreshes immediately; missing
  sensors clear stale cancel controls. Healed cards receive current hass state.
- **PDF preview behavior:** the tab is reserved synchronously during the click,
  before authentication/download awaits; its opener is cleared. Blocked/closed
  tabs fall back to a download. Authenticated links are limited to the
  integration's file endpoint.
- **Duplex rotation:** cloning the document preserves metadata; file-size
  checking stays in the executor.

## Simplification/performance changes

- Streaming errors propagate to one driver failure path instead of being
  silently salvaged; the driver owns successful-stream scratch cleanup.
- Page counting/merging/rotation use file handles, avoiding pypdf's redundant
  whole-input byte buffers. Merge inputs close after import, limiting open files.
- Unavailable capabilities probes back off for five minutes, then retry, so an
  unsupported endpoint is not probed on every scan and a transient failure can
  still recover.
- Card test windows close after each test. The suite no longer waits for the
  60-second object-URL timer; expanded tests finish in under a second locally.

## Remaining improvements, in priority order

These require additional design or compatibility evidence; they are not claims
that the patched paths are broken.

1. **Bound large PDF merges/rotation.** File handles remove redundant input
   copies, but pypdf's writer still holds cloned objects/image streams. Stress
   test realistic 600-DPI ADF batches on Pi-class memory before choosing a size
   limit, bounded merge strategy, or external worker. An executor prevents event
   loop blocking, not process-wide memory pressure.
2. **Model complete capability setting profiles.** Source-specific discrete DPI
   is now respected, but color/DPI combinations, resolution ranges, document
   formats, and referenced profiles are not negotiated. Add real vendor fixtures
   before selecting compatible combinations or introducing image-to-PDF fallback.
3. **Avoid whole-file browser blobs for large downloads.** A short-lived HA
   signed download URL could let the browser stream directly. Verify the auth
   API against the minimum supported frontend and mobile browsers first.
4. **Add supported-version coverage.** Current tests use the pinned modern HA
   stack, while HACS declares HA 2024.12 and pypdf has a broad minimum. Add a
   minimum-version smoke job or deliberately raise/pin the supported floor.
5. **Use a reconfigure flow for connection changes.** Options currently alter
   host/credentials without a probe or identity reconciliation. The single-entry
   restriction limits collision risk, but a proper reconfigure flow would make
   validation and serial/UUID identity behavior explicit.
6. **Separate PDF/storage helpers from lifecycle code when extending it.** The
   coordinator remains large. A focused PDF/storage module would improve review
   boundaries; introducing a generic state-machine framework would add more
   complexity than the current single-job hardware needs.
7. **Localization/accessibility follow-up.** Move card status text into a small
   localization layer; evaluate nested interactive elements and busy/disabled
   semantics with keyboard and screen-reader testing. Preserve the vanilla ES
   module and no-build deployment model.

## Decisions and validation limits

- Incomplete batches now fail instead of salvaging valid pages. This supersedes
  the truncated-part salvage behavior in `issue-1-multidoc-concat.md`; README,
  changelog, and regression expectations reflect the new integrity contract.
- Tolerant local-name XML parsing, shared async network sessions, content-hashed
  card URLs, source-region selection, and Idle-only 503 purging are preserved.
- No new runtime dependency or build step was introduced (yarl comes with HA's
  aiohttp stack). No existing scanner's jobs were touched.
- Run the required Python tests/lint and card tests before delivery. Hosted
  hassfest/HACS checks and physical-device validation require their own run.
- Live validation should cover cancel during cold job creation/download,
  pause/abort, a large duplex ADF batch, metadata/rotation, and folder consumers.

## Local validation

- `pytest -q`: **132 passed** (baseline: 89).
- `ruff check custom_components tests`: **passed**.
- `npm ci`: completed; audit reported zero vulnerabilities.
- `npm run test:card`: **20 passed** (baseline: 12), including syntax check.
- Python compilation, JSON/workflow syntax, and `git diff --check`: **passed**.
- No files staged; no bytecode artifacts staged; changes remain uncommitted.
- Hosted hassfest/HACS validation, minimum-version testing, and live scanner
  testing were **not run**; no release/tag was pushed.
