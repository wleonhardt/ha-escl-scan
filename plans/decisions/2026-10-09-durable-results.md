# Phase 6: latest scan and bounded print activity

Status: accepted for implementation. Existing job states, file URLs and primary
actions remain compatible. Independent integrations, plain JS and no new runtime
dependencies. This is not a document archive or scan-history expansion.

## Scan

Persist one latest successfully completed scan per config entry in a version-1
HA Store. Keep only ID, generated basename, page count, completion time and a
fixed expiry. Never infer success by listing PDFs on disk: abandoned jobs may
leave complete-looking files. Only the existing final successful transition
can publish metadata; manual fronts, partial, failed and canceled scans cannot.
Old retained files remain untouched but cannot be adopted without proof of
completion. No migration reconstructs results from orphan files.

Restore metadata without restoring an active job or firing completion events.
Reconcile the record with a regular, non-symlink file inside the private scan
directory, and use the earlier of saved expiry and current file-mtime + TTL.
Restart and file modification cannot reset its saved deadline. The existing
purge still owns file cleanup. Download checks enforce expiry even between
sweeps and while a different scan is active. Keep an expired/missing metadata
record until the next success so the UI can explain an unavailable result.
Copies in a configured external folder remain outside this retention policy.

Expose compact `latest_scan` metadata on the existing sensor; exclude that
attribute from Recorder. Existing authenticated file URLs can resolve this
one restored record, with the same login requirement as current downloads.
No direct disk path is accepted from the client or loaded metadata.

## Print

Persist at most ten records per config entry for seven days from submission in
a separate version-1 HA Store. Save sanitized filename, job ID, submission and
known finish times, outcome and reported page/sheet counts; never document
bytes, credentials, local source paths or settings. Identical printer job IDs
are distinguished by submission time and entry. Keep a minimal pending record
so restart can label an interrupted tracking session as outcome unknown.
Restoring records never resumes polling, cancels or replays a device job, or
emits a fresh completion event. Completion means the printer reported success.

Expose terminal records through `recent_activity` on the existing sensor,
excluded from Recorder. Prune on load, changes and an hourly timer. Expired
records are filtered from snapshots even between sweeps. Delete the metadata
Store when its integration entry is removed. Scan's Store follows the same
entry-removal rule; older integration versions simply ignore these new keys.

## Cards

Use the same collapsed disclosure below the normal actions: Latest scan / Recent
activity. Show localized dates, outcome/counts and explicit expired/missing
guidance. The scan result offers authenticated Download PDF while retained,
including when the scanner itself is offline. The fresh-completion primary CTA
keeps its current acknowledge-on-download behavior; history does not create a
new completion toast or take over Scan after every reload. No reprint button.
Keep visible Two-sided, native/standalone support, and device isolation. Old
backends without metadata omit the disclosure. Bound and validate metadata at
the frontend boundary; render text safely. Downloads cannot alter a newer job's
status or leak a result after a card target changes or disconnects.

Verify restart, idle hold, expiry/purge, missing files, invalid storage, private
manual fronts, cancellation, multiple printer entries/reused IDs, stale downloads,
non-admin authentication, mixed versions, keyboard and mobile layout. Hardware
protocols are unchanged; fixtures can prove persistence without another print.

## Paired layout follow-up

Use one built-in Vertical stack per card in side-by-side layouts. Auto rows
allow details to grow but do not prevent the shorter neighbour stretching.
Put Sections sizing on each stack. The [live validation](../card-independent-expansion-2026-10-09.md)
covers Tile, Mushroom and standalone hosts with asymmetric disclosure states.
