# eSCL Scan

Trigger document scans directly from Home Assistant on any eSCL/AirScan-capable
network scanner. Per-job sensor, bus events, and a companion Lovelace card.

- `sensor.printer_current_scan` mirrors the scanner-side job state in real time
  (pending → processing → completed/aborted/canceled) with `pages_done`,
  `pages_total`, `source` (ADF/Platen), and timestamps as attributes.
- Bus events: `escl_scan_state_changed` and `escl_scan_completed`.
- `POST /api/escl_scan/start` triggers a scan, returns the scan_id immediately.
- `POST /api/escl_scan/cancel` cancels by scan_id.
- `GET /api/escl_scan/file/{scan_id}` downloads the resulting PDF (bearer auth).

After install: **Settings → Devices & Services → Add Integration → eSCL Scan**.

See README for the full configuration and example dashboard card.
