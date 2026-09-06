// Lovelace card: one-tap "Scan now" against the escl_scan integration.
// Triggers a scan via /api/escl_scan/start and subscribes to
// sensor.printer_current_scan for live progress.
//
// Type:  custom:escl-scan-card
// Options:
//   title:   string, default "Scan now"
//   entity:  the scan sensor, default sensor.printer_current_scan (auto-
//            detected if that entity was renamed)

const TAG = 'escl-scan-card';

if (!customElements.get(TAG)) {
  customElements.define(TAG, class extends HTMLElement {});
}

const C = customElements.get(TAG);

C.prototype.setConfig = function (config) {
  this._config = Object.assign({ title: 'Scan now' }, config || {});
  this._render();
  // _render() no-ops after the first call, so apply title changes (e.g. the
  // dashboard editor's live preview) directly to the already-rendered node.
  if (this._titleEl) this._titleEl.textContent = this._config.title;
};

Object.defineProperty(C.prototype, 'hass', {
  set(hass) {
    this._hass = hass;
    // Lovelace pushes a fresh hass object on every state change. Drive all
    // progress rendering from here by diffing the scan sensor — no
    // subscribeEvents (which streamed every entity's changes to the browser
    // and raced the initial snapshot), and the card now also reflects scans
    // started from another device.
    this._onHass();
  },
  get() { return this._hass; },
  configurable: true,
});

C.prototype.getCardSize = function () { return 2; };

// Dashboard picker support: a default config and a visual editor built on
// HA's own <ha-form>, so the card is configurable without YAML.
C.getStubConfig = function () { return { title: 'Scan now' }; };
C.getConfigElement = function () { return document.createElement(TAG + '-editor'); };

const EDITOR_SCHEMA = [
  { name: 'title', selector: { text: {} } },
  { name: 'entity', selector: { entity: { domain: 'sensor', integration: 'escl_scan' } } },
];
const EDITOR_LABELS = { title: 'Title', entity: 'Scan sensor (optional)' };

if (!customElements.get(TAG + '-editor')) {
  customElements.define(TAG + '-editor', class extends HTMLElement {
    setConfig(config) { this._config = config || {}; this._render(); }
    set hass(hass) { this._hass = hass; if (this._form) this._form.hass = hass; }
    _render() {
      if (!this._form) {
        this._form = document.createElement('ha-form');
        this._form.schema = EDITOR_SCHEMA;
        this._form.computeLabel = (s) => EDITOR_LABELS[s.name] || s.name;
        this._form.addEventListener('value-changed', (ev) => {
          ev.stopPropagation();
          const value = Object.assign({}, this._config, ev.detail.value);
          if (!value.entity) delete value.entity;
          this._config = value;
          this.dispatchEvent(new CustomEvent('config-changed', {
            detail: { config: value }, bubbles: true, composed: true,
          }));
        });
        this.appendChild(this._form);
      }
      this._form.hass = this._hass;
      this._form.data = this._config;
    }
  });
}

C.prototype._render = function () {
  if (this._rendered) return;
  const root = this.attachShadow({ mode: 'open' });
  root.innerHTML = `
    <style>
      :host {
        display: block;
        /* Set up a size-based container so children can adapt to the
           card's own width — covers the case where a horizontal-stack
           shrinks each card narrow even on a wide viewport. */
        container-type: inline-size;
      }
      ha-card {
        padding: 18px 14px;
        border-radius: 18px;
        min-height: 130px;
        /* Tint from the active theme's accent; fall back to the original
           blue so themes without --rgb-primary-color look unchanged. */
        background: rgba(var(--rgb-primary-color, 147,197,253), 0.18);
        border: 1px solid rgba(var(--rgb-primary-color, 147,197,253), 0.55);
        display: flex; flex-direction: column;
        align-items: center; justify-content: center;
        gap: 6px;
        cursor: pointer;
        transition: transform .08s ease, background .15s ease;
        box-sizing: border-box;
      }
      ha-card:hover { background: rgba(var(--rgb-primary-color, 147,197,253), 0.26); }
      ha-card:active { transform: scale(.99); }
      ha-card.busy { cursor: progress; opacity: .85; }
      .icon { width: 36px; height: 36px; color: var(--primary-color, #93c5fd); flex-shrink: 0; }
      .title { font-weight: 700; font-size: 20px; color: var(--primary-text-color, #fff); line-height: 1.1; text-align: center; }
      .status {
        font-size: 13px;
        min-height: 16px;
        color: var(--secondary-text-color, rgba(255,255,255,0.75));
        text-align: center;
        padding: 0 4px;
        line-height: 1.3;
        word-break: break-word;
      }
      /* When the card itself is narrow (typically a phone, or a two-card
         horizontal-stack on a sidebar-split desktop), shrink the title
         and icon so multi-line status messages like "Scanning (platen)
         page 3…" don't push the cancel link off the card or collide
         with the title. Container query fires on the card's own width,
         not the viewport. */
      @container (max-width: 260px) {
        ha-card { padding: 14px 10px; gap: 4px; }
        .icon { width: 30px; height: 30px; }
        .title { font-size: 17px; }
        .status { font-size: 12px; }
      }
      @container (max-width: 200px) {
        .title { font-size: 15px; }
        .status { font-size: 11px; }
        .icon { width: 26px; height: 26px; }
      }
      .status.err { color: var(--error-color, #fca5a5); }
      .status.ok  { color: var(--success-color, #6ee7b7); }
      .status a   { color: inherit; text-decoration: underline; text-underline-offset: 2px; }
      .cancel {
        font-size: 11px;
        color: var(--error-color, #fca5a5);
        cursor: pointer;
        text-decoration: underline;
        text-underline-offset: 2px;
        margin-top: -4px;
        display: none;
      }
      .cancel.show { display: inline; }
      .cancel:hover { filter: brightness(1.15); }
    </style>
    <ha-card role="button" tabindex="0">
      <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor"
           stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <!-- Scanner glyph: flatbed + document peeking out -->
        <rect x="3" y="10" width="18" height="9" rx="1.5"/>
        <path d="M7 10V4h10v6"/>
        <line x1="7" y1="14.5" x2="17" y2="14.5"/>
      </svg>
      <div class="title"></div>
      <div class="status" aria-live="polite"></div>
      <div class="cancel" role="button" tabindex="0">Cancel</div>
    </ha-card>
  `;
  this._card = root.querySelector('ha-card');
  this._titleEl = root.querySelector('.title');
  this._statusEl = root.querySelector('.status');
  this._cancelEl = root.querySelector('.cancel');
  this._titleEl.textContent = this._config.title;

  this._card.addEventListener('click', (ev) => {
    if (ev.target === this._cancelEl) return;
    // Bail if the click landed on (or inside) any anchor — the "Open scan"
    // link lives in the .status div and bubbles up here.
    if (ev.target && typeof ev.target.closest === 'function' && ev.target.closest('a')) return;
    this._startScan();
  });
  this._card.addEventListener('keydown', (ev) => {
    if (ev.target === this._cancelEl) return;
    if (ev.target && typeof ev.target.closest === 'function' && ev.target.closest('a')) return;
    if (ev.key === 'Enter' || ev.key === ' ') {
      ev.preventDefault();
      this._startScan();
    }
  });
  this._cancelEl.addEventListener('click', (ev) => {
    ev.stopPropagation();
    this._cancelScan();
  });
  this._cancelEl.addEventListener('keydown', (ev) => {
    if (ev.key === 'Enter' || ev.key === ' ') {
      ev.preventDefault();
      ev.stopPropagation();
      this._cancelScan();
    }
  });
  this._rendered = true;
  // Reflect any scan already in progress (e.g. started from another device
  // before this card mounted).
  this._onHass();
};

// All API calls go through hass.fetchWithAuth, which injects the auth header
// and transparently refreshes an expired token (the old code dug the raw
// access_token out of hass.auth and 401'd on long-lived dashboard tabs once
// that token rotated). Falls back to a manual bearer only on frontends that
// somehow lack the helper.
C.prototype._apiFetch = function (path, init = {}) {
  const hass = this._hass;
  if (hass && typeof hass.fetchWithAuth === 'function') {
    return hass.fetchWithAuth(path, init);
  }
  const token =
    hass?.auth?.data?.access_token || hass?.auth?.accessToken || null;
  const headers = Object.assign({}, init.headers);
  if (token) headers.Authorization = `Bearer ${token}`;
  return fetch(path, Object.assign({ credentials: 'same-origin' }, init, { headers }));
};

C.prototype._setStatus = function (text, cls = '') {
  this._statusEl.textContent = '';
  if (text instanceof Node) this._statusEl.appendChild(text);
  else this._statusEl.textContent = text || '';
  this._statusEl.className = 'status' + (cls ? ' ' + cls : '');
};

C.prototype._setCancelVisible = function (visible) {
  this._cancelEl.classList.toggle('show', !!visible);
};

C.prototype._startScan = async function () {
  if (this._busy) return;
  this._busy = true;
  this._card.classList.add('busy');
  this._setStatus('Starting…');
  this._setCancelVisible(false);
  this._clearResultTimer();
  try {
    const resp = await this._apiFetch('/api/escl_scan/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{}',
    });
    let body = null;
    try { body = await resp.json(); } catch {}
    if (!resp.ok) {
      // 409 = a scan is already running (busy guard). Surface it plainly.
      const msg = (body && (body.message || body.error)) || `HTTP ${resp.status}`;
      throw new Error(msg);
    }
    this._activeScanId = body?.scan_id ?? null;
    const src = body?.source ? ` (${body.source.toLowerCase()})` : '';
    this._setStatus(`Scanning${src}…`);
    this._setCancelVisible(true);
    // From here on, the hass setter drives progress via _onHass().
  } catch (err) {
    this._setStatus('Scan failed: ' + (err?.message || err), 'err');
  } finally {
    this._busy = false;
    this._card.classList.remove('busy');
  }
};

C.prototype._cancelScan = async function () {
  if (!this._activeScanId) return;
  try {
    const r = await this._apiFetch('/api/escl_scan/cancel', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scan_id: this._activeScanId }),
    });
    if (!r.ok) {
      const body = await r.text();
      this._setStatus('Cancel failed: ' + body.slice(0, 80), 'err');
      return;
    }
    this._setStatus('Cancelling…');
  } catch (err) {
    this._setStatus('Cancel failed: ' + (err?.message || err), 'err');
  }
};

const SCAN_SENSOR = 'sensor.printer_current_scan';

// Resolve the scan sensor: explicit `entity:` config wins; otherwise the
// default id; otherwise find the (single) escl_scan sensor by its enum
// options so a user-renamed entity still works. Result is cached.
C.prototype._scanState = function () {
  const states = this._hass?.states;
  if (!states) return null;
  const id = this._config?.entity;
  if (id) return states[id] || null;
  if (states[SCAN_SENSOR]) return states[SCAN_SENSOR];
  if (this._sensorId && states[this._sensorId]) return states[this._sensorId];
  for (const [eid, st] of Object.entries(states)) {
    const a = st.attributes || {};
    if (eid.startsWith('sensor.') && 'scan_id' in a
        && Array.isArray(a.options) && a.options.includes('processing-stopped')) {
      this._sensorId = eid;
      return st;
    }
  }
  return null;
};

const TERMINAL_STATES = new Set(['completed', 'canceled', 'aborted', 'failed']);
const ACTIVE_STATES = new Set(['pending', 'processing', 'processing-stopped']);
// How long a finished result (esp. the "Open scan" link) stays on the card
// after the server drops the scan back to idle.
const RESULT_LATCH_MS = 30_000;

C.prototype._clearResultTimer = function () {
  if (this._resultTimer) {
    clearTimeout(this._resultTimer);
    this._resultTimer = null;
  }
};

// Called from the hass setter on every state push. Diffs the scan sensor and
// re-renders only when something meaningful changed.
C.prototype._onHass = function () {
  if (!this._rendered) return;
  const st = this._scanState();
  if (!st) return;
  const attrs = st.attributes || {};
  const state = st.state;
  const sid = attrs.scan_id ?? null;
  const sig = `${sid}|${state}|${attrs.pages_done || 0}`;
  if (sig === this._lastSig) return;
  this._lastSig = sig;

  if (ACTIVE_STATES.has(state)) {
    this._activeScanId = sid;
    this._clearResultTimer();
    this._renderScanState(state, attrs);
  } else if (TERMINAL_STATES.has(state)) {
    this._renderScanState(state, attrs);
    // Latch the result so the "Open scan" link stays clickable even after
    // the server drops `current` back to idle (~8s later).
    this._clearResultTimer();
    this._resultTimer = setTimeout(() => {
      this._resultTimer = null;
      this._lastSig = null;
      this._setStatus('');
      this._setCancelVisible(false);
    }, RESULT_LATCH_MS);
  } else if (!this._resultTimer && !this._busy) {
    // idle / unavailable — clear, unless a fresh result is still latched
    // or a local start is mid-flight.
    this._setStatus('');
    this._setCancelVisible(false);
  }
};

C.prototype._buildOpenLink = function (attrs) {
  const url = attrs?.file_url;
  if (!url) return null;
  const a = document.createElement('a');
  // href kept for accessibility / right-click, but the click handler does
  // the authenticated fetch — HA's view rejects plain navigation (no auth).
  a.href = url;
  a.target = '_blank';
  a.rel = 'noopener';
  a.textContent = 'Open scan';
  a.addEventListener('click', async (ev) => {
    ev.preventDefault();
    ev.stopPropagation();
    try {
      const resp = await this._apiFetch(url);
      if (!resp.ok) throw new Error('HTTP ' + resp.status);
      const blob = await resp.blob();
      const objUrl = URL.createObjectURL(blob);
      const w = window.open(objUrl, '_blank', 'noopener');
      if (!w) window.location.href = objUrl;
      setTimeout(() => URL.revokeObjectURL(objUrl), 60_000);
    } catch (err) {
      this._setStatus('Open failed: ' + (err?.message || err), 'err');
    }
  });
  return a;
};

C.prototype._renderScanState = function (state, attrs) {
  const pagesDone = attrs?.pages_done || 0;
  const source = attrs?.source ? attrs.source.toLowerCase() : '';
  if (state === 'pending') {
    this._setStatus('Waiting for scanner…');
    this._setCancelVisible(true);
  } else if (state === 'processing') {
    const src = source ? ` (${source})` : '';
    const pages = pagesDone > 0 ? ` page ${pagesDone}` : '';
    this._setStatus(`Scanning${src}${pages}…`);
    this._setCancelVisible(true);
  } else if (state === 'processing-stopped') {
    this._setStatus('Scanner paused — check tray/jam', 'err');
    this._setCancelVisible(true);
  } else if (state === 'completed') {
    const pages = pagesDone || 1;
    const link = this._buildOpenLink(attrs);
    const wrap = document.createElement('span');
    wrap.append(`Scan ready ✓ (${pages} page${pages > 1 ? 's' : ''}) — `);
    if (link) wrap.appendChild(link);
    this._setStatus(wrap, 'ok');
    this._setCancelVisible(false);
  } else if (state === 'canceled') {
    this._setStatus('Scan canceled', 'err');
    this._setCancelVisible(false);
  } else if (state === 'aborted' || state === 'failed') {
    const reason = attrs?.state_reasons || attrs?.error;
    this._setStatus('Scan failed' + (reason ? `: ${reason}` : ''), 'err');
    this._setCancelVisible(false);
  } else {
    this._setCancelVisible(false);
  }
};

window.customCards = window.customCards || [];
if (!window.customCards.find((c) => c.type === TAG)) {
  window.customCards.push({
    type: TAG,
    name: 'eSCL Scan',
    description: 'One-tap document scan via eSCL/AirScan with live status.',
    preview: true,
    documentationURL: 'https://github.com/wleonhardt/ha-escl-scan#adding-the-card-to-a-dashboard',
  });
}

// Self-healing for HA's whenDefined() race — Lovelace's card factory can
// render hui-error-card "Configuration error" placeholders before this
// script finishes loading, especially on slow reloads (Firefox / mobile)
// or when the dashboard mounts before the integration's static path is
// served. We re-scan for error cards on a staggered schedule AND keep a
// MutationObserver running so error cards that appear later (dashboard
// navigation, lazy view mount) also get healed.
const _ESCL_HEALED = new WeakSet();

function _esclHealOne(err) {
  if (_ESCL_HEALED.has(err)) return;
  // Lovelace wraps each card in a <hui-card> that holds the original
  // user-provided config on `_elementConfig`. The hui-error-card itself
  // has _config = {type: 'error', message: 'Custom element doesn\'t exist...'},
  // which is useless for healing. The parent is the source of truth.
  const parent = err.parentElement;
  let cfg = parent && parent._elementConfig;
  // Fallbacks for older HA layouts that may still hand the config to the
  // error card directly.
  if (!cfg) cfg = err._config || err.config;
  if (!cfg || cfg.type !== 'custom:' + TAG) {
    // Last resort: parse the missing-tag from the error message — handles
    // the case where _elementConfig isn't reachable. We can't reconstruct
    // user-provided fields (like `title`) without it, but we can at least
    // get a working default card so the dashboard isn't broken.
    const msg = err._config && err._config.message;
    if (typeof msg === 'string' && msg.indexOf(TAG) !== -1) {
      cfg = {type: 'custom:' + TAG};
    } else {
      return;
    }
  }
  _ESCL_HEALED.add(err);
  // If the parent hui-card already has a real instance of our element
  // (Lovelace's own whenDefined() callback may have inserted one alongside
  // the error card), just remove the error card sibling. Otherwise replace
  // the error card in place with a fresh instance.
  const existing = parent && parent.querySelector
    ? parent.querySelector(TAG)
    : null;
  if (existing) {
    err.remove();
    return;
  }
  const fresh = document.createElement(TAG);
  try {
    fresh.setConfig(cfg);
  } catch (e) {
    return;
  }
  err.replaceWith(fresh);
}

function _esclHeal() {
  const root = document.querySelector('home-assistant');
  if (!root) return;
  const stack = [root];
  while (stack.length) {
    const el = stack.pop();
    if (!el) continue;
    if (el.tagName === 'HUI-ERROR-CARD') _esclHealOne(el);
    if (el.shadowRoot) stack.push(el.shadowRoot);
    for (const c of (el.children || [])) stack.push(c);
  }
}

// Initial staggered retries — covers the common timing window.
[40, 120, 300, 700, 1500, 3000, 6000, 10_000].forEach(
  (ms) => setTimeout(_esclHeal, ms),
);

// Watch for hui-error-cards appearing after the initial retry window, then
// STOP. The pre-define race only exists until customElements.define (top of
// this module) runs; once defined, Lovelace constructs our card correctly.
// A permanent body-wide subtree observer would otherwise fire on every DOM
// mutation in the whole HA UI, on every page, for the life of the tab.
try {
  const observer = new MutationObserver((mutations) => {
    for (const m of mutations) {
      for (const n of m.addedNodes) {
        if (!n || n.nodeType !== 1) continue;
        if (n.tagName === 'HUI-ERROR-CARD') {
          _esclHealOne(n);
        } else if (n.querySelectorAll) {
          // querySelectorAll won't cross shadow roots, but most error
          // cards live in the light DOM under hui-card-element-editor or
          // similar parents that DO render them as direct children.
          n.querySelectorAll('hui-error-card').forEach(_esclHealOne);
        }
      }
    }
  });
  observer.observe(document.body, {childList: true, subtree: true});
  // The race window closes within seconds of load; disconnect once the
  // staggered sweeps above have all fired.
  setTimeout(() => observer.disconnect(), 12_000);
} catch {}
