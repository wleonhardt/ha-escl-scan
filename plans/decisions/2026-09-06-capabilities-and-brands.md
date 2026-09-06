# 2026-09-06 — ScannerCapabilities as source of truth; inline brand icons

## Decisions
- **Scan region comes from `ScannerCapabilities`** (per-source MaxWidth/MaxHeight).
  Fallback `DEFAULT_REGION = (2550, 3508)` (Letter width, A4 height) when the
  endpoint is missing. Rationale: scanners clamp oversize regions down but never
  grow one; the old Letter-height default cropped A4.
- **DPI snaps to nearest supported discrete resolution** instead of failing with
  a truncated-PDF error. Logged at info.
- **Duplex only for Feeder on a duplex-capable ADF**; silently downgraded otherwise
  (attribute `duplex` reflects what was sent).
- **unique_id = serial number, else UUID, else host:port** for new entries.
  Existing entries keep host:port (no migration; single_config_entry makes
  collisions impossible anyway).
- **Brand icon ships inline** in `custom_components/escl_scan/brand/` (HA 2026.3+
  brands proxy). `home-assistant/brands` auto-closes custom-integration PRs, so
  no upstream submission. HACS store icon depends on hacs/frontend#937.
- **503 on ScanJobs**: purge listed jobs only when the device reports Idle.
  A Processing device belongs to someone else; raise "scanner busy".
- **NextDocument 500/503**: consult JobInfo; retry while the job is alive,
  bounded by `NEXT_DOCUMENT_RETRY_SECONDS` (120 s).
- **Scan storage stays in `.storage/escl_scan`.** Moving it buys nothing: HA
  backups include the whole config dir either way. Copy-to-folder covers the
  "I want the file elsewhere" need.
- **Services registered in `async_setup`** (domain-level, resolve coordinator per
  call) — consistent with the HTTP views, works with single_config_entry.
