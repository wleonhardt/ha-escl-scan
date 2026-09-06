# Open questions

## Open
- Is the real printer bundle- or per-page-mode for ADF? (Logs "merged N documents"
  on per-page devices.) Determines which merge path gets exercised live.

## Resolved
- Multi-scanner support → `single_config_entry: true` (2026-07-20).
- Card load mechanism → `add_extra_js_url` only; resource sync reaped (2026-07-20).
- pypdf dependency → accepted, pure Python (2026-07-20, v0.3.0).
- Brands submission → not needed; inline `brand/` folder since HA 2026.3 (2026-09-06).
- Storage location (`.storage` vs elsewhere) → stays; backups include either (2026-09-06).
