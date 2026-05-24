// Lovelace card: one-tap "Scan now" against the escl_scan integration.
// Triggers a scan via /api/escl_scan/start and subscribes to
// sensor.printer_current_scan for live progress.
//
// Type:  custom:escl-scan-card
// Options:
//   title:  string, default "Scan now"

const TAG = 'escl-scan-card';

if (!customElements.get(TAG)) {
  customElements.define(TAG, class extends HTMLElement {});
}

const C = customElements.get(TAG);

C.prototype.setConfig = function (config) {
  this._config = Object.assign({ title: 'Scan now' }, config || {});
  this._render();
};

Object.defineProperty(C.prototype, 'hass', {
  set(hass) { this._hass = hass; },
  configurable: true,
});

C.prototype.getCardSize = function () { return 2; };

C.prototype._render = function () {
  if (this._rendered) return;
  const root = this.attachShadow({ mode: 'open' });
  root.innerHTML = `
    <style>
      :host { display: block; }
      ha-card {
        padding: 22px 18px;
        border-radius: 18px;
        height: 130px;
        background: rgba(96,165,250,0.18);
        border: 1px solid rgba(96,165,250,0.55);
        display: flex; flex-direction: column;
        align-items: center; justify-content: center;
        gap: 8px;
        cursor: pointer;
        transition: transform .08s ease, background .15s ease;
        box-sizing: border-box;
      }
      ha-card:hover { background: rgba(96,165,250,0.26); }
      ha-card:active { transform: scale(.99); }
      ha-card.busy { cursor: progress; opacity: .85; }
      .icon { width: 36px; height: 36px; color: #93c5fd; flex-shrink: 0; }
      .title { font-weight: 700; font-size: 20px; color: var(--primary-text-color, #fff); line-height: 1; }
      .status { font-size: 13px; min-height: 16px; color: var(--secondary-text-color, rgba(255,255,255,0.75)); text-align: center; padding: 0 8px; }
      .status.err { color: #fca5a5; }
      .status.ok  { color: #6ee7b7; }
      .status a   { color: inherit; text-decoration: underline; text-underline-offset: 2px; }
      .cancel {
        font-size: 11px;
        color: #fca5a5;
        cursor: pointer;
        text-decoration: underline;
        text-underline-offset: 2px;
        margin-top: -4px;
        display: none;
      }
      .cancel.show { display: inline; }
      .cancel:hover { color: #fecaca; }
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
    this._startScan();
  });
  this._card.addEventListener('keydown', (ev) => {
    if (ev.target === this._cancelEl) return;
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
};

C.prototype._authHeaders = function (json = false) {
  const token =
    this._hass?.auth?.data?.access_token ||
    this._hass?.connection?.auth?.data?.access_token ||
    this._hass?.auth?.accessToken ||
    null;
  const h = {};
  if (json) h['Content-Type'] = 'application/json';
  if (token) h.Authorization = `Bearer ${token}`;
  return h;
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
  try {
    const resp = await fetch('/api/escl_scan/start', {
      method: 'POST',
      headers: this._authHeaders(true),
      body: '{}',
      credentials: 'same-origin',
    });
    let body = null;
    try { body = await resp.json(); } catch {}
    if (!resp.ok) {
      const msg = (body && (body.message || body.error)) || `HTTP ${resp.status}`;
      throw new Error(msg);
    }
    this._activeScanId = body?.scan_id ?? null;
    const src = body?.source ? ` (${body.source.toLowerCase()})` : '';
    this._setStatus(`Scanning${src}…`);
    this._setCancelVisible(true);
    this._trackScanProgress().catch((e) => {
      console.warn('[escl-scan] progress tracking error', e);
    });
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
    const r = await fetch('/api/escl_scan/cancel', {
      method: 'POST',
      headers: this._authHeaders(true),
      body: JSON.stringify({ scan_id: this._activeScanId }),
      credentials: 'same-origin',
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
const TERMINAL_STATES = new Set(['completed', 'canceled', 'aborted', 'failed']);
const ACTIVE_STATES = new Set(['pending', 'processing', 'processing-stopped']);

C.prototype._trackScanProgress = async function () {
  const hass = this._hass;
  if (!hass || !hass.connection) return;

  if (this._unsubProgress) {
    try { this._unsubProgress(); } catch {}
    this._unsubProgress = null;
  }
  clearTimeout(this._progressSafety);

  const ourScanId = this._activeScanId;
  let sawState = null;

  const renderLink = (attrs) => {
    const url = attrs?.file_url;
    if (!url) return null;
    const a = document.createElement('a');
    a.href = url;
    a.target = '_blank';
    a.rel = 'noopener';
    a.textContent = 'Open scan';
    return a;
  };

  const render = (state, attrs) => {
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
      const link = renderLink(attrs);
      const wrap = document.createElement('span');
      wrap.append(
        `Scan ready ✓ (${pages} page${pages > 1 ? 's' : ''}) — `
      );
      if (link) wrap.appendChild(link);
      this._setStatus(wrap, 'ok');
      this._setCancelVisible(false);
    } else if (state === 'canceled') {
      this._setStatus('Scan canceled', 'err');
      this._setCancelVisible(false);
    } else if (state === 'aborted' || state === 'failed') {
      const reason = attrs?.state_reasons || attrs?.error;
      this._setStatus(
        'Scan failed' + (reason ? `: ${reason}` : ''),
        'err',
      );
      this._setCancelVisible(false);
    } else {
      this._setCancelVisible(false);
    }
  };

  // Push initial render — sensor may already have moved past pending.
  const initial = hass.states[SCAN_SENSOR];
  if (initial && initial.attributes?.scan_id === ourScanId) {
    sawState = initial.state;
    render(initial.state, initial.attributes);
  }

  this._unsubProgress = await hass.connection.subscribeEvents((ev) => {
    if (ev?.data?.entity_id !== SCAN_SENSOR) return;
    const newState = ev.data.new_state;
    if (!newState) return;
    const attrs = newState.attributes || {};
    const sid = attrs.scan_id;
    if (sid != null && sid !== ourScanId) return;
    sawState = newState.state;
    render(newState.state, attrs);
    if (TERMINAL_STATES.has(newState.state)) {
      clearTimeout(this._progressSafety);
      // Leave the result up longer than the print card's 10s — users want
      // time to tap the "Open scan" link before it disappears.
      this._progressSafety = setTimeout(() => {
        if (this._statusEl?.textContent &&
            !ACTIVE_STATES.has(sawState)) {
          this._setStatus('');
        }
      }, 30_000);
      try { this._unsubProgress(); } catch {}
      this._unsubProgress = null;
    }
  }, 'state_changed');

  this._progressSafety = setTimeout(() => {
    if (this._unsubProgress) {
      try { this._unsubProgress(); } catch {}
      this._unsubProgress = null;
    }
    if (!sawState) {
      this._setStatus('Scan started (no further updates)', 'ok');
    }
  }, 180_000);  // scans can take a while for big ADF batches
};

window.customCards = window.customCards || [];
if (!window.customCards.find((c) => c.type === TAG)) {
  window.customCards.push({
    type: TAG,
    name: 'eSCL Scan',
    description: 'One-tap document scan via eSCL/AirScan with live status.',
    preview: false,
  });
}

// Self-healing for HA's whenDefined() race — see ipp_print card.js for context.
function _esclHeal() {
  const root = document.querySelector('home-assistant');
  if (!root) return;
  const stack = [root];
  const errors = [];
  while (stack.length) {
    const el = stack.pop();
    if (!el) continue;
    if (el.tagName === 'HUI-ERROR-CARD') errors.push(el);
    if (el.shadowRoot) stack.push(el.shadowRoot);
    for (const c of (el.children || [])) stack.push(c);
  }
  for (const err of errors) {
    const cfg = err._config || err.config;
    if (!cfg || cfg.type !== 'custom:' + TAG) continue;
    const fresh = document.createElement(TAG);
    fresh.setConfig(cfg);
    err.replaceWith(fresh);
  }
}
[60, 250, 800, 2000, 5000].forEach((ms) => setTimeout(_esclHeal, ms));
