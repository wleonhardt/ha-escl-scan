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

function boot() {
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
  dom.window.eval(CARD_SRC);
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
  assert.deepEqual(JSON.parse(calls.fetch[0].init.body), { scan_id: 'manual1', reverse_back_order: false });
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

test('changing configured entity updates immediately and missing sensors clear cancel', () => {
  const win = boot();
  const el = mount(win);
  const { push } = makeHass(el);
  push(SENSOR, 'processing', { scan_id: 's1' });
  push('sensor.other', 'failed', { scan_id: 's2', error: 'jam' });
  el.setConfig({ entity: 'sensor.other' });
  assert.equal(status(el).textContent, 'Scan failed: jam');
  el.setConfig({ entity: 'sensor.missing' });
  assert.equal(status(el).textContent, 'Automatic source');
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
