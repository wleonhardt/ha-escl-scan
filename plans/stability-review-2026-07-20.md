# Stability / bug / performance review — 2026-07-20

Status: queued (review done, fixes not started)
Scope: full read of integration + card. Findings ranked. Line refs against HEAD `9607012`.

---

## P1 — Real bugs (fix first)

### 1.1 Concurrent scan start can kill an in-flight scan
`coordinator.py:166` `start_scan()` has no busy guard. Card clears its `_busy`
flag as soon as the start POST returns (`card.js:199-202`), so a second tap
mid-scan is easy. Second `create_job` typically gets 503 from the device →
`scanner.py:306-309` responds by **purging all active jobs** — including the
first scan's job. First scan then dies mid-pull with a confusing error.

Fix (both layers):
- Coordinator: reject `start_scan` when `self._current` exists and not terminal
  → view returns 409; card shows "scan already running".
- `create_job` purge path: never delete the job URL of a scan this coordinator
  is currently driving (pass known-active URLs in, or drop auto-purge and let
  the guard make it unreachable in normal flow).

### 1.2 No task cleanup on unload/reload — orphaned drivers
`__init__.py:122-126` unload pops `hass.data` but never touches
`coordinator._driver_tasks` / poll loops / `_terminal_hold` tasks
(`coordinator.py:134,193,243,364`). Options-flow save triggers
`async_reload` (`__init__.py:129-131`), so a reload during an active scan
leaves the old driver running: polls old client with old creds, writes files,
fires bus events, calls `_notify` on a dead listener list. On HA shutdown,
`finally` at `coordinator.py:364` even spawns a *new* task
(`_terminal_hold`) → "Task was destroyed but it is pending" warnings.

Fix: add `ScanCoordinator.async_shutdown()` — cancel driver, poll, and hold
tasks, await them, close client session (see 2.1). Call from
`async_unload_entry`. In `_drive_scan`'s `finally`, skip `_terminal_hold`
spawn when task is being cancelled; track hold tasks so they're cancellable.

### 1.3 Executor thread mutates coordinator state
`coordinator.py:192` runs `_ensure_storage_and_purge` in an executor;
`_purge_expired_files` (`coordinator.py:446-461`) then mutates
`self._scans.pop()` from that thread while the event loop freely reads/writes
the same dict. Violates HA's threading model; GIL makes corruption unlikely
but stale-read/lost-update races are real (e.g. purge pops a scan the loop is
about to mark terminal).

Fix: executor does file I/O only, returns the set of deleted paths; dict
cleanup happens back on the loop.

### 1.4 Whole PDF buffered in RAM — twice
`scanner.py:360` `resp.read()` + `coordinator.py:241` `bytearray` +
`coordinator.py:305` `bytes(buffer)` copy. A 600-DPI color ADF batch is
easily hundreds of MB → memory spike ×2–3 inside the HA process; on a Pi
this can OOM the whole instance.

Fix: stream `resp.content.iter_chunked()` to a temp file in the storage dir;
validate `%PDF-` prefix and `%%EOF` tail by reading first/last KB of the
file; rename into place on success, delete on failure. Bonus: fixes 1.4b —
`ClientTimeout(total=120)` at `scanner.py:211` also caps slow-but-healthy
transfers; switch pull to `sock_connect`/`sock_read` timeouts instead of
total.

---

## P2 — Stability & performance

### 2.1 New ClientSession + TCPConnector + SSLContext per request
`scanner.py:250-255` builds a fresh session (and `scanner.py:169-183` a fresh
`SSLContext` incl. `load_default_certs()` — disk reads) for **every** call.
Poll loop does this every 1.5 s; `pull_next_document` re-creates the session
per retry attempt (`scanner.py:347-361`). Cost: TLS handshake per request, FD
churn, CA-bundle reads.

Fix: build SSL context once in `__init__`; hold one lazily-created
`ClientSession` per client; `close()` from coordinator shutdown (1.2).

### 2.2 Card subscribes to ALL state_changed events
`card.js:328-350` `subscribeEvents(..., 'state_changed')` streams every
entity change in the whole instance to the browser for up to 180 s per scan,
filtering client-side. On busy instances that's a firehose. Also has a race:
state can go terminal between the `hass.states` snapshot (`card.js:322-326`)
and subscribe completing → status stuck "Scanning…" until the 180 s safety.

Fix: drop the subscription entirely. Lovelace pushes a fresh `hass` object to
the card on every state change — render from the `hass` setter
(`card.js:22-25`) by diffing `hass.states['sensor.printer_current_scan']`.
Simpler, no race, no firehose. Also fixes: card currently shows nothing when
a scan was started from another device/card, since tracking only begins on
local tap (`_activeScanId`, `card.js:190`).

### 2.3 Raw access-token digging breaks on refresh
`card.js:148-158` reads `hass.auth.data.access_token` (internal API).
Long-lived dashboard tabs: token refresh timing can hand you an expired
token → 401 on start/cancel/file fetch with no retry.

Fix: use `hass.fetchWithAuth()` / `hass.callApi()` — they refresh and retry.

### 2.4 Heal machinery runs forever, everywhere
`card.js:440-463`: 8 staggered full-DOM walks (crossing shadow roots) plus a
permanent body-level `MutationObserver` with `subtree: true` — fires on every
DOM change in the HA UI for the lifetime of the tab, on every HA page
(`add_extra_js_url` loads the card on settings pages too). The
hui-error-card race window closes once `customElements.define` runs (top of
script), so error cards can only pre-exist the module — late ones can't
happen except across dashboard navigations that re-use pre-define renders.

Fix: keep the staggered sweeps; disconnect the observer after ~30 s or after
first successful heal sweep finds zero error cards twice in a row.

### 2.5 Double card-load mechanism + stale URLs
Two registration paths at once: `add_extra_js_url` (`__init__.py:113`) and
lovelace resource sync (`__init__.py:134-170`). Issues:
- Resource sync touches private internals (`hass.data['lovelace']`) — shape
  already changed once (dict → object; code handles both, next change breaks it).
- Concurrent entry reloads race: two sync tasks can both see
  `current_id is None` → duplicate resource entries.
- After card.js update changes the hash, old extra_js_url entries persist for
  the HA session and 404 in the console.
- 60×1 s poll loop per setup when lovelace is slow/YAML-mode.

Fix: pick ONE mechanism. `add_extra_js_url` is the integration-sanctioned
path and needs no lovelace internals; keep it, delete the resource sync (and
its 60 s poll). If keeping sync anyway (belt-and-braces for YAML dashboards),
add an asyncio.Lock and dedupe check.

---

## P3 — Correctness edges

- **3.1 Multi-entry broken by design**: views pick an arbitrary coordinator
  (`__init__.py:173-185`) and sensor hardcodes
  `entity_id = "sensor.printer_current_scan"` (`sensor.py:52`) — second entry
  collides. Either add `"single_config_entry": true` to `manifest.json`
  (honest about the limitation) or route views by entry/host and drop the
  hardcoded entity_id.
- **3.2 Stale title on reconfigure**: `card.js:29-30` `_render` early-returns
  once rendered; later `setConfig` with new `title` never applied (editor
  live-preview shows stale). Update `_titleEl.textContent` on every
  `setConfig`.
- **3.3 Options can change host, unique_id stays stale**
  (`config_flow.py:57-60` vs options flow) — duplicate detection wrong after
  host edit. Update unique_id on host change or make host immutable in
  options (reconfigure flow is the modern answer).
- **3.4 Unvalidated option ranges**: options flow (`config_flow.py:114-116`)
  accepts any int — `default_dpi: 0` / negative `file_ttl_seconds` (purges
  everything instantly, TrackedScans dropped while completing). Add
  `vol.Range`; use password selector for `CONF_PASSWORD`
  (`config_flow.py:111`) instead of plain text.
- **3.5 Completed page count can undercount**: final JobInfo check
  (`coordinator.py:334-343`) reads state but ignores `pages_completed`;
  single-document scanners report pages only server-side, and the poll loop
  may be cancelled before the last update. Take
  `max(pages_done, info.pages_completed)` there.
- **3.6 TTL purge only on next scan start** (`coordinator.py:192`): with rare
  scans, files outlive TTL by days. Add `async_track_time_interval` purge
  (every ~15 min), cancelled on unload.
- **3.7 `hass.data[DOMAIN]` never emptied** after last entry unload
  (`_views_registered`, `_card_urls_registered` persist) — harmless today,
  but purge on last-entry unload keeps reload semantics clean.

## P4 — Hygiene

- **4.1 Zero tests.** Highest-leverage additions, in order:
  1. Parser unit tests (`parse_scanner_status`, `parse_job_info`) with vendor
     XML fixtures (HP/Canon/Epson variants, wrapper-vs-leaf JobStateReasons).
  2. Coordinator lifecycle with a fake client: happy path, cancel mid-scan,
     truncated PDF, non-PDF body, 503-purge path, unload-during-scan (catches
     1.1/1.2 regressions).
  3. View tests: auth required, input validation, 404/409 precedence.
  4. Config-flow tests.
  Tooling: `pytest-homeassistant-custom-component`, wire into validate.yml.
- **4.2 Lint/type CI**: add ruff + mypy jobs (py-compile job catches almost
  nothing).
- **4.3 manifest.json**: add `"integration_type": "device"`, decide 3.1's
  `single_config_entry`, add `"loggers": ["escl_scan"]`.
- **4.4 Style nits**: function-level `import asyncio`
  (`scanner.py:345`, `__init__.py:139`) → module top; unused `_LOGGER` in
  sensor.py; `_attr_device_class = "enum"` → `SensorDeviceClass.ENUM`; add
  `device_info` so sensor groups under a device.
- **4.5 Card theming**: hardcoded rgba blues/reds (`card.js:45,57,85-86`)
  ignore light themes — poor contrast. Map to HA theme vars with fallbacks.

## Suggested execution order

1. Phase 1 (P1, one PR): busy-guard + purge scoping, coordinator shutdown +
   unload wiring, executor-safety split, streaming PDF write. Test manually
   against real scanner (start/cancel/reload-mid-scan/big ADF batch).
2. Phase 2 (P2, one PR): session reuse + SSL cache, card `hass`-setter
   rendering + fetchWithAuth, heal observer bounds, single card-load
   mechanism. Version bump; verify card update propagates (hash change).
3. Phase 3 (P3): small independent fixes, cherry-pick order free.
4. Phase 4 (P4): test suite + CI hardening; then P1 regression tests lock in.

Non-goals (explicitly fine as-is): tolerant local-name XML parsing, broad
exception catches around device I/O (vendor quirk armor, keep), verify_tls
default False (LAN self-signed reality, documented), SECLEVEL=0 opt-in.
