# AGENTS.md — ha-escl-scan

Agent operations file. Read before working.

## Instruction priority
1. User instructions in chat
2. This file
3. `plans/` docs (check `plans/decisions/` before structural changes)

## Project overview
HACS custom integration for Home Assistant: trigger document scans on eSCL/AirScan
network scanners. Python backend (`custom_components/escl_scan/`) + vanilla-JS
Lovelace card (`static/card.js`). No build step, no dependencies beyond HA core
(aiohttp comes from HA). Sister project: ipp_print (shares patterns).

## Non-negotiable rules
- `pytest -q` and `ruff check custom_components tests` must pass before done.
- CI must stay green: hassfest, HACS validation, ruff, pytest (`.github/workflows/validate.yml`).
- card.js is plain ES module, no framework, no build — keep it that way.
- All scanner I/O is async (aiohttp); never block the event loop (file I/O via
  `hass.async_add_executor_job`). Never mutate coordinator state from executor threads.
- Match existing style; tolerant XML parsing (local tag names, not namespace-strict)
  is deliberate — vendors differ.
- Project knowledge belongs in `plans/`, not agent memory.
- Never delete another client's scanner job: the 503 purge only runs when ScannerStatus is Idle.
- Anything that touches the network in setup/flows must be patchable in tests (HA blocks sockets).
- Commit after each meaningful change (only when user asked for commits).

## Before-done checklist
- [ ] `pytest -q` + `ruff check` pass
- [ ] version bumped in `manifest.json` if user-facing change; CHANGELOG.md entry added
- [ ] README/examples updated if config surface changed
- [ ] release: push tag `vX.Y.Z` (release workflow publishes the GitHub release; HACS installs releases only)
- [ ] no `__pycache__`/`.pyc` staged

## Key commands
- Setup: `python3 -m venv .venv && .venv/bin/pip install -r requirements-test.txt ruff`
- Tests: `.venv/bin/pytest -q`
- Lint: `.venv/bin/ruff check custom_components tests`

## Workspace structure
- `custom_components/escl_scan/` — integration
  - `__init__.py` — setup, HTTP views (start/cancel/file), card URL registration
  - `scanner.py` — eSCL HTTP client + XML parsing (status, capabilities, jobs, streaming)
  - `coordinator.py` — scan lifecycle driver, state machine, copy-to-folder, file retention
  - `sensor.py` / `button.py` — `sensor.printer_current_scan`, `button.*_scan_now`
  - `services.py` + `services.yaml` — `escl_scan.start` / `escl_scan.cancel`
  - `config_flow.py` — user + zeroconf flows, options flow
  - `diagnostics.py`, `icons.json`, `brand/` (inline icon, HA 2026.3+)
  - `static/card.js` — Lovelace card + visual editor (served content-hashed)
- `plans/` — plans, decisions, open questions
- `examples/` — dashboard YAML snippets

## Context recovery
1. Read this file, then `plans/next-up.md` and latest plan doc in `plans/`.
2. `git log --oneline -10` for recent direction.
3. Key invariants: views resolve coordinator via `hass.data` per request;
   card URL is content-hashed for cache busting; heal code in card.js works
   around Lovelace whenDefined race.
