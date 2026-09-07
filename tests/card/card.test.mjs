// jsdom tests for the Lovelace card. Run: npm run test:card
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { JSDOM } from 'jsdom';

const here = path.dirname(fileURLToPath(import.meta.url));
const CARD_SRC = readFileSync(
  path.join(here, '..', '..', 'custom_components', 'escl_scan', 'static', 'card.js'),
  'utf8',
);
const TAG = 'escl-scan-card';
const SENSOR = 'sensor.printer_current_scan';

function boot() {
  const dom = new JSDOM('<home-assistant></home-assistant>', {
    runScripts: 'outside-only',
    pretendToBeVisual: true,
  });
  dom.window.eval(CARD_SRC);
  return dom.window;
}

function jsonResponse(body, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
    text: async () => JSON.stringify(body),
  };
}

// A hass object the card can diff. `push(entityState)` simulates lovelace
// handing the card a fresh hass after a state change.
function makeHass(el, { fetchImpl } = {}) {
  const calls = { fetch: [] };
  const states = {};
  const hass = {
    states,
    fetchWithAuth: async (url, init) => {
      calls.fetch.push({ url, init });
      return fetchImpl ? fetchImpl(url, init) : jsonResponse({});
    },
  };
  const push = (id, state, attributes = {}) => {
    states[id] = { entity_id: id, state, attributes };
    el.hass = Object.assign({}, hass, { states: Object.assign({}, states) });
  };
  el.hass = hass;
  return { hass, calls, push };
}

function mount(win, config = {}) {
  const el = win.document.createElement(TAG);
  el.setConfig(config);
  win.document.body.appendChild(el);
  return el;
}

const status = (el) => el.shadowRoot.querySelector('.status');
const cancelShown = (el) => el.shadowRoot.querySelector('.cancel').classList.contains('show');

test('registers card + editor, picker entry, stub config', () => {
  const win = boot();
  const C = win.customElements.get(TAG);
  assert.ok(C);
  assert.equal(C.getStubConfig().title, 'Scan now');
  assert.ok(win.customElements.get(TAG + '-editor'), 'editor element defined');
  assert.equal(C.getConfigElement().tagName.toLowerCase(), TAG + '-editor');
  const entry = win.customCards.find((c) => c.type === TAG);
  assert.ok(entry && entry.preview === true);
});

test('renders title and updates it on later setConfig without re-rendering', () => {
  const win = boot();
  const el = mount(win, { title: 'Hello' });
  const title = el.shadowRoot.querySelector('.title');
  assert.equal(title.textContent, 'Hello');
  el.setConfig({ title: 'Changed' });
  assert.equal(title.textContent, 'Changed');
  assert.equal(el.shadowRoot.querySelectorAll('ha-card').length, 1);
});

test('start posts to the endpoint, shows source, exposes cancel', async () => {
  const win = boot();
  const el = mount(win);
  const { calls } = makeHass(el, {
    fetchImpl: async () => jsonResponse({ ok: true, scan_id: 'abc', source: 'Feeder' }),
  });
  await el._startScan();
  assert.equal(calls.fetch[0].url, '/api/escl_scan/start');
  assert.equal(calls.fetch[0].init.method, 'POST');
  assert.equal(el._activeScanId, 'abc');
  assert.equal(status(el).textContent, 'Scanning (feeder)…');
  assert.ok(cancelShown(el));
  assert.equal(el._busy, false);
});

test('409 busy guard and other errors are surfaced', async () => {
  const win = boot();
  const el = mount(win);
  makeHass(el, { fetchImpl: async () => jsonResponse({ message: 'scan already running' }, 409) });
  await el._startScan();
  assert.equal(status(el).textContent, 'Scan failed: scan already running');
  assert.ok(status(el).classList.contains('err'));
  assert.ok(!cancelShown(el));
});

test('hass setter drives progress: pending → processing → completed with Open scan link', async () => {
  const win = boot();
  const el = mount(win);
  const { push, calls } = makeHass(el, {
    fetchImpl: async () => ({ ok: true, status: 200, blob: async () => new win.Blob(['x']) }),
  });

  push(SENSOR, 'pending', { scan_id: 's1' });
  assert.equal(status(el).textContent, 'Waiting for scanner…');
  assert.ok(cancelShown(el));
  assert.equal(el._activeScanId, 's1');

  push(SENSOR, 'processing', { scan_id: 's1', source: 'Platen', pages_done: 2 });
  assert.equal(status(el).textContent, 'Scanning (platen) page 2…');

  push(SENSOR, 'processing-stopped', { scan_id: 's1', pages_done: 2 });
  assert.match(status(el).textContent, /paused/);
  assert.ok(status(el).classList.contains('err'));

  push(SENSOR, 'completed', { scan_id: 's1', pages_done: 3, file_url: '/api/escl_scan/file/s1.pdf' });
  assert.match(status(el).textContent, /^Scan ready ✓ \(3 pages\)/);
  assert.ok(status(el).classList.contains('ok'));
  assert.ok(!cancelShown(el));
  const link = status(el).querySelector('a');
  assert.ok(link, 'Open scan link rendered');
  assert.equal(link.textContent, 'Open scan');

  // Result latches: an idle push right after does NOT clear the link.
  push(SENSOR, 'idle', { scan_id: null });
  assert.ok(status(el).querySelector('a'), 'link still latched');

  // Clicking the link fetches with auth rather than navigating.
  win.URL.createObjectURL = () => 'blob:x';
  win.URL.revokeObjectURL = () => {};
  win.open = () => ({});
  link.dispatchEvent(new win.MouseEvent('click', { bubbles: true, cancelable: true }));
  await new Promise((r) => setTimeout(r, 0));
  assert.equal(calls.fetch.at(-1).url, '/api/escl_scan/file/s1.pdf');
  // The click must not have started a new scan.
  assert.ok(!calls.fetch.some((c) => c.url === '/api/escl_scan/start'));
});

test('aborted state shows the reason; canceled shows plain text', () => {
  const win = boot();
  const el = mount(win);
  const { push } = makeHass(el);
  push(SENSOR, 'aborted', { scan_id: 's2', state_reasons: 'adf-jam' });
  assert.equal(status(el).textContent, 'Scan failed: adf-jam');
  push(SENSOR, 'canceled', { scan_id: 's3' });
  assert.equal(status(el).textContent, 'Scan canceled');
});

test('identical pushes do not re-render (signature dedupe)', () => {
  const win = boot();
  const el = mount(win);
  const { push } = makeHass(el);
  let renders = 0;
  const orig = el._renderScanState.bind(el);
  el._renderScanState = (...a) => { renders += 1; return orig(...a); };
  push(SENSOR, 'processing', { scan_id: 's1', pages_done: 1 });
  push(SENSOR, 'processing', { scan_id: 's1', pages_done: 1 });
  push(SENSOR, 'processing', { scan_id: 's1', pages_done: 2 });
  assert.equal(renders, 2);
});

test('entity option wins; renamed sensor is auto-detected by enum options', () => {
  const win = boot();
  const explicit = mount(win, { entity: 'sensor.office_scan' });
  const { push } = makeHass(explicit);
  push('sensor.office_scan', 'processing', { scan_id: 'x' });
  assert.equal(status(explicit).textContent, 'Scanning…');

  const auto = mount(win);
  const h = makeHass(auto);
  h.push('sensor.unrelated', 'on', {});
  h.push('sensor.renamed_scan', 'pending', {
    scan_id: 'y',
    options: ['idle', 'pending', 'processing', 'processing-stopped', 'completed'],
  });
  assert.equal(status(auto).textContent, 'Waiting for scanner…');
  assert.equal(auto._sensorId, 'sensor.renamed_scan');
});

test('cancel posts the active scan id', async () => {
  const win = boot();
  const el = mount(win);
  const { calls } = makeHass(el, { fetchImpl: async () => jsonResponse({ ok: true }) });
  el._activeScanId = 's9';
  await el._cancelScan();
  assert.equal(calls.fetch[0].url, '/api/escl_scan/cancel');
  assert.equal(JSON.parse(calls.fetch[0].init.body).scan_id, 's9');
  assert.equal(status(el).textContent, 'Cancelling…');
});

test('falls back to a bearer header when fetchWithAuth is missing', async () => {
  const win = boot();
  const el = mount(win);
  const seen = [];
  win.fetch = async (url, init) => { seen.push({ url, init }); return jsonResponse({ scan_id: 'z' }); };
  el.hass = { states: {}, auth: { data: { access_token: 'tok' } } };
  await el._startScan();
  assert.equal(seen[0].url, '/api/escl_scan/start');
  assert.equal(seen[0].init.headers.Authorization, 'Bearer tok');
});

test('heals a hui-error-card placeholder using the parent hui-card config', async () => {
  const win = boot();
  const doc = win.document;
  const host = doc.querySelector('home-assistant');
  const huiCard = doc.createElement('hui-card');
  huiCard._elementConfig = { type: 'custom:' + TAG, title: 'Healed' };
  const err = doc.createElement('hui-error-card');
  err._config = { type: 'error', message: "Custom element doesn't exist: escl-scan-card." };
  huiCard.appendChild(err);
  host.appendChild(huiCard);
  // First staggered sweep fires at 40 ms.
  await new Promise((r) => setTimeout(r, 80));
  const healed = huiCard.querySelector(TAG);
  assert.ok(healed, 'error card replaced');
  assert.equal(huiCard.querySelector('hui-error-card'), null);
  assert.equal(healed.shadowRoot.querySelector('.title').textContent, 'Healed');
});

test('editor emits config-changed and drops an empty entity', () => {
  const win = boot();
  const editor = win.document.createElement(TAG + '-editor');
  editor.setConfig({ title: 'T', entity: 'sensor.x' });
  win.document.body.appendChild(editor);
  const form = editor.querySelector('ha-form');
  assert.ok(form, 'ha-form mounted');
  let got = null;
  editor.addEventListener('config-changed', (ev) => { got = ev.detail.config; });
  form.dispatchEvent(new win.CustomEvent('value-changed', { detail: { value: { title: 'New', entity: '' } } }));
  assert.equal(JSON.stringify(got), JSON.stringify({ title: 'New' }));
});
