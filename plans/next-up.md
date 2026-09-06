# Next up

## Queue
- HACS store icon: shows once hacs/frontend#937 (brands-proxy support) ships;
  nothing to do on our side.
- Live-test v0.4.0 against the real printer: zeroconf discovery, capabilities
  parse (attach XML to a device report), duplex, copy-to-folder.

## Backlog / nice-to-have
- Image-mode (JPEG) scans converted to PDF (needs Pillow/img2pdf).
- Reconfigure flow for host/creds (options flow currently edits them).
- Card: localisation of status strings.
- Community forum thread + device compatibility reports.

## Done
- 2026-09-06 — v0.4.0 work: capabilities (bed size, duplex, DPI snap, device
  info, serial unique_id), zeroconf, services + button, copy-to-folder,
  diagnostics, card editor, purge scoping, NextDocument retry, view tests.
  See `plans/decisions/2026-09-06-capabilities-and-brands.md`.
- 2026-09-06 — v0.3.0 finally pushed + released (was 7 commits unpushed);
  CHANGELOG, release workflow, issue templates, dependabot.
- 2026-07-20 — stability review + phased fixes (P1–P4) landed, v0.2.0. See `stability-review-2026-07-20.md`.
- 2026-07-20 — test suite (37 tests) + ruff wired into CI.
