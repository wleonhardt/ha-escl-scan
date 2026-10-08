# Phase 2 capability and upload contract

Status: accepted and implemented. Schema version 1; independent local modules.

Expose authenticated GET /api/{escl_scan,ipp_print}/capabilities with optional
entity_id. Resolve the integration's sensor through the entity registry on each
request; a missing target is allowed only with one loaded device. Unknown or
foreign targets return 404, ambiguous targets 400, unloaded integrations 503.
No admin-only service is required. Return no addresses, credentials or raw XML/IPP.

Use a backend cache per loaded device: fetch at setup and on demand after a
15-minute success TTL; retry failures after five minutes. Serialize refreshes,
bound them to 15 seconds, retain the last success as stale, and drain on unload.
No periodic polling or sensor/recorder capability churn. Expose fetched_at,
attempted_at, fresh/stale/unknown, a generic error and retry timing. Null means
unknown; an empty supported list means known but no integration-supported choices.
Unknown data does not assert that hardware lacks a feature or is online.

Snapshots include schema_version, domain, resolved entity_id, compact identity,
supported settings, request_options and integration limits/defaults. Scan
profiles keep Platen, Feeder simplex and FeederDuplex resolutions/colors separate.
Manual duplex depends on a known feeder; automatic duplex on advertised support.
Missing per-source lists stay unknown rather than borrowing another source's list.
Only scalar strings and bounded lists are published.

Print accepts optional copies and sides multipart fields in any order, alongside
file/entity_id. Metadata remains capped at 512 bytes per field; document limit
stays 50 MiB. Reject duplicate/unknown fields. Copies accept only an integer or
ASCII decimal integer string, 1–99; booleans/floats/signs/whitespace are invalid.
The service and upload share validation, advertised device limits and submission.
Omitted options retain printer defaults. Explicit sides always require a fresh
per-job default-paper read; a failed read submits nothing and observes backoff.
No accepted/ambiguous job is retried automatically.

The additive response advertises the backend's accepted request fields. Phase 3
must check this metadata and leave options unavailable on an older backend.
No additional settings UI ships in Phase 2. Existing card modules remain unchanged.
