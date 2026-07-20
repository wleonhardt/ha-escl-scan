# eSCL Scan for Home Assistant

A Home Assistant custom integration that triggers document scans on any
eSCL/AirScan-capable network scanner and surfaces **per-job state** through
a sensor — including live page progress for ADF batches, completion,
cancellation, and the scanner's own error reasons.

Ships with a companion Lovelace card so a "Scan now" tile on your dashboard
is a single tap.

> 💡 **Sister project:** for printing PDFs to the same multifunction
> printers, see [**ha-ipp-print**](https://github.com/wleonhardt/ha-ipp-print)
> — same architecture (per-job sensor + Lovelace card + bus events) targeting
> IPP/IPPS instead of eSCL.

<p align="center">
  <img src="assets/card-idle.png" width="320" alt="Idle card" />
  <img src="assets/card-scanning.png" width="320" alt="Scanning card" />
  <br/>
  <img src="assets/card-complete.png" width="320" alt="Complete card" />
  <img src="assets/card-failed.png" width="320" alt="Failed card" />
</p>

## Why this exists

Home Assistant's built-in printer integrations (`brother`, `ipp`, the various
HACS HP/Epson components) are all **read-only** — they poll device status
sensors but cannot trigger scans. The only existing HACS scan-trigger
integration is Brother-DCP-1610W-specific and produces a single JPEG via
WSD SOAP. Nothing in the ecosystem targets eSCL, even though eSCL is the
vendor-neutral standard that nearly every modern multifunction device
supports (HP, Canon, Epson, modern Brother, Kyocera, Xerox, …).

`escl_scan` talks eSCL directly:

- `ScannerStatus` to probe and detect ADF vs Platen source
- `ScanJobs` (POST) to create a job with a `ScanSettings` envelope
- `ScanJobs/{uuid}/NextDocument` (GET) to pull each page as the scanner produces it
- `ScanJobs/{uuid}` (DELETE) to cancel

Job state flows into `sensor.printer_current_scan` (state + filename
+ pages_done + pages_total + source + timestamps), and
`escl_scan_state_changed` / `escl_scan_completed` events fire on the bus so
you can wire up automations (mobile notifications with the PDF attached,
auto-upload to Paperless, etc.).

## Features

- 📄 Direct eSCL submission — no SANE, no CUPS, no driver layer
- 📚 Multi-page ADF batches merged into one PDF (per-page scanners included)
- 📊 Per-scan sensor (`sensor.printer_current_scan`) with live page progress
- 🔔 Bus events for state changes and completion
- 🛑 Cancel-Job support
- 🎨 Lovelace card with one-tap scan and status display
- 🔒 Bearer-token authenticated file download endpoint
- ⚙️ Config flow — no YAML required
- 🔑 Works with the legacy ciphers some HP LaserJets ship with (opt-in)

## Requirements

- Home Assistant 2024.8 or newer
- A network scanner that supports eSCL / AirScan (most modern MFPs do)
- The scanner reachable from your HA host (typically port 443 or 80)

## Installation

### Via HACS (custom repository)

1. HACS → Integrations → ⋮ → Custom repositories
2. Add `https://github.com/wleonhardt/ha-escl-scan` as type **Integration**
3. Install **eSCL Scan**
4. Restart Home Assistant

### Manual

1. Copy `custom_components/escl_scan/` into your `<config>/custom_components/` directory
2. Restart Home Assistant

## Setup

**Settings → Devices & Services → Add Integration → eSCL Scan**

Fill in:

| Field | Notes |
|---|---|
| Hostname or IP | e.g. `scanner.local` or `192.168.1.50` |
| Port | `443` for HTTPS (default), `80` for HTTP |
| Use TLS | On for HTTPS |
| User | Only required if scanner uses basic auth |
| Password | Only required if scanner uses basic auth |
| Verify TLS | Off for self-signed certs (most consumer scanners) |
| Allow legacy cipher suites | Enable if you see `SSLV3_ALERT_HANDSHAKE_FAILURE` in the logs |

The flow does a quick eSCL `ScannerStatus` probe before saving — any 200
response confirms the network/auth path works.

## Adding the card to a dashboard

The integration registers the card globally — no `resources:` block needed.

```yaml
type: custom:escl-scan-card
title: Scan now        # optional, defaults to "Scan now"
```

## Sensor + events

`sensor.printer_current_scan`

| Field | Value |
|---|---|
| state | `idle` / `pending` / `processing` / `processing-stopped` / `canceled` / `aborted` / `completed` / `failed` |
| attributes.scan_id | Internal scan id (matches the file endpoint) |
| attributes.filename | Auto-generated filename (e.g. `scan-20260524-153012-adf.pdf`) |
| attributes.pages_done | Pages pulled from the scanner so far |
| attributes.pages_total | Total pages, if the scanner reports it (ADF only) |
| attributes.source | `Platen` or `Feeder` |
| attributes.state_reasons | The scanner's eSCL `JobStateReasons` |
| attributes.submitted_at / finished_at | ISO timestamps |
| attributes.file_url | Download URL once complete (`/api/escl_scan/file/{id}`) |

Bus events you can trigger automations from:

- `escl_scan_state_changed` — every observed state change
- `escl_scan_completed` — once per terminal transition (completed / canceled / aborted)

Both carry the full scan dict as `event.data`.

## REST API

The integration registers three HA HTTP views (all `requires_auth = true`):

### `POST /api/escl_scan/start`

Optional JSON body to override defaults: `{"dpi": 600, "color": "gray", "source": "Feeder"}`. Returns:

```json
{"ok": true, "scan_id": "abc123", "source": "Feeder", "dpi": 600, "color": "gray", "state": "pending"}
```

Returns `409` if a scan is already running — the scanner is single-job
hardware, so starts are serialized.

### `POST /api/escl_scan/cancel`

JSON body `{"scan_id": "abc123"}`. Returns `{"ok": true}` on success.

### `GET /api/escl_scan/file/{scan_id}`

Streams the PDF. Returns 404 if the scan isn't complete yet or has been
TTL-purged.

## Caveats

- **No OCR.** Scans land as image-mode PDFs. Pair with Paperless-ngx or an
  OCR-capable bus-event listener for searchable text.
- **1h TTL on stored PDFs** by default (configurable in options; a periodic
  sweep purges expired files even when no new scan runs).
- **One scanner, one scan at a time.** The integration allows a single config
  entry, and a start request while a scan is in progress is rejected (`409`)
  rather than clobbering the running job.
- **HP LaserJets**: some models only offer non-PFS TLS ciphers. Enable
  "Allow legacy cipher suites" in the config flow.

## Development

```
custom_components/escl_scan/
├── __init__.py        # entry setup, HTTP views, card registration
├── config_flow.py     # UI flow + options flow
├── coordinator.py     # scan lifecycle driver + file retention
├── const.py
├── manifest.json
├── scanner.py         # eSCL wire format + client
├── sensor.py          # sensor.printer_current_scan
├── static/card.js     # the Lovelace card
├── strings.json
└── translations/en.json
```

### Tests

```
pip install -r requirements-test.txt
pytest -q            # parser, coordinator lifecycle, scanner, config-flow tests
ruff check custom_components tests
```

Pull requests welcome.

## License

MIT
