# HTTP API

[Documentation](README.md) · [Home Assistant actions and events](automations.md)

Use actions for Home Assistant automations. These endpoints are for external
clients and dashboard implementations. All require Home Assistant authentication;
ordinary authenticated users can call them. Examples below show paths relative
to your Home Assistant URL.

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/escl_scan/capabilities` | Read supported settings. |
| POST | `/api/escl_scan/start` | Start one scan. |
| POST | `/api/escl_scan/scan_backs` | Resume a waiting manual duplex scan. |
| POST | `/api/escl_scan/cancel` | Cancel an active scan. |
| GET | `/api/escl_scan/file/{scan_id}` | Download a completed PDF. |

Start, backs and cancel accept an optional `entity_id` for the scan sensor.
Invalid/unloaded explicit targets return 404; omitted targets use the single
configured scanner. An unconfigured integration returns 503.

## Read capabilities

`GET /api/escl_scan/capabilities?entity_id=sensor.printer_current_scan`

The target is optional with the single scanner. Schema version 1 includes:

- `entity_id`, bounded model `identity`, and `schema_version`.
- `supported.sources`, `supported.automatic_duplex`, `supported.manual_duplex`,
  and per-source `Platen`, `Feeder`, `FeederDuplex` profiles.
- Profile colors, formats, resolutions, regions and supported combinations.
- `request_options`, integration `limits` and cache freshness fields.

Check `schema_version` and `request_options` before exposing controls. `null`
means unreported; an empty supported list means no integration-supported choices
were advertised. Do not infer feeder capabilities from glass capabilities.

The cache refreshes on demand after 15 minutes, shares concurrent refreshes,
and backs off failed reads for five minutes. Fetches have a 15-second deadline.
`status` is `fresh`, `stale` (previous success retained), or `unknown`.
`fetched_at`, `attempted_at`, `refresh_after_seconds` and the generic
`refresh_failed` error describe the cache, not current device reachability.
Malformed queries return 400; unknown targets 404; an unloaded integration 503.

## Start

`POST /api/escl_scan/start` with an optional JSON object:

```json
{"source":"Feeder","dpi":300,"color":"gray","duplex":true,"page_size":"letter"}
```

Fields and dimension units match the [start action](automations.md#start-a-scan).
Omitted values use integration defaults; source is selected automatically.
Example response:

```json
{"ok":true,"scan_id":"abc123def456","source":"Feeder","dpi":300,"color":"gray","duplex":true,"duplex_mode":"manual","scan_phase":"fronts","state":"pending"}
```

The response starts the workflow; it does not mean a PDF is ready. Follow the
sensor/events for progress. A conflicting scan returns 409; invalid settings
400; device/start failure 502. Do not automatically repeat a start after a lost
response: the first request may already have started scanning.

## Resume back sides

`POST /api/escl_scan/scan_backs`:

```json
{"scan_id":"abc123def456","reverse_back_order":true}
```

`scan_id` is required here, unlike the Home Assistant action.
`reverse_back_order` defaults to false. Use true if the last sheet feeds first.
The scanner must be idle with paper detected, and the scan must be waiting for
backs. A stale request or empty/busy feeder returns 409; a scanner check failure
returns 502. A rejected resume leaves the waiting scan available to retry.
Success returns `ok`, `scan_id` and `state`.

## Cancel

`POST /api/escl_scan/cancel`:

```json
{"scan_id":"abc123def456"}
```

The ID is required. Success returns `{"ok":true,"scan_id":"abc123def456"}`.
Unknown scans return 404; terminal scans or scans already publishing a folder
copy return 409. Cancellation does not remove documents already consumed by a
folder watcher.

## Download

`GET /api/escl_scan/file/{scan_id}` streams `application/pdf` with a generated
filename and `Cache-Control: private, no-store`. Authentication is required;
the URL is not a public sharing link.

A known scan that is not successfully complete returns 409. Unknown, expired or
missing files return 404. The latest retained successful PDF remains available
after a restart. See [retention](scanning.md#download-and-retention).

## Client notes

Use `Authorization: Bearer <token>` for an external client. Keep the token out
of URLs, shared examples and logs. Error bodies contain a human-readable
`message`; check HTTP status rather than matching message wording. A frontend
should recover current state after reconnecting, never replay a start blindly.
The detailed cache contract is in the maintainer
[capability decision](../plans/decisions/2026-10-08-capability-api.md).
