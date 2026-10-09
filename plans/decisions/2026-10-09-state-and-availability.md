# Phase 4: tracked state, recovery and checked connection

Status: implementing. Preserve the visible Two-sided layout selected by the user.

Print follows HA's pushed job sensor from first mount, including external service
jobs and other cards; remove the redundant per-card entity subscription. Scope
tracking and async replies to sensor, job ID, submitted time and a request
sequence. Freeze the active device during a job. Keep local staged files private
and never submit automatically during reconnect. Completion uses a bounded
acknowledgement; unknown outcomes do not claim success or invite blind retries.
Scan retains its separate two-pass state machine and gains equivalent stale
response/disconnection guards. Existing protocol values and API clients remain
compatible. Print counters distinguish impressions from sheets.

Add one backend connection monitor per integration entry. It performs only a
small read-only status query, never creates, cancels or purges jobs. One request
at a time, a 10-second deadline, checks every 60 seconds when healthy, exponential
failure backoff capped at five minutes. Stop/drain it before closing the client
on unload. Setup/flows remain patchable in tests; initial probe runs in the
background after entity setup so an offline device never blocks installation.

Expose reachable/unreachable/unknown with last-check and last-success timestamps
in a compact job-sensor attribute and a native connectivity binary sensor (unknown
before the first check). Preserve job state independently: idle says nothing about
connection. Failed probes mean this integration could not reach the protocol;
absence/stale evidence is unknown. Cards show connection trouble separately from
job outcomes and disable device actions while HA itself is disconnected. Use the
new printer connectivity entity to replace the dashboard's legacy offline summary.

Vendor proven common presentation/localization/options helpers inline, with a
canonical plain-JS source and a checked synchronization script. Keep a single
content-hashed runtime asset and early custom-element registration; no build,
framework, cross-integration runtime dependency, or new global element name.

Verify pushed external jobs, reload/reconnect, identical job IDs on two printers,
late response bodies, target changes, completion/zero/unknown counters, offline
backoff/unload, old API payloads, duplicate-resource cleanup and both cards in HA.
Do not print or scan merely to test UI state; use isolated browser fixtures and
read-only live device status unless a physical job is needed and explicitly queued.
