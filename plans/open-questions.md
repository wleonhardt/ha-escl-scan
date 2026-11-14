# Open questions

## Open
- How should job URLs from HP scanners on the advertised port 8080 be handled?
  The HP returns `Location` with an explicit `:80`, so discovery-created entries
  fail with "job URL outside its origin", and the accepted job is left running.
  Candidate: keep only the `Location` path and resolve it against our own
  origin, so requests never leave the configured scanner. Evidence:
  [v0.12.7 live test](v0127-live-test-2026-11-14.md).
- Is the real printer bundle- or per-page-mode for ADF? (Logs "merged N documents"
  on per-page devices.) Determines which merge path gets exercised live.

## Resolved
- Multi-scanner support → `single_config_entry: true` (2026-07-20).
- Card load mechanism → `add_extra_js_url` only; resource sync reaped (2026-07-20).
- pypdf dependency → accepted, pure Python (2026-07-20, v0.3.0).
- Brands submission → not needed; inline `brand/` folder since HA 2026.3 (2026-09-06).
- HACS default listing → already listed in `hacs/default` `integration` (verified 2026-09-06).
- Storage location (`.storage` vs elsewhere) → stays; backups include either (2026-09-06).
