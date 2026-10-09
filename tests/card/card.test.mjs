// jsdom tests for the Lovelace card. Run: npm run test:card
import { afterEach, test } from 'node:test';
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
test('healing rebuilds the HA-owned card so state updates cannot restore the error', async () => {
  const win = boot();
  const doc = win.document;
  const host = doc.querySelector('home-assistant');
  host.hass = { states: {} };
  const wrapper = doc.createElement('hui-card');
  wrapper.config = wrapper._elementConfig = { type: 'custom:' + TAG, title: 'Recovered' };
  const error = doc.createElement('hui-error-card');
  error._config = { type: 'error', message: "Custom element doesn't exist: " + TAG + '.' };
  wrapper._element = error;
  wrapper.appendChild(error);
  let loads = 0;
  wrapper.load = () => {
    loads++;
    const replacement = doc.createElement(TAG);
    replacement.setConfig(wrapper.config);
    replacement.hass = host.hass;
    wrapper._element.replaceWith(replacement);
    wrapper._element = replacement;
  };
  host.appendChild(wrapper);
  await new Promise(resolve => setTimeout(resolve, 80));
  assert.equal(loads, 1);
  assert.equal(wrapper._element.localName, TAG);
  assert.equal(wrapper.querySelector(TAG), wrapper._element);
  assert.equal(wrapper._element.shadowRoot.querySelector('.title').textContent, 'Recovered');
  // HA updates and shows its stored element, not whichever node is in the DOM.
  const nextHass = { states: {} };
  wrapper._element.hass = nextHass;
  if (!wrapper._element.parentElement) wrapper.appendChild(wrapper._element);
  assert.equal(wrapper.children.length, 1);
  assert.equal(wrapper.querySelector('hui-error-card'), null);
});
const SENSOR = 'sensor.printer_current_scan';
const windows = [];
afterEach(() => {
  for (const win of windows.splice(0)) win.close();
});

function boot(translations = {}, setup) {
  const dom = new JSDOM('<home-assistant></home-assistant>', {
    runScripts: 'outside-only',
    pretendToBeVisual: true,
  });
  dom.window.downloads = [];
  dom.window.HTMLAnchorElement.prototype.click = function () {
    dom.window.downloads.push({ href: this.href, filename: this.download, attached: this.isConnected });
  };
  dom.window.URL.createObjectURL = () => 'blob:scan';
  dom.window.URL.revokeObjectURL = () => {};
  // jsdom has no native dialog lifecycle; model its asynchronous close event.
  dom.window.HTMLDialogElement.prototype.showModal = function () { this.open = true; };
  dom.window.HTMLDialogElement.prototype.close = function () {
    if (!this.open) return;
    this.open = false;
    dom.window.setTimeout(() => this.dispatchEvent(new dom.window.Event('close')), 0);
  };
  setup?.(dom.window);
  dom.window.eval(CARD_SRC + '\nObject.assign(CARD_TRANSLATIONS, ' + JSON.stringify(translations) + ');');
  windows.push(dom.window);
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
function makeHass(el, { fetchImpl, capabilitiesImpl } = {}) {
  const calls = { fetch: [], capabilities: [] };
  const states = {};
  const hass = {
    states,
    fetchWithAuth: async (url, init) => {
      if (url.startsWith('/api/escl_scan/capabilities?')) {
        calls.capabilities.push({ url, init });
        return capabilitiesImpl ? capabilitiesImpl(url, init) : jsonResponse({}, 404);
      }
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

test('Two-sided changes intent without submitting; Scan submits the frozen feeder intent once', async () => {
  const win = boot();
  const el = mount(win);
  const { calls } = makeHass(el, {
    fetchImpl: async () => jsonResponse({ scan_id: 'duplex1', source: 'Feeder' }),
  });
  const toggle = el.shadowRoot.querySelector('.two-sided');
  assert.equal(toggle.getAttribute('role'), 'switch');
  toggle.click();
  assert.equal(calls.fetch.length, 0);
  assert.equal(toggle.checked, true);
  assert.match(status(el).textContent, /Feeder.*two passes/);
  const primary = el.shadowRoot.querySelector('.primary');
  primary.click();
  primary.click();
  await new Promise(resolve => setTimeout(resolve, 0));
  assert.equal(calls.fetch.length, 1);
  assert.deepEqual(JSON.parse(calls.fetch[0].init.body), { source: 'Feeder', duplex: true });
  assert.equal(toggle.disabled, true);
  toggle.click();
  assert.equal(toggle.checked, true);
});

test('manual duplex waiting shows instructions and resumes once without overwriting progress', async () => {
  const win = boot();
  const el = mount(win);
  let finish;
  const { calls, push } = makeHass(el, {
    fetchImpl: () => new Promise(resolve => { finish = resolve; }),
  });
  const attrs = { scan_id: 'manual1', duplex_mode: 'manual', front_pages: 3, pages_done: 3 };
  push(SENSOR, 'pending', { ...attrs, scan_phase: 'fronts' });
  assert.match(status(el).textContent, /Wait for the reload prompt before flipping/);
  push(SENSOR, 'processing', { ...attrs, scan_phase: 'fronts' });
  assert.match(status(el).textContent, /Wait for the reload prompt before flipping/);
  push(SENSOR, 'awaiting-back-sides', attrs);
  assert.match(status(el).textContent, /same sheet order/);
  assert.ok(cancelShown(el));
  await el._startScan();
  assert.equal(calls.fetch.length, 0);
  const button = status(el).querySelector('button');
  button.click();
  button.click();
  assert.equal(calls.fetch.length, 1);
  assert.equal(calls.fetch[0].url, '/api/escl_scan/scan_backs');
  assert.deepEqual(JSON.parse(calls.fetch[0].init.body), { scan_id: 'manual1', reverse_back_order: false, entity_id: SENSOR });
  push(SENSOR, 'processing', { ...attrs, scan_phase: 'backs', pages_done: 4 });
  finish(jsonResponse({ ok: true, scan_id: 'manual1', state: 'pending' }));
  await new Promise(resolve => setTimeout(resolve, 0));
  assert.match(status(el).textContent, /Scanning backs.*page 4/);
  assert.doesNotMatch(status(el).textContent, /reload prompt/);
});

test('manual resume errors retain the retry and cancel controls', async () => {
  const win = boot();
  const el = mount(win);
  const { calls, push } = makeHass(el, {
    fetchImpl: async () => jsonResponse({ message: 'Load the back sides first' }, 409),
  });
  push(SENSOR, 'awaiting-back-sides', { scan_id: 'manual1', front_pages: 2 });
  const order = status(el).querySelector('select');
  order.click();
  order.dispatchEvent(new win.KeyboardEvent('keydown', { key: ' ', bubbles: true }));
  assert.equal(calls.fetch.length, 0);
  order.value = 'reverse';
  order.dispatchEvent(new win.Event('change'));
  status(el).querySelector('button').click();
  await new Promise(resolve => setTimeout(resolve, 0));
  assert.match(status(el).textContent, /Load the back sides first/);
  assert.ok(cancelShown(el));
  assert.equal(status(el).querySelector('button').disabled, false);
  assert.equal(status(el).querySelector('select').value, 'reverse');
  assert.equal(status(el).querySelector('select').disabled, false);
  assert.equal(JSON.parse(calls.fetch[0].init.body).reverse_back_order, true);
  status(el).querySelector('button').click();
  await new Promise(resolve => setTimeout(resolve, 0));
  assert.equal(calls.fetch.length, 2);
  push(SENSOR, 'canceled', { scan_id: 'manual1' });
  push(SENSOR, 'awaiting-back-sides', { scan_id: 'manual2', front_pages: 2 });
  assert.equal(status(el).querySelector('select').value, 'same');
});

test('cancel wins over a late manual resume response', async () => {
  const win = boot();
  const el = mount(win);
  let finish;
  const { push } = makeHass(el, { fetchImpl: () => new Promise(resolve => { finish = resolve; }) });
  push(SENSOR, 'awaiting-back-sides', { scan_id: 'manual1', front_pages: 2 });
  status(el).querySelector('button').click();
  push(SENSOR, 'canceled', { scan_id: 'manual1' });
  finish(jsonResponse({ ok: true, scan_id: 'manual1' }));
  await new Promise(resolve => setTimeout(resolve, 0));
  assert.equal(status(el).textContent, 'Scan canceled');
  assert.equal(cancelShown(el), false);
});

test('registers card + editor, picker entry, stub config', () => {
  const win = boot();
  const C = win.customElements.get(TAG);
  assert.ok(C);
  assert.equal(C.getStubConfig().title, 'Scan');
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
  assert.match(status(el).textContent, /scanner is busy.*Wait.*cancel/);
  assert.doesNotMatch(status(el).textContent, /409/);
  assert.ok(status(el).classList.contains('err'));
  assert.ok(!cancelShown(el));
});

for (const [name, response, expected] of [
  ['non-JSON 409', { ok: false, status: 409, json: async () => { throw new Error('HTML'); } }, /scanner is busy.*Wait/],
  ['invalid message type', jsonResponse({ message: { technical: 409 } }, 409), /scanner is busy.*Wait/],
  ['technical status message', jsonResponse({ message: 'HTTP 409' }, 409), /scanner is busy.*Wait/],
  ['waiting for backs', jsonResponse({ message: 'A two-sided scan is waiting for the back sides. Choose Scan back sides.' }, 409), /waiting for the back sides.*Scan back sides/],
  ['other errors', jsonResponse({ message: 'Connection unavailable' }, 502), /Connection unavailable/],
]) {
  test(`start error explains ${name}`, async () => {
    const win = boot();
    const el = mount(win);
    makeHass(el, { fetchImpl: async () => response });
    await el._startScan({ source: 'Feeder', duplex: true });
    assert.match(status(el).textContent, expected);
    assert.ok(status(el).classList.contains('err'));
    assert.equal(el._activeScanId, null);
    assert.equal(el.shadowRoot.querySelector('.two-sided').disabled, false);
  });
}

test('back-side conflicts without JSON give guidance and retain retry controls', async () => {
  const win = boot();
  const el = mount(win);
  const { push } = makeHass(el, {
    fetchImpl: async () => ({ ok: false, status: 409, json: async () => { throw new Error('HTML'); } }),
  });
  push(SENSOR, 'awaiting-back-sides', { scan_id: 'manual1', front_pages: 3 });
  await el._scanBacks();
  assert.match(status(el).textContent, /Check.*idle.*loaded.*try again/);
  assert.doesNotMatch(status(el).textContent, /HTTP 409/);
  assert.ok(cancelShown(el));
  assert.equal(status(el).querySelector('button').disabled, false);
});

test('hass setter drives progress: pending → processing → completed with Download PDF action', async () => {
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
  const primary = el.shadowRoot.querySelector('.primary');
  assert.equal(primary.textContent, 'Download PDF');
  assert.equal(primary.disabled, false);

  // A result survives the server's idle reset without a 30-second timeout.
  push(SENSOR, 'idle', { scan_id: null });
  assert.equal(primary.textContent, 'Download PDF');
  assert.ok(!el._resultTimer);
  primary.click();
  await new Promise((r) => setTimeout(r, 0));
  assert.equal(primary.textContent, 'Scan');
  assert.equal(el.shadowRoot.querySelector('.two-sided').disabled, false);
  assert.equal(win.downloads.length, 1);
  assert.equal(win.downloads[0].attached, true);
  assert.equal(win.document.querySelector('a[download]'), null);
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
  host.hass = { states: {} };
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
  assert.equal(healed.hass, host.hass);
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

test('active scans block repeat taps until a terminal state arrives', async () => {
  const win = boot();
  const el = mount(win);
  const { push, calls } = makeHass(el);
  push(SENSOR, 'processing', { scan_id: 's1' });
  await el._startScan();
  assert.equal(calls.fetch.length, 0);
  push(SENSOR, 'completed', { scan_id: 's1' });
  assert.equal(el._activeScanId, null);
});

test('start response cannot overwrite an earlier terminal sensor update', async () => {
  const win = boot();
  const el = mount(win);
  let respond;
  const { push } = makeHass(el, {
    fetchImpl: () => new Promise((resolve) => { respond = resolve; }),
  });
  const request = el._startScan();
  push(SENSOR, 'completed', { scan_id: 's1', pages_done: 2, file_url: '/api/escl_scan/file/s1' });
  respond(jsonResponse({ scan_id: 's1', source: 'Feeder' }));
  await request;
  assert.match(status(el).textContent, /Scan ready/);
  assert.equal(el.shadowRoot.querySelector('.primary').textContent, 'Download PDF');
  assert.equal(el._activeScanId, null);
  assert.ok(!cancelShown(el));
});

test('cancel response cannot overwrite an earlier canceled sensor update', async () => {
  const win = boot();
  const el = mount(win);
  let respond;
  const { push, calls } = makeHass(el, {
    fetchImpl: () => new Promise((resolve) => { respond = resolve; }),
  });
  push(SENSOR, 'processing', { scan_id: 's1' });
  const request = el._cancelScan();
  await el._cancelScan();
  assert.equal(calls.fetch.length, 1);
  push(SENSOR, 'canceled', { scan_id: 's1' });
  respond(jsonResponse({ ok: true }));
  await request;
  assert.equal(status(el).textContent, 'Scan canceled');
});

test('attribute changes refresh status even with unchanged state and page count', () => {
  const win = boot();
  const el = mount(win);
  const { push } = makeHass(el);
  push(SENSOR, 'failed', { scan_id: 's1', error: 'first error' });
  push(SENSOR, 'failed', { scan_id: 's1', error: 'second error' });
  assert.equal(status(el).textContent, 'Scan failed: second error');
  push(SENSOR, 'completed', { scan_id: 's2' });
  assert.equal(status(el).querySelector('a'), null);
  push(SENSOR, 'completed', { scan_id: 's2', file_url: '/api/escl_scan/file/s2' });
  assert.equal(el.shadowRoot.querySelector('.primary').textContent, 'Download PDF');
});

test('changing configured entity waits for the active scan and missing sensors clear cancel', () => {
  const win = boot();
  const el = mount(win);
  const { push } = makeHass(el);
  push(SENSOR, 'processing', { scan_id: 's1' });
  push('sensor.other', 'failed', { scan_id: 's2', error: 'jam' });
  el.setConfig({ entity: 'sensor.other' });
  assert.equal(el._activeScanId, 's1', 'active scan target stays frozen');
  assert.equal(status(el).textContent, 'Scanning…');
  push(SENSOR, 'canceled', {scan_id:'s1'});
  push('sensor.other', 'failed', {scan_id:'s2',error:'jam'});
  assert.equal(status(el).textContent, 'Scan failed: jam');
  el.setConfig({ entity: 'sensor.missing' });
  assert.equal(status(el).textContent, 'Scan status unavailable');
  assert.equal(el._activeScanId, null);
  assert.ok(!cancelShown(el));
});

test('Download PDF fetches once and only returns to Scan after receiving the file', async () => {
  const win = boot();
  const el = mount(win);
  let respond;
  const { push, calls } = makeHass(el, {
    fetchImpl: () => new Promise((resolve) => { respond = resolve; }),
  });
  push(SENSOR, 'completed', { scan_id: 's1', filename: 'document.pdf', file_url: '/api/escl_scan/file/s1' });
  const primary = el.shadowRoot.querySelector('.primary');
  primary.click();
  primary.click();
  assert.equal(calls.fetch.length, 1);
  assert.equal(primary.textContent, 'Downloading…');
  assert.equal(primary.disabled, true);
  assert.equal(win.downloads.length, 0);
  respond({ ok: true, blob: async () => new win.Blob(['PDF'], { type: 'application/pdf' }) });
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(win.downloads[0].filename, 'document.pdf');
  assert.equal(primary.textContent, 'Scan');
  // Even a changed terminal snapshot must not resurrect a consumed download.
  push(SENSOR, 'completed', { scan_id: 's1', pages_done: 3, file_url: '/api/escl_scan/file/s1' });
  assert.equal(primary.textContent, 'Scan');
});

test('Download PDF refuses external URLs from sensor attributes', () => {
  const win = boot();
  const el = mount(win);
  const { push, calls } = makeHass(el);
  push(SENSOR, 'completed', { scan_id: 's1', file_url: 'https://other-host/collect' });
  assert.equal(el.shadowRoot.querySelector('.primary').textContent, 'Scan');
  assert.equal(calls.fetch.length, 0);
});

test('malformed successful start responses show an error with no cancel control', async () => {
  const win = boot();
  const el = mount(win);
  makeHass(el, { fetchImpl: async () => jsonResponse({ ok: true }) });
  await el._startScan();
  assert.match(status(el).textContent, /Invalid response/);
  assert.ok(!cancelShown(el));
});

test('one-sided switch explicitly overrides integration duplex defaults', async () => {
  const win = boot();
  const el = mount(win, { duplex: true });
  const { calls } = makeHass(el, { fetchImpl: async () => jsonResponse({ scan_id: 'one' }) });
  el.shadowRoot.querySelector('.two-sided').click();
  el.shadowRoot.querySelector('.primary').click();
  await new Promise(resolve => setTimeout(resolve, 0));
  assert.deepEqual(JSON.parse(calls.fetch[0].init.body), { duplex: false });
});

test('card surface and switch keyboard events do not start a scan', () => {
  const win = boot();
  const el = mount(win);
  const { calls } = makeHass(el);
  const card = el.shadowRoot.querySelector('ha-card');
  assert.equal(card.getAttribute('role'), null);
  assert.equal(card.getAttribute('tabindex'), null);
  for (const node of [card, el.shadowRoot.querySelector('.two-sided')]) {
    node.dispatchEvent(new win.KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
    node.dispatchEvent(new win.KeyboardEvent('keydown', { key: ' ', bubbles: true }));
  }
  card.click();
  assert.equal(calls.fetch.length, 0);
  assert.equal(el.shadowRoot.querySelector('.cancel').tagName, 'BUTTON');
});

test('duplex preference survives title edits and freezes during an active scan', async () => {
  const win = boot();
  const el = mount(win);
  const { push, calls } = makeHass(el, { fetchImpl: async () => jsonResponse({ scan_id: 's1' }) });
  const toggle = el.shadowRoot.querySelector('.two-sided');
  toggle.click();
  el.setConfig({ title: 'Desk' });
  assert.equal(toggle.checked, true);
  await el._startScan();
  el.setConfig({ title: 'Desk', duplex: true });
  el.setConfig({ title: 'Desk', duplex: false });
  assert.equal(toggle.checked, true, 'submitted intent stays visible');
  assert.equal(toggle.disabled, true);
  assert.deepEqual(JSON.parse(calls.fetch[0].init.body), { source: 'Feeder', duplex: true });
  push(SENSOR, 'completed', { scan_id: 's1', pages_done: 1 });
  assert.equal(toggle.checked, false, 'new default applies after completion');
  assert.equal(toggle.disabled, false);
});

test('long scan conflict exposes summary and recovery details without starting jobs', async () => {
  const win = boot();
  const el = mount(win);
  const { calls } = makeHass(el, { fetchImpl: async () => jsonResponse({}, 409) });
  await el._startScan();
  const details = status(el).querySelector('details');
  assert.match(details.querySelector('summary').textContent, /scanner is busy/);
  assert.match(details.querySelector('div').textContent, /Wait.*cancel/);
  details.querySelector('summary').click();
  assert.equal(calls.fetch.length, 1);
  assert.equal(details.open, true);
});

test('an external duplex job displays its actual mode without changing next-job intent', () => {
  const win = boot();
  const el = mount(win);
  const { push } = makeHass(el);
  const toggle = el.shadowRoot.querySelector('.two-sided');
  push(SENSOR, 'processing', { scan_id: 'external', duplex_mode: 'manual' });
  assert.equal(toggle.checked, true);
  assert.equal(toggle.disabled, true);
  push(SENSOR, 'completed', { scan_id: 'external', duplex_mode: 'manual' });
  assert.equal(toggle.checked, false);
  assert.equal(toggle.disabled, false);
});

const tick = () => new Promise(resolve => setTimeout(resolve, 0));
const capabilities = (entity = SENSOR, automatic = false, manual = true) => ({
  schema_version: 1, domain: 'escl_scan', entity_id: entity, status: 'fresh',
  refresh_after_seconds: 900, supported: { automatic_duplex: automatic, manual_duplex: manual },
});

test('two-sided label distinguishes automatic, manual and unknown scanner support', async () => {
  for (const [body, expected] of [
    [capabilities(SENSOR, true), 'Feeder · Automatic duplex'],
    [capabilities(), 'Feeder · Two passes required'],
    [capabilities(SENSOR, null, true), 'Feeder · may need two passes'],
    [{ ...capabilities(), status: 'stale' }, 'Feeder · may need two passes'],
    [{ ...capabilities(), schema_version: 2 }, 'Feeder · may need two passes'],
    [capabilities('sensor.other'), 'Feeder · may need two passes'],
    [{ ...capabilities(), domain: 'ipp_print' }, 'Feeder · may need two passes'],
  ]) {
    const el = mount(boot(), { duplex: true });
    const { push, calls } = makeHass(el, { capabilitiesImpl: async () => jsonResponse(body) });
    push(SENSOR, 'idle');
    await tick();
    assert.equal(status(el).textContent, expected);
    push(SENSOR, 'idle');
    assert.equal(calls.capabilities.length, 1, 'hass updates use the cache');
    assert.equal(calls.fetch.length, 0, 'discovery never starts a job');
  }
});

test('capability failures use bounded retries and never prevent starting a scan', async () => {
  for (const capabilitiesImpl of [async () => jsonResponse({}, 404), async () => { throw new Error('offline'); }]) {
    const el = mount(boot(), { duplex: true });
    const { push, calls } = makeHass(el, {
      capabilitiesImpl, fetchImpl: async () => jsonResponse({ scan_id: 'new' }),
    });
    push(SENSOR, 'idle');
    await tick();
    push(SENSOR, 'idle');
    assert.match(status(el).textContent, /may need two passes/);
    assert.equal(calls.capabilities.length, 1);
    await el._startScan();
    assert.equal(calls.fetch.length, 1);
    assert.equal(el._activeScanId, 'new');
  }
});

test('capability requests coalesce and an old sensor response cannot relabel a new target', async () => {
  const el = mount(boot(), { duplex: true });
  const pending = [];
  const { push, calls } = makeHass(el, {
    capabilitiesImpl: () => new Promise(resolve => pending.push(resolve)),
  });
  push(SENSOR, 'idle');
  push(SENSOR, 'idle');
  assert.equal(calls.capabilities.length, 1);
  push('sensor.other', 'idle');
  el.setConfig({ entity: 'sensor.other', duplex: true });
  assert.equal(calls.capabilities[0].init.signal.aborted, true);
  assert.equal(calls.capabilities.length, 2);
  pending[1](jsonResponse(capabilities('sensor.other', true)));
  await tick();
  pending[0](jsonResponse(capabilities()));
  await tick();
  assert.equal(status(el).textContent, 'Feeder · Automatic duplex');
  el._capabilities.expires = 0;
  push('sensor.other', 'idle');
  assert.match(status(el).textContent, /may need two passes/, 'expired data stops promising automatic duplex');
  assert.equal(calls.capabilities.length, 3);
  el.remove();
  assert.equal(calls.capabilities[2].init.signal.aborted, true, 'native detach aborts the request');
  pending[2](jsonResponse(capabilities('sensor.other')));
  await tick();
});

test('a failed or invalid PDF download keeps the primary action available for retry', async () => {
  const win = boot();
  for (const failure of [
    async () => jsonResponse({}, 500),
    async () => { throw new Error('Connection lost'); },
    async () => ({ ok: true, blob: async () => new win.Blob([]) }),
    async () => ({ ok: true, blob: async () => new win.Blob(['login'], { type: 'text/html' }) }),
  ]) {
    const el = mount(win);
    let fetchImpl = failure;
    const { push } = makeHass(el, { fetchImpl: (...args) => fetchImpl(...args) });
    push(SENSOR, 'completed', { scan_id: 's1', file_url: '/api/escl_scan/file/s1' });
    await el._downloadScan();
    assert.match(status(el).textContent, /Download failed/);
    assert.equal(el._primaryEl.textContent, 'Download PDF');
    assert.equal(el._primaryEl.disabled, false);
    push(SENSOR, 'idle');
    assert.equal(el._primaryEl.textContent, 'Download PDF');
    fetchImpl = async () => ({ ok: true, blob: async () => new win.Blob(['PDF']) });
    await el._downloadScan();
    assert.equal(el._primaryEl.textContent, 'Scan');
  }
});

test('an expired PDF offers Scan again instead of trapping the user in a failed download', async () => {
  const el = mount(boot());
  const { push } = makeHass(el, { fetchImpl: async () => jsonResponse({}, 404) });
  push(SENSOR, 'completed', { scan_id: 'expired', file_url: '/api/escl_scan/file/expired' });
  await el._downloadScan();
  assert.match(status(el).textContent, /no longer available/);
  assert.equal(el._primaryEl.textContent, 'Scan');
  push(SENSOR, 'completed', { scan_id: 'expired', pages_done: 2, file_url: '/api/escl_scan/file/expired' });
  assert.equal(el._primaryEl.textContent, 'Scan');
});

test('late download success or failure cannot overwrite another scan or target', async () => {
  for (const transition of ['scan', 'entity']) {
    for (const success of [true, false]) {
      const win = boot();
      const el = mount(win);
      let respond;
      const { push } = makeHass(el, { fetchImpl: () => new Promise(resolve => { respond = resolve; }) });
      push(SENSOR, 'completed', { scan_id: 'old', file_url: '/api/escl_scan/file/old' });
      const downloading = el._downloadScan();
      if (transition === 'entity') {
        push('sensor.other', 'idle');
        el.setConfig({ entity: 'sensor.other' });
      } else {
        push(SENSOR, 'processing', { scan_id: 'new' });
        push(SENSOR, 'completed', { scan_id: 'new', file_url: '/api/escl_scan/file/new', pages_done: 2 });
      }
      respond({ ok: success, status: success ? 200 : 500, blob: async () => new win.Blob(['PDF']) });
      await downloading;
      assert.equal(win.downloads.length, 0, 'obsolete download is discarded');
      assert.equal(el._primaryEl.textContent, transition === 'entity' ? 'Scan' : 'Download PDF');
      if (transition === 'scan') assert.match(status(el).textContent, /2 pages/);
    }
  }
});

function optionCaps() {
  return { schema_version: 1, domain: 'escl_scan', entity_id: SENSOR, status: 'fresh',
    request_options: ['source','color','dpi','duplex','page_size','width','height'], supported: {
      sources: ['Platen','Feeder'], automatic_duplex: false, manual_duplex: true,
      profiles: { Platen: { colors: ['gray'], resolutions: [300,600], maximum_region: [2550,3508],
        combinations: [{colors:['gray'],formats:['image/png'],resolutions:[300,600]}] },
      Feeder: { colors:['color','gray'],resolutions:[150,300,600], combinations: [
        {colors:['color'],formats:['application/pdf'],resolutions:[150,300]},
        {colors:['gray'],formats:['image/png'],resolutions:[600]}] } },
    } };
}
const optionsTick = () => new Promise(resolve => setTimeout(resolve, 0));
function changeOption(win, el, name, value) {
  const field = el._optionFields[name]; field.value = value;
  field.dispatchEvent(new win.Event('change')); return field;
}
test('scan options preserve complete profiles, explain DPI adjustment and reject incompatible source/color', async () => {
  const win = boot(), el = mount(win);
  const { push, calls } = makeHass(el, { capabilitiesImpl: async () => jsonResponse(optionCaps()),
    fetchImpl: async () => jsonResponse({scan_id:'chosen'}) });
  push(SENSOR, 'idle'); el._toggleOptions(true); await optionsTick();
  changeOption(win, el, 'dpi', '600');
  changeOption(win, el, 'source', 'Feeder');
  changeOption(win, el, 'color', 'color');
  assert.equal(el._settings.dpi, '300');
  assert.match(el._optionHelp.textContent, /600.*300/);
  changeOption(win, el, 'source', 'Platen');
  assert.equal(el._twoSidedEl.disabled, true);
  assert.equal(el._primaryEl.disabled, true);
  assert.match(el._optionHelp.textContent, /color mode/);
  changeOption(win, el, 'color', 'gray');
  await el._startScan();
  assert.deepEqual(JSON.parse(calls.fetch[0].init.body), {duplex:false,source:'Platen',color:'gray',dpi:300,page_size:'full',entity_id:SENSOR});
});
test('scan options keep focus and user intent across hass updates; config defaults defer until job ends', async () => {
  const win=boot(), el=mount(win);
  const { push } = makeHass(el,{capabilitiesImpl:async()=>jsonResponse(optionCaps())});
  push(SENSOR,'idle');el._toggleOptions(true);await optionsTick();
  const field=changeOption(win,el,'source','Feeder');field.focus();
  push(SENSOR,'idle');assert.equal(el.shadowRoot.activeElement,field);
  el.setConfig({title:'Renamed'});assert.equal(el._settings.source,'Feeder');
  field.dispatchEvent(new win.KeyboardEvent('keydown',{key:'Escape',bubbles:true}));
  assert.equal(el._optionsPanel.hidden,true);assert.equal(el.shadowRoot.activeElement,el._optionsButton);
  push(SENSOR,'processing',{scan_id:'active'});el.setConfig({source:'Platen'});
  assert.equal(el._settings.source,'Feeder');
  push(SENSOR,'canceled',{scan_id:'active'});assert.equal(el._settings.source,'Platen');
  el.setConfig({});assert.equal(el._settings.source,'auto');
});
test('custom scan regions cannot submit missing dimensions; options-only duplex stays compact', async () => {
  const win=boot(),el=mount(win,{duplex_in_options:true});
  const {push}=makeHass(el,{capabilitiesImpl:async()=>jsonResponse(optionCaps())});
  push(SENSOR,'idle');el._toggleOptions(true);await optionsTick();
  changeOption(win,el,'page_size','custom');assert.equal(el._primaryEl.disabled,true);
  assert.equal(el._twoSidedEl.closest('dialog'),el._optionsPanel);
  changeOption(win,el,'width','215.9');changeOption(win,el,'height','279.4');
  assert.equal(el._primaryEl.disabled,false);assert.equal(el._scanRequest().height,3300);
});

test('selected scan options can return to defaults while capabilities are unavailable', async () => {
  const win=boot(),el=mount(win,{source:'Platen'});
  const {push,calls}=makeHass(el,{fetchImpl:async()=>jsonResponse({scan_id:'defaults'})});
  push(SENSOR,'idle');await optionsTick();el._toggleOptions(true);await optionsTick();
  assert.equal(el._optionFields.source.disabled,false);
  changeOption(win,el,'source','auto');await el._startScan();
  assert.deepEqual(JSON.parse(calls.fetch[0].init.body),{duplex:false,entity_id:SENSOR});
});

// Exercise HA's public showDialog/closeDialog contract. Real browser history
// and native modal/top-layer behavior are checked on the live paired dashboard.
async function optionsHost(win, card) {
  let request;
  card.addEventListener('show-dialog', event => { request = event.detail; }, { once: true });
  card._toggleOptions(true);
  assert.ok(request);
  await request.dialogImport();
  const host = win.document.createElement(request.dialogTag);
  win.document.body.append(host);
  host.showDialog(request.dialogParams);
  return host;
}

test('HA Back closes Options once and preserves selections for the next opening', async () => {
  const win = boot(), card = mount(win);
  const host = await optionsHost(win, card);
  const settings = card._settings;
  let closed = 0;
  host.addEventListener('dialog-closed', event => {
    assert.equal(event.detail.dialog, host.localName);
    assert.equal(event.bubbles, true);
    assert.equal(event.composed, true);
    closed++;
  });
  assert.equal(card._optionsPanel.open, true);
  assert.equal(host.closeDialog(), true); // HA calls this on Back.
  host.closeDialog();
  assert.equal(closed, 1);
  assert.equal(card._optionsPanel.hidden, true);
  assert.equal(card._optionsPanel.open, false);
  assert.equal(card._optionsButton.getAttribute('aria-expanded'), 'false');
  assert.equal(card.shadowRoot.activeElement, card._optionsButton);
  card._toggleOptions(true);
  assert.equal(card._settings, settings);
  assert.equal(card._optionsPanel.open, true);
  let duplicates = 0;
  card.addEventListener('show-dialog', () => duplicates++);
  card._toggleOptions(true);
  assert.equal(duplicates, 0);
});

test('leaving and returning to a dashboard never leaves Options open inline', async () => {
  const win = boot(), card = mount(win);
  const host = await optionsHost(win, card);
  let closed = 0;
  host.addEventListener('dialog-closed', () => closed++);
  card.remove();
  win.document.body.append(card);
  assert.equal(closed, 1);
  assert.equal(card._optionsPanel.hidden, true);
  assert.equal(card._optionsPanel.open, false);
  assert.equal(card._optionsOpen, false);
  assert.equal(card._optionsButton.getAttribute('aria-expanded'), 'false');
  card._optionsButton.click();
  assert.equal(card._optionsPanel.open, true);
  assert.equal(card._optionsPanel.hidden, false);
});

test('native dismissals and Done close HA state without a delayed close dismissing a new dialog', async () => {
  const win = boot(), card = mount(win);
  const host = await optionsHost(win, card);
  let closed = 0;
  host.addEventListener('dialog-closed', () => closed++);
  card._optionsPanel.close();
  await new Promise(resolve => win.setTimeout(resolve, 5));
  assert.equal(card._optionsOpen, false);
  assert.equal(closed, 1);
  host.showDialog({ card }); // A delayed HA loader must not leave a stale dialog.
  assert.equal(host._card, null);
  await optionsHost(win, card);
  const done = [...card._optionsPanel.querySelectorAll('button')].find(b => b.textContent === 'Done');
  done.click();
  assert.equal(card._optionsPanel.hidden, true);
  card._optionsButton.click();
  await new Promise(resolve => win.setTimeout(resolve, 5));
  assert.equal(card._optionsPanel.open, true);
  assert.equal(card._optionsOpen, true);
});

test('a pending HA dialog registration cannot reopen Options after navigation', async () => {
  const win = boot(), card = mount(win);
  let request;
  card.addEventListener('show-dialog', event => { request = event.detail; });
  card._toggleOptions(true);
  card.remove();
  await request.dialogImport();
  const host = win.document.createElement(request.dialogTag);
  let closed = 0;
  host.addEventListener('dialog-closed', () => closed++);
  host.showDialog(request.dialogParams);
  assert.equal(closed, 1);
  assert.equal(host._card, null);
  win.document.body.append(card);
  assert.equal(card._optionsPanel.hidden, true);
  assert.equal(card._optionsPanel.open, false);
});

test('a restored HA history entry without live parameters closes safely', async () => {
  const win = boot(), card = mount(win);
  const host = await optionsHost(win, card);
  host.closeDialog();
  let closed = 0;
  host.addEventListener('dialog-closed', () => closed++);
  host.showDialog(null);
  assert.equal(closed, 1);
  assert.equal(host._card, null);
  assert.equal(card._optionsPanel.hidden, true);
});

// Test-only catalogs exercise localization without shipping unreviewed languages.
test('language resolution uses region, base, then English per key and plural rules', () => {
  const win = boot({
    fr: { 'card.title': 'BASE TITLE', 'status.complete': { one: 'ONE {count}', other: 'MANY {count}' } },
    'fr-ca': { 'dialog.title': 'REGIONAL OPTIONS' },
  });
  const localize = win.localize;
  const hass = { locale: { language: 'fr-CA' }, language: 'en' };
  assert.equal(localize('card.title', {}, hass), 'BASE TITLE');
  assert.equal(localize('dialog.title', {}, hass), 'REGIONAL OPTIONS');
  assert.equal(localize('action.done', {}, hass), 'Done');
  assert.equal(localize('status.complete', { count: 0 }, hass), 'ONE 0');
  assert.equal(localize('status.complete', { count: 2 }, hass), 'MANY 2');
  assert.equal(localize('card.title', {}, { language: 'fr_CA' }), 'BASE TITLE');
  assert.equal(localize('action.done', {}, { locale: { language: 'not a locale' } }), 'Done');
  assert.equal(localize('constructor', {}, hass), 'constructor');
  assert.equal(localize('missing.key', {}, hass), 'missing.key');
  const english = localize('status.complete', { count: 0 }, { language: 'xx' });
  assert.match(english, /0 pages/);
});

test('catalog references and plural placeholders are valid', () => {
  const win = boot();
  const catalogs = JSON.parse(CARD_SRC.match(/const CARD_TRANSLATIONS = (\{[\s\S]*?\});\n\/\/ END ENGLISH CATALOG/)[1]);
  assert.deepEqual(Object.keys(catalogs), ['en'], 'only reviewed English is shipped');
  for (const [key, message] of Object.entries(catalogs.en)) {
    assert.match(key, /^[a-z][a-z0-9_.]+$/);
    const forms = typeof message === 'string' ? [message] : Object.values(message);
    if (typeof message !== 'string') assert.equal(typeof message.other, 'string');
    const placeholders = forms.map(value => [...value.matchAll(/\{(\w+)\}/g)].map(m => m[1]).sort());
    for (const names of placeholders) assert.deepEqual(names, placeholders[0], key);
  }
  const refs = [...CARD_SRC.matchAll(/(?:_t|_msg|_setMessage|localize|translatedText)\('([^']+)'/g)].map(m => m[1]);
  for (const key of refs) assert.ok(Object.hasOwn(catalogs.en, key), key);
  assert.equal(win.localize('action.done'), 'Done');
});

test('Options is named, focuses its heading and describes fields without opening a keyboard', async () => {
  const win = boot(), card = mount(win);
  const host = await optionsHost(win, card);
  const heading = card._optionsPanel.querySelector('h2');
  assert.equal(card.shadowRoot.activeElement, heading);
  assert.equal(heading.autofocus, true);
  assert.equal(card._optionsButton.getAttribute('aria-label'), heading.textContent);
  for (const field of Object.values(card._optionFields)) {
    assert.equal(field.getAttribute('aria-describedby'), 'options-help');
    assert.ok(card.shadowRoot.getElementById('options-help'));
    assert.ok(field.closest('label').querySelector('[data-i18n]').textContent);
  }
  host.closeDialog();
  assert.equal(card.shadowRoot.activeElement, card._optionsButton);
});

test('translation text and placeholder data cannot create HTML', () => {
  const markup = '<img src=x onerror=alert(1)>';
  const win = boot({ fr: { 'dialog.title': markup, 'status.cancel_failed': 'ERROR {error}' } });
  const card = mount(win, { title: markup });
  card.hass = { states: {}, entities: {}, locale: { language: 'fr' } };
  card._setMessage('status.cancel_failed', { error: markup + ' $&' }, 'err');
  assert.equal(card._statusEl.textContent, 'ERROR ' + markup + ' $&');
  assert.equal(card.shadowRoot.querySelector('img'), null);
  assert.equal(card._titleEl.textContent, markup, 'custom title remains literal user data');
  assert.equal(card._optionsPanel.querySelector('h2').textContent, markup);
});

test('unchanged status and Options guidance do not repeat live-region mutations', async () => {
  const win = boot(), card = mount(win);
  card._setMessage('status.canceled', {}, 'err');
  let changed = 0;
  const observer = new win.MutationObserver(records => { changed += records.length; });
  observer.observe(card._statusEl, { childList: true, characterData: true, subtree: true });
  observer.observe(card._optionHelp, { childList: true, characterData: true, subtree: true });
  card._setMessage('status.canceled', {}, 'err');
  card._syncControls();
  card._syncControls();
  await new Promise(resolve => win.setTimeout(resolve, 0));
  observer.disconnect();
  assert.equal(changed, 0);
});

test('scan editor labels preserve wire values, defaults and optional resolution', () => {
  const win = boot(), editor = win.customElements.get(TAG).getConfigElement();
  editor.hass = { locale: { language: 'en' } };
  let changes = 0, saved;
  editor.addEventListener('config-changed', event => { changes++; saved = event.detail.config; });
  editor.setConfig({ type: 'custom:' + TAG, custom_option: 'preserved' });
  const form = editor._form;
  assert.equal(changes, 0);
  assert.equal(form.data.source, 'auto');
  assert.equal(form.data.duplex, false);
  assert.equal(form.data.dpi, undefined);
  const sources = form.schema.find(f => f.name === 'source').selector.select.options;
  assert.equal(sources.find(o => o.value === 'Platen').label, 'Glass');
  assert.equal(sources.find(o => o.value === 'auto').label, 'Automatic');
  assert.equal(form.schema.find(f => f.name === 'color').selector.select.options.find(o => o.value === 'gray').label, 'Grayscale');
  assert.match(form.computeHelper({ name: 'dpi' }), /Leave blank/);
  assert.match(form.computeHelper({ name: 'duplex_in_options' }), /compact/);
  form.dispatchEvent(new win.CustomEvent('value-changed', { detail: { value: { ...form.data, source: 'Platen', dpi: null } } }));
  assert.equal(changes, 1);
  assert.equal(saved.source, 'Platen');
  assert.equal(saved.custom_option, 'preserved');
  assert.equal(Object.hasOwn(saved, 'dpi'), false);
  assert.doesNotThrow(() => mount(win, saved));
});

test('scan language updates preserve settings, focused controls and translated status placeholders', async () => {
  const win = boot({ fr: { 'dialog.title': 'SCAN OPTIONS TEST', 'status.scanning': 'TEST{source}{progress}', 'source.feeder': 'FEEDER TEST', 'action.scan': 'SCAN TEST' } });
  const card = mount(win);
  const { hass, push, calls } = makeHass(card, { capabilitiesImpl: async () => jsonResponse(optionCaps()) });
  push(SENSOR, 'idle'); card._toggleOptions(true); await optionsTick();
  const field = changeOption(win, card, 'source', 'Feeder'); field.focus();
  card._setMessage('status.scanning', { source: card._sourceText('Feeder'), progress: card._msg('status.page', { count: 2 }), phase: '', adjustment: '', hint: '' });
  card.hass = { ...hass, locale: { language: 'fr-CA' } };
  assert.equal(card._optionFields.source, field);
  assert.equal(card.shadowRoot.activeElement, field);
  assert.equal(card._settings.source, 'Feeder');
  assert.equal(card._optionsPanel.querySelector('h2').textContent, 'SCAN OPTIONS TEST');
  assert.equal(card._primaryEl.textContent, 'SCAN TEST');
  assert.equal(card._statusEl.textContent, 'TEST (FEEDER TEST) page 2');
  assert.equal(calls.fetch.length, 0);
});

test('translated scan phases preserve protocol matching and reload guidance', () => {
  const win = boot({ fr: { 'phase.fronts': 'FRONTS TEST', 'help.wait_backs': ' WAIT TEST' } });
  const card = mount(win);
  card.hass = { states: {}, locale: { language: 'fr' } };
  card._renderScanState('processing', { duplex_mode: 'manual', scan_phase: 'fronts', pages_done: 1 });
  assert.match(card._statusEl.textContent, /FRONTS TEST/);
  assert.match(card._statusEl.textContent, /WAIT TEST/);
  card._renderScanState('processing', { duplex_mode: 'manual', scan_phase: 'backs', pages_done: 2 });
  assert.doesNotMatch(card._statusEl.textContent, /WAIT TEST/);
});


test('checked connection is independent from idle and stale evidence becomes unknown', () => {
  const win = boot();
  const el = mount(win, { entity: SENSOR });
  const { push, calls } = makeHass(el);
  const snapshot = { state: 'unreachable', checked_at: new Date().toISOString(), next_check_at: new Date(Date.now()+60_000).toISOString() };
  push(SENSOR, 'idle', { device_connection: snapshot });
  const warning = el.shadowRoot.querySelector('.connection');
  assert.equal(warning.hidden, false);
  assert.match(warning.textContent, /reach/i);
  assert.match(warning.title, /check/i);
  push(SENSOR, 'idle', { device_connection: { ...snapshot, state: 'reachable' } });
  assert.equal(warning.hidden, true);
  push(SENSOR, 'idle', { device_connection: { ...snapshot, state: 'reachable', next_check_at: '2000-01-01T00:00:00Z' } });
  assert.equal(warning.hidden, false);
  assert.match(warning.textContent, /not.*confirmed/i);
});

test('HA disconnect blocks actions and reconnect restores pushed state without submission', async () => {
  const win = boot();
  const el = mount(win, { entity: SENSOR });
  const { push, calls } = makeHass(el);
  push(SENSOR, 'processing', { scan_id: 'external', pages_done: 0 });
  el.hass = { ...el._hass, connected: false };
  assert.equal(el.shadowRoot.querySelector('.primary').disabled, true);
  assert.equal(el.shadowRoot.querySelector('.cancel').disabled, true);
  assert.match(el.shadowRoot.querySelector('.connection').textContent, /Home Assistant/);
  el.shadowRoot.querySelector('.primary').click();
  el.shadowRoot.querySelector('.cancel').click();
  assert.equal(calls.fetch.length, 0);
  push(SENSOR, 'canceled', { scan_id: 'external', pages_done: 0 });
  assert.equal(el.shadowRoot.querySelector('.primary').disabled, false);
  assert.match(el.shadowRoot.querySelector('.status').textContent, /canceled/i);
  assert.equal(calls.fetch.length, 0);
});

test('shared long errors keep device text literal and expand recovery guidance', () => {
  const win = boot();
  const el = mount(win);
  const message = 'Device could not confirm the outcome. Check the device before trying again; <img src=x onerror=alert(1)> is text, never markup.';
  el._setStatus(message, 'err');
  const node = el.shadowRoot.querySelector('.status');
  assert.equal(node.textContent, message);
  assert.equal(node.querySelector('img'), null);
  assert.ok(node.querySelector('details'));
});

test('a detached delayed start cannot overwrite a newer observed scan on return', async () => {
  const win = boot();
  const el = mount(win, { entity: SENSOR });
  let finish;
  const { push } = makeHass(el, { fetchImpl: () => new Promise(resolve => { finish = resolve; }) });
  push(SENSOR, 'idle');
  const request = el._startScan();
  await new Promise(resolve => setTimeout(resolve, 0));
  el.remove();
  win.document.body.append(el);
  push(SENSOR, 'processing', { scan_id: 'new-scan', pages_done: 2 });
  finish(jsonResponse({ scan_id: 'old-scan', source: 'Feeder' }));
  await request;
  assert.equal(el._activeScanId, 'new-scan');
  assert.match(status(el).textContent, /2/);
});

test('late back-side error cannot disable or relabel a different scan', async () => {
  const win = boot();
  const el = mount(win, { entity: SENSOR });
  let finish;
  const { push } = makeHass(el, { fetchImpl: () => new Promise(resolve => { finish = resolve; }) });
  const waiting = id => ({ scan_id: id, duplex_mode: 'manual', front_pages: 2, pages_done: 2 });
  push(SENSOR, 'awaiting-back-sides', waiting('first'));
  const request = el._scanBacks();
  push(SENSOR, 'awaiting-back-sides', waiting('second'));
  finish(jsonResponse({ message: 'Old request failed' }, 409));
  await request;
  assert.equal(el._activeScanId, 'second');
  assert.equal(el._backError, null);
  assert.doesNotMatch(status(el).textContent, /Old request/);
  assert.equal(el._resuming, null);
});


// Native host adapter: these exercise routing/lifetime, not CSS implementation.
const FEATURE = 'escl-scan-feature';
function featureFixture(win, options = {}) {
  const other = 'sensor.another_device';
  const ids = [SENSOR, other];
  const calls = [];
  const hass = {
    connected: true,
    entities: Object.fromEntries(ids.map(id => [id, { entity_id: id, platform: 'escl_scan' }])),
    states: Object.fromEntries(ids.map(id => [id, { entity_id: id, state: 'idle', attributes: {} }])),
    fetchWithAuth: async (url, init) => {
      if (url.includes('/capabilities?')) return jsonResponse({}, 404);
      calls.push({ url, init });
      return options.fetchImpl ? options.fetchImpl(url, init) : jsonResponse({ scan_id: 'native-scan', job_id: 401 });
    },
  };
  const feature = win.document.createElement(FEATURE);
  feature.setConfig({ type: 'custom:' + FEATURE });
  win.document.body.append(feature);
  feature.hass = hass;
  feature.context = { entity_id: SENSOR };
  return { feature, hass, calls, other };
}

test('native feature registers independently and edits defaults without host identity', () => {
  const win = boot();
  const F = win.customElements.get(FEATURE);
  assert.equal(F.getStubConfig().type, 'custom:' + FEATURE);
  assert.equal(F.getStubConfig().duplex, false);
  const entry = win.customCardFeatures.find(item => item.type === FEATURE);
  assert.equal(entry.configurable, true);
  const { feature, hass } = featureFixture(win);
  assert.equal(entry.isSupported(hass, { entity_id: SENSOR }), true);
  assert.equal(entry.isSupported(hass, { area_id: 'office' }), false);
  assert.equal(entry.isSupported(hass, { entity_id: 'light.lamp' }), false);
  assert.equal(entry.isSupported({ ...hass, entities: { [SENSOR]: { platform: 'unrelated' } } }, { entity_id: SENSOR }), false);
  assert.throws(() => feature.setConfig({ entity: SENSOR }), /parent card/);
  assert.throws(() => feature.setConfig({ duplex: 'yes' }));
  const editor = F.getConfigElement();
  editor.setConfig(F.getStubConfig()); editor.hass = hass;
  const form = editor.querySelector('ha-form');
  assert.ok(form.schema.some(field => field.name === 'duplex'));
  assert.ok(form.schema.every(field => !['entity', 'title'].includes(field.name)));
  let changed;
  editor.addEventListener('config-changed', event => { changed = event.detail.config; });
  form.dispatchEvent(new win.CustomEvent('value-changed', { detail: { value: { duplex: true } } }));
  assert.equal(changed.type, 'custom:' + FEATURE);
  assert.equal(changed.duplex, true);
  assert.equal(feature._workflow.shadowRoot.querySelector('ha-card'), null);
});

test('native feature supports legacy entity delivery but empty modern context stays authoritative', () => {
  const win = boot();
  const { feature, hass } = featureFixture(win);
  const legacy = win.document.createElement(FEATURE);
  legacy.setConfig({}); legacy.stateObj = hass.states[SENSOR]; legacy.hass = hass;
  win.document.body.append(legacy);
  assert.equal(legacy._workflow._config.entity, SENSOR);
  legacy.context = {};
  legacy.stateObj = hass.states[SENSOR];
  assert.equal(legacy._workflow, null);
  assert.match(legacy.shadowRoot.textContent, /Select an/);
  feature.position = 'inline';
  assert.equal(feature._workflow, null);
  assert.match(feature.shadowRoot.textContent, /Bottom/);
  feature.position = 'bottom';
  assert.equal(feature._workflow._config.entity, SENSOR);
});

test('native feature preserves local intent across state pushes and remount without starting work', () => {
  const win = boot();
  const { feature, hass, calls } = featureFixture(win);
  const workflow = feature._workflow;
  workflow._twoSidedEl.click();
  feature.hass = { ...hass };
  feature.context = { entity_id: SENSOR };
  feature.stateObj = hass.states[SENSOR];
  feature.remove(); win.document.body.append(feature);
  assert.equal(feature._workflow, workflow);
  assert.equal(workflow._twoSidedEl.checked, true);
  assert.equal(calls.length, 0);
  let bubbled = 0;
  feature.addEventListener('click', () => { bubbled++; });
  workflow._twoSidedEl.click();
  assert.equal(bubbled, 0);
});

test('native target change during submission detaches old replies and never carries intent to new device', async () => {
  const win = boot();
  let finish;
  const { feature, hass, calls, other } = featureFixture(win, {
    fetchImpl: () => new Promise(resolve => { finish = resolve; }),
  });
  const workflow = feature._workflow;

  workflow._primaryEl.click(); workflow._primaryEl.click();
  assert.equal(calls.length, 1);
  assert.equal(JSON.parse(calls[0].init.body).entity_id, SENSOR);
  feature.context = { entity_id: other };
  const next = feature._workflow;
  assert.notEqual(next, workflow);
  assert.equal(next._config.entity, other);
  assert.ok(!next._stagedFile);
  finish(jsonResponse({ scan_id: 'old-reply', job_id: 402 }));
  await new Promise(resolve => setTimeout(resolve, 0));
  assert.ok(!next._activeScanId && next._activeJobId == null);
  assert.equal(calls.length, 1);
  feature.hass = { ...hass, connected: false };
  assert.equal(next._primaryEl.disabled, true);
  feature.hass = { ...hass, connected: true };
  assert.equal(next._primaryEl.disabled, false);
});

test('native scan keeps manual backs and download on the same workflow through idle', async () => {
  const win = boot();
  const { feature, hass, calls } = featureFixture(win, { fetchImpl: async url => url.includes('/file/')
    ? { ok: true, headers: { get: () => 'application/pdf' }, blob: async () => new win.Blob(['pdf'], { type: 'application/pdf' }) }
    : jsonResponse({ ok: true }) });
  const update = (state, attrs) => {
    hass.states[SENSOR] = { entity_id: SENSOR, state, attributes: { scan_id: 'native-scan', ...attrs } };
    feature.hass = { ...hass }; feature.context = { entity_id: SENSOR };
  };
  const workflow = feature._workflow;
  update('awaiting-back-sides', { front_pages: 2, duplex_mode: 'manual', pages_done: 2 });
  assert.ok(workflow._backButton);
  workflow._backButton.click();
  await new Promise(resolve => setTimeout(resolve, 0));
  assert.equal(calls[0].url, '/api/escl_scan/scan_backs');
  assert.equal(JSON.parse(calls[0].init.body).entity_id, SENSOR);
  update('completed', { pages_done: 4, file_url: '/api/escl_scan/file/native-scan', filename: 'native.pdf' });
  update('idle', { scan_id: null });
  assert.equal(feature._workflow, workflow);
  assert.equal(workflow._primaryEl.textContent, 'Download PDF');
  workflow._primaryEl.click();
  await new Promise(resolve => setTimeout(resolve, 0));
  assert.equal(win.downloads.length, 1);
  assert.equal(workflow._primaryEl.textContent, 'Scan');
});


test('native editor excludes host identity even when an older standalone editor loaded first', () => {
  const win = boot({}, window => {
    window.customElements.define(TAG + '-editor', class extends window.HTMLElement {
      setConfig(config) { this._config = config; this._render(); }
      set hass(hass) { this._hass = hass; this._render(); }
      _render() {
        if (!this._form) { this._form = window.document.createElement('ha-form'); this.append(this._form); }
        this._form.schema = ['title','entity','duplex'].map(name => ({ name }));
      }
    });
  });
  const F = win.customElements.get(FEATURE), editor = F.getConfigElement();
  editor.setConfig(F.getStubConfig()); editor.hass = { states: {} };
  assert.equal(editor.localName, FEATURE + '-editor');
  assert.deepEqual(Array.from(editor.querySelector('ha-form').schema, field => field.name), ['duplex']);
});
