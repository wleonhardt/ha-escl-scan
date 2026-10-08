# eSCL Scan for Home Assistant

[![HACS Default](https://img.shields.io/badge/HACS-Default-41BDF5.svg)](https://github.com/hacs/default)
[![GitHub release](https://img.shields.io/github/v/release/wleonhardt/ha-escl-scan)](https://github.com/wleonhardt/ha-escl-scan/releases)
[![validate](https://github.com/wleonhardt/ha-escl-scan/actions/workflows/validate.yml/badge.svg)](https://github.com/wleonhardt/ha-escl-scan/actions/workflows/validate.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

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
+ pages_done + source + timestamps), and
`escl_scan_state_changed` / `escl_scan_completed` events fire on the bus so
you can wire up automations (mobile notifications with the PDF attached,
auto-upload to Paperless, etc.).

## Features

- 📄 Direct eSCL submission — no SANE, no CUPS, no driver layer
- 🔍 Auto-discovered via mDNS (`_uscan`/`_uscans`) — shows up under *Discovered*
- 📚 Multi-page ADF batches merged into one PDF (per-page scanners included)
- 📐 Full-bed scan region and duplex from the device's own `ScannerCapabilities`
- 📊 Per-scan sensor (`sensor.printer_current_scan`) with live page progress
- 🔘 `button.<scanner>_scan_now` entity + `escl_scan.start` / `escl_scan.cancel` services for automations
- 🔔 Bus events for state changes and completion
- 🛑 Cancel-Job support
- 🎨 Lovelace card with one-tap scan and status display
- 🔒 Bearer-token authenticated file download endpoint
- ⚙️ Config flow — no YAML required
- 🔑 Works with the legacy ciphers some HP LaserJets ship with (opt-in)

## Requirements

- Home Assistant 2024.12 or newer (2026.3+ for the integration icon)
- A network scanner that supports eSCL / AirScan (most modern MFPs do)
- The scanner reachable from your HA host (typically port 443 or 80)

### Tested devices

| Device | Platen | ADF | Duplex | Notes |
|---|---|---|---|---|
| HP Color LaserJet MFP M283fdw | ✅ | ✅ | n/a (simplex ADF) | Discovered via mDNS; capabilities, DPI snap, cancel, copy-to-folder verified live on HA 2026.9.1 |

Works with yours? Open a [device report](https://github.com/wleonhardt/ha-escl-scan/issues/new?template=device_report.yml)
and it gets added here.

## Installation

### Via HACS (default store)

[![Open in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=wleonhardt&repository=ha-escl-scan&category=integration)

HACS → search **eSCL Scan** → Download → restart Home Assistant. No custom
repository needed.

### Manual

1. Copy `custom_components/escl_scan/` into your `<config>/custom_components/` directory
2. Restart Home Assistant

## Setup

Most eSCL scanners advertise themselves on the LAN, so the scanner usually
appears under **Settings → Devices & Services → Discovered**; press
*Configure*, confirm, done. Credentials and TLS settings can be adjusted
afterwards in the integration's options.

For manual setup: **Settings → Devices & Services → Add Integration → eSCL Scan**
and fill in:

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
response confirms the network/auth path works. It then reads
`ScannerCapabilities` (best-effort) for the model name, serial number, bed
size per source, duplex support, and the supported resolutions:

- the scan region is the full bed of the chosen source (A4, Letter, Legal
  ADF — whatever the device reports), so nothing gets cropped;
- a requested DPI snaps to the nearest supported resolution for the chosen
  source and simplex/duplex mode, when discrete resolutions are advertised;
- automatic duplex is only sent for Feeder scans on a duplex-capable ADF.
  A two-sided request on a simplex ADF, or when capabilities are unavailable,
  uses the manual workflow below.

Options (gear icon on the integration) hold the defaults: DPI, color mode,
duplex, rotating duplex back sides 180° (for ADFs that feed them reversed),
and file retention.

## Adding the card to a dashboard

The integration registers the card as a dashboard resource automatically — no
`resources:` block needed. It also injects the module globally as a fallback
for YAML resource configurations.

```yaml
type: custom:escl-scan-card
title: Scan now        # optional, defaults to "Scan now"
entity: sensor.printer_current_scan   # optional; auto-detected if renamed
```

Choose **Scan Duplex** for a two-sided feeder document. Automatic duplex
is used when advertised by the scanner. Otherwise, the card scans the fronts
and pauses with reload instructions. **Wait for the reload prompt before
flipping**; some scanners keep the first job open after sheets leave the
feeder and will consume any pages reloaded early into that same pass.
Reload with backs facing the scanner and
choose their feed order: **First sheet first** when keeping the same sheet
order, or **Last sheet first (flipped stack)** when flipping the whole stack
reverses its order. Then choose **Scan back sides**. The default is first sheet
first; the integration uses your selection rather than inferring page order.
The final PDF is ordered front 1, back 1, front 2, back 2, and so on.

Both passes must contain the same number of pages. A mismatch fails the scan
without publishing a partial document. You can cancel while waiting; the
reload window expires after 15 minutes. Fronts are held privately until the
backs succeed. A scanner failure during automatic duplex is reported as a
failure; it is not silently retried after sheets have already been consumed.

Automations can watch for `awaiting-back-sides`, then call
`escl_scan.scan_backs` after the user reloads the backs. Optional `scan_id`
selects the waiting scan; omitted `scan_id` uses the current scan. Set
`reverse_back_order: true` when the last sheet feeds first (default `false`).

## Services and button

For automations, use the services instead of the REST API (no token needed):

```yaml
# Scan the ADF in grayscale, both sides, and grab the resulting scan_id
action: escl_scan.start
data:
  source: Feeder      # optional: Platen | Feeder (auto-detected if omitted)
  dpi: 300            # optional, snaps to a supported resolution
  color: gray         # optional: color | gray
  duplex: true        # optional, Feeder: automatic duplex or manual fallback
response_variable: scan

# Cancel the current scan (or pass scan_id: ...)
action: escl_scan.cancel
```

`escl_scan.start` returns the same dict the sensor exposes as attributes
(`scan_id`, `source`, `dpi`, `state`, …). A `button.<scanner>_scan_now`
entity is created too, so a stock *Tile* or *Button* card works without the
custom card.

### Example: notify with the PDF when a scan completes

```yaml
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
```

## Sensor + events

`sensor.printer_current_scan`

| Field | Value |
|---|---|
| state | `idle` / `pending` / `processing` / `processing-stopped` / `awaiting-back-sides` / `canceled` / `aborted` / `completed` / `failed` |
| attributes.scan_id | Internal scan id (matches the file endpoint) |
| attributes.filename | Auto-generated filename (e.g. `scan-20260524-153012-adf.pdf`) |
| attributes.pages_done | Pages pulled from the scanner so far (final PDF page count on completion) |
| attributes.source | `Platen` or `Feeder` |
| attributes.duplex | `true` when both sides were requested (Feeder + duplex ADF only) |
| attributes.duplex_mode | `simplex`, `automatic`, or `manual` |
| attributes.scan_phase | Manual workflow: `fronts`, `waiting-for-backs`, or `backs` |
| attributes.front_pages | Validated front-side page count in a manual scan |
| attributes.reverse_back_order | Whether the manual back-side pass was loaded last sheet first |
| attributes.state_reasons | The scanner's eSCL `JobStateReasons` |
| attributes.submitted_at / finished_at | ISO timestamps |
| attributes.file_url | Download URL once complete (`/api/escl_scan/file/{id}`) |
| attributes.file_path | Absolute path of the stored PDF once complete (for `shell_command`, Paperless uploads, …) |
| attributes.copied_to | Path of the copy made by *copy to folder*, if enabled |

Bus events you can trigger automations from:

- `escl_scan_state_changed` — every observed state change
- `escl_scan_completed` — once per terminal transition (completed / canceled / aborted)

Both carry the full scan dict as `event.data`.

## REST API

The integration registers four HA HTTP views (all `requires_auth = true`):

### `POST /api/escl_scan/start`

Optional JSON body to override defaults: `{"dpi": 600, "color": "gray", "source": "Feeder", "duplex": true}`. Returns:

```json
{"ok": true, "scan_id": "abc123", "source": "Feeder", "dpi": 600, "color": "gray", "duplex": true, "state": "pending"}
```

Returns `409` if a scan is already running — the scanner is single-job
hardware, so starts are serialized.

### `POST /api/escl_scan/cancel`

JSON body `{"scan_id": "abc123"}`. Returns `{"ok": true}` on success.

### `POST /api/escl_scan/scan_backs`

JSON body `{"scan_id": "abc123", "reverse_back_order": false}`. The optional
boolean `reverse_back_order` defaults to `false`; use `true` if backs feed last
sheet first. Resumes a scan in `awaiting-back-sides`
after confirming the scanner is idle and its feeder has paper. Returns `409`
for a stale/duplicate request or an empty/busy feeder, leaving a waiting scan
available for retry. The start response includes `duplex_mode` and `scan_phase`.

### `GET /api/escl_scan/file/{scan_id}`

Streams the PDF. Returns `409` while the scan is incomplete, and `404` for a
missing or TTL-purged scan.

## Scan to folder (Paperless-ngx etc.)

Options → *Also copy finished scans to this folder*. Every completed scan is
copied there (written under a temp name and renamed, so folder watchers never
see a half-written file). Point it at a Paperless-ngx consume directory and
scans become documents with no automation at all. The folder must be listed
in `configuration.yaml`:

```yaml
homeassistant:
  allowlist_external_dirs:
    - /media/paperless/consume
```

Copies are never purged by the retention TTL. Only successful batches are
published. Cancellation is accepted until folder publication begins; after that,
a folder consumer may already have ingested the file.

## Troubleshooting

- **Download diagnostics** (device page → ⋮ → *Download diagnostics*) and
  attach it to bug reports: it contains the parsed `ScannerCapabilities`,
  the current/tracked scans, and redacted entry data.
- **Debug logging:**
  ```yaml
  logger:
    logs:
      custom_components.escl_scan: debug
  ```
- **`SSLV3_ALERT_HANDSHAKE_FAILURE`** → enable *Allow legacy cipher suites*.
- **Scan fails with "truncated PDF"** → the DPI/colour combination isn't
  supported; with capabilities available the DPI snaps automatically, so
  try a different colour mode.
- **"scanner busy"** → another client (phone, PC) has an active job; wait
  or cancel it on the device.
- **Card shows "Configuration error" briefly on a slow reload** → expected,
  the card self-heals within a few seconds.

## Caveats

- **Incomplete batches fail.** A truncated page, corrupt PDF, interrupted
  transfer, or exhausted retry budget fails the scan; an incomplete batch is
  never labeled successful or copied to a watched folder.
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
├── button.py          # button.<scanner>_scan_now
├── config_flow.py     # user + zeroconf flows, options flow
├── coordinator.py     # scan lifecycle driver, copy-to-folder, file retention
├── const.py
├── diagnostics.py
├── manifest.json
├── scanner.py         # eSCL wire format + client (capabilities, jobs, streaming)
├── sensor.py          # sensor.printer_current_scan
├── services.py        # escl_scan.start / escl_scan.cancel
├── services.yaml
├── static/card.js     # the Lovelace card + its visual editor
├── brand/             # integration icon (HA 2026.3+ inline brands)
├── strings.json, icons.json
└── translations/en.json
```

### Tests

```
python3 -m venv .venv && .venv/bin/pip install -r requirements-test.txt
.venv/bin/pytest -q            # parsers, scanner client, coordinator, flows, services, views
.venv/bin/ruff check custom_components tests
npm ci && npm run test:card       # jsdom tests for the card
```

Releases: bump `version` in `manifest.json`, add a CHANGELOG section, push a
`vX.Y.Z` tag — the release workflow publishes the GitHub release from the
CHANGELOG entry (HACS only installs releases).

Pull requests welcome.

## License

MIT
