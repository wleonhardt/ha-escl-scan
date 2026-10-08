// Lovelace card: one-tap "Scan now" against the escl_scan integration.
// Triggers a scan via /api/escl_scan/start and subscribes to
// sensor.printer_current_scan for live progress.
//
// Type:  custom:escl-scan-card
// Options:
//   title:   string, default "Scan"
//   entity:  the scan sensor, default sensor.printer_current_scan (auto-
//            detected if that entity was renamed)

const TAG = 'escl-scan-card';

if (!customElements.get(TAG)) {
  customElements.define(TAG, class extends HTMLElement {
    connectedCallback() { this._onHass?.(); }
    disconnectedCallback() { this._capabilityRequest?.abort(); }
  });
}

const C = customElements.get(TAG);

function responseErrorMessage(response, body, conflictFallback) {
  const message = [body?.message, body?.error]
    .find(value => typeof value === 'string' && value.trim());
  if (response.status === 409) {
    // Older servers (and proxies without JSON bodies) lack actionable detail.
    if (!message || /^(a )?scan (is )?already (running|in progress)$/i.test(message.trim())
        || /^(HTTP )?409( Conflict)?$/i.test(message.trim())) {
      return conflictFallback;
    }
  }
  return message || `HTTP ${response.status}`;
}

C.prototype.setConfig = function (config) {
  if (config?.duplex !== undefined && typeof config.duplex !== 'boolean') {
    throw new Error('Two-sided default must be true or false.');
  }
  const previousDefault = this._config?.duplex;
  const previousEntity = this._config?.entity;
  this._config = Object.assign({ title: 'Scan', duplex: false }, config || {});
  if (this._duplex === undefined || previousDefault !== this._config.duplex) {
    if (this._busy || this._activeScanId) this._resetDuplex = true;
    else this._duplex = this._config.duplex;
  }
  this._render();
  // _render() no-ops after the first call, so apply title changes (e.g. the
  // dashboard editor's live preview) directly to the already-rendered node.
  if (this._titleEl) this._titleEl.textContent = this._config.title;
  if (previousEntity !== this._config.entity) {
    this._lastSig = null;
    this._onHass();
  }
  this._syncControls();
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

C.prototype.getCardSize = function () { return 3; };
C.prototype.getGridOptions = function () { return { columns: 6, rows: 4, min_columns: 6, min_rows: 4 }; };

// Dashboard picker support: a default config and a visual editor built on
// HA's own <ha-form>, so the card is configurable without YAML.
C.getStubConfig = function () { return { title: 'Scan' }; };
C.getConfigElement = function () { return document.createElement(TAG + '-editor'); };

const EDITOR_SCHEMA = [
  { name: 'title', selector: { text: {} } },
  { name: 'duplex', selector: { boolean: {} } },
  { name: 'entity', selector: { entity: { domain: 'sensor', integration: 'escl_scan' } } },
];
const EDITOR_LABELS = { title: 'Title', entity: 'Scan sensor (optional)', duplex: 'Two-sided by default (uses feeder)' };

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
      /* Shared document-card contract v1. Keep this base identical in both cards. */
      :host { display: block; height: 100%; }
      [hidden] { display: none !important; }
      ha-card {
        box-sizing: border-box; height: 100%; min-height: 200px; padding: 12px;
        display: flex; flex-direction: column; gap: 8px;
        color: var(--primary-text-color);
      }
      .header { display: flex; align-items: center; gap: 8px; min-width: 0; }
      .icon { --mdc-icon-size: 24px; width: 24px; height: 24px; color: var(--primary-color); flex: none; }
      .title { font-size: 16px; font-weight: 500; line-height: 24px; overflow-wrap: anywhere; }
      .status { color: var(--secondary-text-color); font-size: 14px; line-height: 20px; min-height: 40px; overflow-wrap: anywhere; }
      .status.err { color: var(--error-color); }
      .status.ok { color: var(--success-color, var(--primary-color)); }
      .status a { color: inherit; text-underline-offset: 2px; display: inline-flex; align-items: center; min-height: 44px; }
      .status summary { cursor: pointer; min-height: 44px; }
      .status details > div { padding-top: 8px; }
      .controls { min-height: 44px; }
      .actions { margin-top: auto; }
      button, select { font: inherit; font-size: 14px; }
      button {
        min-height: 44px; padding: 8px 12px; border: 0;
        border-radius: var(--ha-card-border-radius, 12px);
        background: var(--secondary-background-color); color: var(--primary-text-color);
        cursor: pointer; line-height: 20px; box-sizing: border-box;
      }
      button:disabled { opacity: .5; cursor: default; }
      button:focus-visible, input:focus-visible, select:focus-visible, summary:focus-visible, a:focus-visible {
        outline: 2px solid var(--primary-color); outline-offset: 2px;
      }
      .primary, .cancel { width: 100%; font-weight: 500; }
      .cancel { display: none; color: var(--error-color); }
      .cancel.show { display: block; }
      @media (prefers-reduced-motion: reduce) { * { transition: none !important; animation: none !important; } }
      /* End shared document-card base. */
      .toggle { display: flex; align-items: center; justify-content: space-between; gap: 8px; min-height: 44px; font-size: 14px; cursor: pointer; }
      .toggle small { display: block; color: var(--secondary-text-color); font-size: 12px; }
      .two-sided { appearance: none; position: relative; margin: 0; width: 36px; height: 22px; flex: none; border-radius: 12px; background: var(--disabled-text-color); cursor: pointer; }
      .two-sided::before { content: ''; position: absolute; width: 16px; height: 16px; left: 3px; top: 3px; border-radius: 50%; background: var(--card-background-color); }
      .two-sided:checked { background: var(--primary-color); }
      .two-sided:checked::before { left: 17px; }
      .two-sided:disabled { opacity: .5; cursor: default; }
      .status select { display: block; width: 100%; min-height: 44px; margin: 8px 0; padding: 4px; color: var(--primary-text-color); background: var(--card-background-color); border: 1px solid var(--divider-color); border-radius: 8px; }
      .status button { width: 100%; margin-top: 4px; }
    </style>
    <ha-card>
      <div class="header"><ha-icon class="icon" icon="mdi:scanner" aria-hidden="true"></ha-icon><div class="title"></div></div>
      <div class="status" aria-live="polite" aria-atomic="true"></div>
      <div class="controls">
        <label class="toggle"><span>Two-sided<small>Uses feeder</small></span><input class="two-sided" type="checkbox" role="switch" aria-label="Two-sided scan using feeder"></label>
      </div>
      <div class="actions">
        <button class="primary" type="button">Scan</button>
        <button class="cancel" type="button">Cancel scan</button>
      </div>
    </ha-card>
  `;
  this._card = root.querySelector('ha-card');
  this._titleEl = root.querySelector('.title');
  this._statusEl = root.querySelector('.status');
  this._cancelEl = root.querySelector('.cancel');
  this._primaryEl = root.querySelector('.primary');
  this._twoSidedEl = root.querySelector('.two-sided');
  this._titleEl.textContent = this._config.title;
  this._primaryEl.addEventListener('click', () => {
    if (this._completedScan) this._downloadScan();
    else this._startScan();
  });
  this._cancelEl.addEventListener('click', () => this._cancelScan());
  this._twoSidedEl.addEventListener('change', () => {
    if (this._busy || this._activeScanId || this._completedScan) {
      this._syncControls();
      return;
    }
    this._duplex = this._twoSidedEl.checked;
    this._clearResultTimer();
    this._setStatus('');
    this._refreshCapabilities();
  });
  this._rendered = true;
  this._syncControls();
  this._onHass();
};

C.prototype._syncControls = function () {
  if (!this._primaryEl) return;
  const locked = !!this._busy || !!this._activeScanId;
  if (!locked && this._resetDuplex) {
    this._duplex = this._config.duplex;
    this._resetDuplex = false;
  }
  const current = this._scanState()?.attributes;
  const activeMode = locked && current?.scan_id === this._activeScanId
    ? current?.duplex_mode : null;
  this._twoSidedEl.checked = activeMode
    ? activeMode === 'manual' || activeMode === 'automatic' : !!this._duplex;
  const downloading = this._completedScan && this._downloadRequest === this._completedScan;
  this._twoSidedEl.disabled = locked || !!this._completedScan;
  this._primaryEl.disabled = locked || !!downloading;
  this._primaryEl.hidden = !!this._showCancel;
  this._primaryEl.textContent = this._busy ? 'Starting…' : downloading ? 'Downloading…'
    : this._completedScan ? 'Download PDF' : 'Scan';
  if (this._showingIdle) this._statusEl.textContent = this._idleStatus();
};

C.prototype._idleStatus = function () {
  if (!this._duplex) return 'Automatic source';
  const caps = this._capabilities;
  if (caps?.expires > Date.now()) {
    if (caps.automatic === true) return 'Feeder · Automatic duplex';
    if (caps.automatic === false && caps.manual === true) return 'Feeder · Two passes required';
  }
  return 'Feeder · may need two passes';
};

// Read only when the two-sided option is relevant. Cache per selected sensor,
// coalesce hass pushes, and retry unknown/older backends without blocking Scan.
C.prototype._refreshCapabilities = async function () {
  const entity = this._scanState()?.entity_id;
  if (!this.isConnected || !this._duplex || !entity || !this._hass
      || this._capabilityRequest || this._capabilities?.expires > Date.now()) return;
  const request = new AbortController();
  this._capabilityRequest = request;
  const caps = { automatic: null, manual: null, expires: Date.now() + 300_000 };
  this._capabilities = caps;
  this._syncControls();
  const timeout = setTimeout(() => request.abort(), 20_000);
  try {
    const response = await this._apiFetch('/api/escl_scan/capabilities?entity_id=' + encodeURIComponent(entity),
      { signal: request.signal });
    if (!response.ok) return;
    const body = await response.json();
    if (request.signal.aborted || this._capabilities !== caps || body?.schema_version !== 1
        || body.domain !== 'escl_scan' || body.entity_id !== entity || body.status !== 'fresh') return;
    caps.automatic = body.supported?.automatic_duplex;
    caps.manual = body.supported?.manual_duplex;
    const ttl = body.refresh_after_seconds;
    caps.expires = Date.now() + (Number.isFinite(ttl) ? Math.max(1, Math.min(900, ttl)) : 300) * 1000;
  } catch {
    // Capability discovery is optional. Unknown support must not imply manual.
  } finally {
    clearTimeout(timeout);
    if (this._capabilityRequest === request) {
      this._capabilityRequest = null;
      if (request.signal.aborted && !this.isConnected) this._capabilities = null;
      this._syncControls();
    }
  }
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
  this._showingIdle = !text;
  this._statusEl.textContent = '';
  if (text instanceof Node) this._statusEl.appendChild(text);
  else {
    const message = text || this._idleStatus();
    const split = cls === 'err' && message.length > 100 ? message.indexOf('. ') : -1;
    if (split > 0) {
      const details = document.createElement('details');
      const summary = document.createElement('summary');
      summary.textContent = message.slice(0, split + 2);
      const recovery = document.createElement('div');
      recovery.textContent = message.slice(split + 2);
      details.append(summary, recovery);
      this._statusEl.appendChild(details);
    } else this._statusEl.textContent = message;
  }
  this._statusEl.className = 'status' + (cls ? ' ' + cls : '');
};

C.prototype._setCancelVisible = function (visible) {
  this._showCancel = !!visible;
  this._cancelEl.classList.toggle('show', !!visible);
  this._syncControls();
};

C.prototype._startScan = async function (overrides) {
  if (this._busy || this._activeScanId || this._completedScan) return;
  const request = overrides || (this._duplex
    ? { source: 'Feeder', duplex: true } : { duplex: false });
  this._busy = true;
  this._backError = null;
  this._reverseBackOrder = false;
  this._card.classList.add('busy');
  this._setStatus('Starting…');
  this._setCancelVisible(false);
  this._clearResultTimer();
  try {
    const resp = await this._apiFetch('/api/escl_scan/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });
    let body = null;
    try { body = await resp.json(); } catch {}
    if (!resp.ok) {
      throw new Error(responseErrorMessage(resp, body,
        'The scanner is busy. Wait for the current scan to finish, or cancel it before starting a new scan.'));
    }
    if (typeof body?.scan_id !== 'string' || !body.scan_id) {
      throw new Error('Invalid response from scan service');
    }
    this._activeScanId = body?.scan_id ?? null;
    const src = typeof body.source === 'string' ? ` (${body.source.toLowerCase()})` : '';
    this._setStatus(`Scanning${src}…`);
    this._setCancelVisible(true);
    // A fast scan can already be terminal before its POST response arrives.
    const current = this._scanState();
    if (current?.attributes?.scan_id === this._activeScanId) {
      this._lastSig = null;
      this._onHass();
    }
    // From here on, the hass setter drives progress via _onHass().
  } catch (err) {
    if (this._activeScanId) {
      this._lastSig = null;
      this._onHass();
    } else {
      this._setStatus('Cannot start scan: ' + (err?.message || err), 'err');
    }
  } finally {
    this._busy = false;
    this._card.classList.remove('busy');
    this._syncControls();
  }
};

C.prototype._scanBacks = async function () {
  const current = this._scanState();
  const scanId = current?.attributes?.scan_id;
  if (current?.state !== 'awaiting-back-sides' || !scanId || this._resuming) return;
  this._resuming = true;
  this._backError = null;
  if (this._backButton) this._backButton.disabled = true;
  if (this._backOrderEl) this._backOrderEl.disabled = true;
  try {
    const r = await this._apiFetch('/api/escl_scan/scan_backs', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scan_id: scanId, reverse_back_order: !!this._reverseBackOrder }),
    });
    if (!r.ok) {
      let body = null;
      try { body = await r.json(); } catch {}
      throw new Error(responseErrorMessage(r, body,
        'Cannot scan the backs yet. Check that the scanner is idle and the back sides are loaded, then try again.'));
    }
    if (this._scanState()?.state === 'awaiting-back-sides'
        && this._activeScanId === scanId) this._setStatus('Starting back sides…');
  } catch (err) {
    const st = this._scanState();
    if (st?.state === 'awaiting-back-sides' && st.attributes?.scan_id === scanId) {
      this._backError = String(err?.message || err);
      this._renderScanState(st.state, st.attributes);
    }
  } finally {
    this._resuming = false;
    if (this._backButton) this._backButton.disabled = false;
    if (this._backOrderEl) this._backOrderEl.disabled = false;
  }
};

C.prototype._cancelScan = async function () {
  if (!this._activeScanId || this._canceling) return;
  const scanId = this._activeScanId;
  this._canceling = true;
  try {
    const r = await this._apiFetch('/api/escl_scan/cancel', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scan_id: scanId }),
    });
    if (!r.ok) {
      const body = await r.text();
      if (this._activeScanId === scanId) {
        this._setStatus('Cancel failed: ' + body.slice(0, 80), 'err');
      }
      return;
    }
    if (this._activeScanId === scanId) this._setStatus('Cancelling…');
  } catch (err) {
    if (this._activeScanId === scanId) {
      this._setStatus('Cancel failed: ' + (err?.message || err), 'err');
    }
  } finally {
    this._canceling = false;
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
const ACTIVE_STATES = new Set(['pending', 'processing', 'processing-stopped', 'awaiting-back-sides']);
// Non-download results briefly remain after the server returns to idle.
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
  const entity = st?.entity_id || this._config?.entity || null;
  if (this._resultEntity !== entity) {
    this._resultEntity = entity;
    this._completedScan = null;
    this._downloadedScanId = null;
    this._capabilityRequest?.abort();
    this._capabilityRequest = null;
    this._capabilities = null;
    this._lastSig = null;
    this._clearResultTimer();
  }
  this._refreshCapabilities();
  if (!st) {
    this._activeScanId = null;
    this._lastSig = null;
    if (!this._busy) {
      this._clearResultTimer();
      this._setStatus('');
      this._setCancelVisible(false);
    }
    return;
  }
  const attrs = st.attributes || {};
  const state = st.state;
  const sid = attrs.scan_id ?? null;
  const sig = JSON.stringify([
    st.entity_id, sid, state, attrs.pages_done, attrs.source,
    attrs.state_reasons, attrs.error, attrs.file_url, attrs.filename,
    attrs.duplex_mode, attrs.scan_phase, attrs.front_pages,
  ]);
  if (sig === this._lastSig) return;
  this._lastSig = sig;

  if (ACTIVE_STATES.has(state)) {
    this._completedScan = null;
    if (this._activeScanId !== sid) {
      this._backError = null;
      this._reverseBackOrder = false;
    }
    this._activeScanId = sid;
    this._clearResultTimer();
    this._renderScanState(state, attrs);
  } else if (TERMINAL_STATES.has(state)) {
    this._activeScanId = null;
    if (state !== 'completed') this._completedScan = null;
    this._renderScanState(state, attrs);
    this._clearResultTimer();
    // A downloadable result stays until handed to the browser or superseded
    // by a new scan. The backend's short terminal hold must not erase it.
    if (!this._completedScan) {
      this._resultTimer = setTimeout(() => {
        this._resultTimer = null;
        this._setStatus('');
        this._setCancelVisible(false);
      }, RESULT_LATCH_MS);
    }
  } else if (!this._resultTimer && !this._busy && !this._completedScan) {
    this._activeScanId = null;
    // idle / unavailable — clear, unless a fresh result is still latched
    // or a local start is mid-flight.
    this._setStatus(state === 'unavailable' || state === 'unknown' ? 'Scan status unavailable' : '',
      state === 'unavailable' || state === 'unknown' ? 'err' : '');
    this._setCancelVisible(false);
  }
};

C.prototype._downloadScan = async function () {
  const result = this._completedScan;
  if (!result || this._busy || this._activeScanId || this._downloadRequest === result) return;
  this._downloadRequest = result;
  this._syncControls();
  try {
    const response = await this._apiFetch(result.url);
    if (this._completedScan !== result) return;
    if (response.status === 404 || response.status === 410) {
      this._completedScan = null;
      this._downloadedScanId = result.scanId;
      this._setStatus('This PDF is no longer available. Scan the document again.', 'err');
      return;
    }
    if (!response.ok) throw new Error('Please try again.');
    const blob = await response.blob();
    if (this._completedScan !== result) return;
    if (!blob.size || (blob.type && !['application/pdf', 'application/octet-stream'].includes(blob.type))) {
      throw new Error('The server did not return a PDF. Please try again.');
    }
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = result.filename;
    link.hidden = true;
    document.body.appendChild(link);
    try { link.click(); } finally {
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    }
    // Browsers do not report whether the user ultimately saves the file.
    // Consume only after the authenticated PDF has been handed to Downloads.
    this._completedScan = null;
    this._downloadedScanId = result.scanId;
    this._setStatus('');
  } catch (err) {
    if (this._completedScan === result) {
      this._setStatus('Download failed. ' + (err?.message || 'Please try again.'), 'err');
    }
  } finally {
    if (this._downloadRequest === result) this._downloadRequest = null;
    this._syncControls();
  }
};

C.prototype._renderScanState = function (state, attrs) {
  const pagesDone = attrs?.pages_done || 0;
  const source = typeof attrs?.source === 'string' ? attrs.source.toLowerCase() : '';
  const reloadHint = attrs.duplex_mode === 'manual' && attrs.scan_phase === 'fronts'
    ? ' Wait for the reload prompt before flipping.' : '';
  if (state === 'pending') {
    this._setStatus(`Waiting for scanner…${reloadHint}`);
    this._setCancelVisible(true);
  } else if (state === 'processing') {
    const src = source ? ` (${source})` : '';
    const pages = pagesDone > 0 ? ` page ${pagesDone}` : '';
    const phase = attrs.duplex_mode === 'manual' ? ` ${attrs.scan_phase || 'fronts'}` : '';
    this._setStatus(`Scanning${phase}${src}${pages}…${reloadHint}`);
    this._setCancelVisible(true);
  } else if (state === 'processing-stopped') {
    this._setStatus('Scanner paused — check tray/jam', 'err');
    this._setCancelVisible(true);
  } else if (state === 'awaiting-back-sides') {
    const wrap = document.createElement('span');
    wrap.append(`Fronts ready (${attrs.front_pages || pagesDone} sheets). Reload with backs facing the scanner. Choose which sheet feeds first: `);
    const order = document.createElement('select');
    order.setAttribute('aria-label', 'Back-side sheet order');
    for (const [value, text] of [['same', 'First sheet first (same sheet order)'], ['reverse', 'Last sheet first (flipped stack)']]) {
      const option = document.createElement('option');
      option.value = value;
      option.textContent = text;
      order.appendChild(option);
    }
    order.value = this._reverseBackOrder ? 'reverse' : 'same';
    order.disabled = !!this._resuming;
    order.addEventListener('change', () => { this._reverseBackOrder = order.value === 'reverse'; });
    this._backOrderEl = order;
    wrap.appendChild(order);
    wrap.append(' ');
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = 'Scan back sides';
    button.disabled = !!this._resuming;
    button.addEventListener('click', (ev) => { ev.stopPropagation(); this._scanBacks(); });
    wrap.appendChild(button);
    if (this._backError) wrap.append(` ${this._backError}`);
    this._backButton = button;
    this._setStatus(wrap);
    this._setCancelVisible(true);
  } else if (state === 'completed') {
    if (attrs.scan_id && attrs.scan_id === this._downloadedScanId) {
      this._setCancelVisible(false);
      return;
    }
    const pages = pagesDone || 1;
    if (typeof attrs.file_url === 'string' && /^\/api\/escl_scan\/file\/[a-zA-Z0-9._-]+$/.test(attrs.file_url)) {
      if (this._completedScan?.scanId !== attrs.scan_id || this._completedScan?.url !== attrs.file_url) {
        this._completedScan = {
          scanId: attrs.scan_id, url: attrs.file_url,
          filename: typeof attrs.filename === 'string' && attrs.filename ? attrs.filename : 'scan.pdf',
        };
      }
    } else this._completedScan = null;
    this._setStatus(`Scan ready ✓ (${pages} page${pages > 1 ? 's' : ''})`, 'ok');
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
  // Let HA rebuild its owned element, not just the DOM node. Otherwise it
  // keeps pushing hass to the error and may reinsert it on visibility updates.
  if (parent?.tagName === 'HUI-CARD' && parent._element === err
      && parent.config?.type === 'custom:' + TAG && typeof parent.load === 'function') {
    try {
      parent.load();
      return;
    } catch {
      _ESCL_HEALED.delete(err);
      return;
    }
  }
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
  // Lovelace keeps references to the failed card. Seed the replacement with
  // the current hass object so it can scan even before the next state push.
  fresh.hass = err.hass || parent?.hass
    || document.querySelector('home-assistant')?.hass;
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
