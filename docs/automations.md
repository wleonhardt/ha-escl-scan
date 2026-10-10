# Actions, entities and events

[Documentation](README.md) · [HTTP API](api.md)

Use Home Assistant actions for automations; they do not require an access token.
The examples below use current automation YAML. Replace notification actions and
entity IDs with the ones on your installation.

## Start a scan

This action starts one-sided feeder scanning. `response_variable` receives the
initial scan record; it does not wait for the PDF to finish.

```yaml
action: escl_scan.start
data:
  source: Feeder
  dpi: 300
  color: gray
  duplex: false
  page_size: letter
response_variable: scan
```

| Field | Allowed value / behavior when omitted |
| --- | --- |
| `source` | `Platen` or `Feeder`; omitted selects loaded feeder, otherwise glass. |
| `dpi` | 50–1200; omitted uses the integration default. Adjusted to a supported DPI when known. |
| `color` | `color` or `gray`; omitted uses the integration default. |
| `duplex` | Boolean; omitted uses the integration default. Feeder only, automatic or manual. |
| `page_size` | `full` (default), `letter`, `a4`, or `custom`. |
| `width`, `height` | Required together for `custom`: positive integers, 1–60000, in **1/300-inch units**, within source limits. Do not send for other sizes. |

For example, Letter is 2550 × 3300 in these units. The card's custom-size dialog
uses millimeters instead. Both manual duplex passes use the accepted first-pass
settings.

## Resume backs or cancel

After a two-sided scan enters `awaiting-back-sides`, wait for the person to reload
the feeder before calling:

```yaml
action: escl_scan.scan_backs
data:
  reverse_back_order: true
```

Set `reverse_back_order: true` only when the last sheet will feed first. Omitted
or `false` means first sheet first. An optional `scan_id` selects a specific
waiting scan; otherwise the current scan is used. This action can also return a
scan record through `response_variable`.

Cancel the current scan:

```yaml
action: escl_scan.cancel
```

Or pass `data: {scan_id: "YOUR_SCAN_ID"}` to select it. Unlike the HTTP API,
actions may omit the ID. No target selector is needed: one scanner is supported.

## Notify when a PDF is ready

Paste this as one automation in the automation editor's YAML mode:

```yaml
alias: Notify when a scan is ready
triggers:
  - trigger: event
    event_type: escl_scan_completed
conditions:
  - condition: template
    value_template: "{{ trigger.event.data.state == 'completed' }}"
actions:
  - action: notify.mobile_app_phone
    data:
      message: "Scan ready: {{ trigger.event.data.pages_done }} page(s)"
      data:
        url: "{{ trigger.event.data.file_url }}"
mode: queued
```

The event also fires for unsuccessful outcomes, so keep the condition. The URL
is an authenticated Home Assistant endpoint, not a public PDF attachment;
opening it depends on the receiving client's authentication support. The card's
Download PDF action is the normal browser download path.

To archive every result, [copy to a folder](scanning.md#save-scans-to-a-folder)
is simpler than an automation. For scan-to-print, see the sister project's
[example](https://github.com/wleonhardt/ha-ipp-print/blob/main/docs/automations.md#print-a-completed-scan).

## Entities

| Entity | Purpose |
| --- | --- |
| **Current scan** (`sensor.printer_current_scan` unless renamed) | Active scan state and details. |
| **Scan now** (`button.<scanner>_scan_now`) | Starts a scan with integration defaults; usable in a standard Button or Tile card. |
| **Connection** (binary sensor on the device) | Whether eSCL is reachable, not whether paper is loaded or the device is ready. |

Current scan states: `idle`, `pending`, `processing`, `processing-stopped`,
`awaiting-back-sides`, `canceled`, `aborted`, `completed`, `failed`.

## Events and fields

| Event | When it fires |
| --- | --- |
| `escl_scan_state_changed` | An observed scan state change. |
| `escl_scan_completed` | A terminal transition: `completed`, `canceled`, `aborted` **or `failed`**. |

Both events carry the scan record in `event.data`. The Current scan sensor exposes
the same record while a scan is current, plus `latest_scan` and `device_connection`.

| Field | Meaning |
| --- | --- |
| `scan_id`, `state` | Scan identity and current outcome. |
| `source`, `dpi`, `requested_dpi`, `color`, `page_size` | Selected/effective scan settings. |
| `document_format` | Acquisition format returned by the scanner; final downloads are PDF. |
| `duplex`, `duplex_mode` | Whether both sides were requested; `simplex`, `automatic` or `manual`. |
| `scan_phase`, `front_pages`, `reverse_back_order` | Manual-pass phase, front count and selected back order. |
| `pages_done`, `bytes` | Progress; successful completion uses the assembled PDF page count. |
| `filename` | Generated PDF basename. |
| `submitted_at`, `finished_at` | ISO timestamps; finish time is null until terminal. |
| `state_reasons`, `error` | Device reason and integration error, when available. |
| `file_url`, `file_path` | Authenticated URL and local absolute path after successful completion. |
| `copied_to` | Published folder-copy path, or null when disabled/unsuccessful. |

`latest_scan` holds the latest successful scan's ID, basename, page count,
finish/expiry timestamps, availability and download URL while available. It
survives restart and is excluded from Recorder; it is separate from the current
job and is not included in these event payloads.

`device_connection` contains `state`, `checked_at`, `last_success_at` and
`next_check_at`. Reachability checks normally run every 60 seconds, back off to
five minutes on failure, and have a ten-second deadline. They do not start scans.
