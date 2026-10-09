// Development-only isolated native hosts. No device writes or saved dashboard changes.
(async () => {
  const app = document.querySelector('home-assistant');
  app.shadowRoot.querySelector('#document-native-preview')?.remove();
  const panel = document.createElement('section'); panel.id = 'document-native-preview';
  panel.style.cssText = 'position:fixed;inset:0;z-index:10000;padding:8px;background:var(--primary-background-color);color:var(--primary-text-color);overflow:auto;box-sizing:border-box;';
  const title = document.createElement('p'); title.textContent = 'Native feature preview · simulated jobs'; panel.append(title);
  const helpers = await window.loadCardHelpers();
  const sid = 'sensor.fixture_scan', pid = 'sensor.fixture_print';
  const calls = [];
  const hass = { ...app.hass, connected: true, states: {}, entities: {
    [sid]: { entity_id: sid, platform: 'escl_scan' }, [pid]: { entity_id: pid, platform: 'ipp_print' },
  }, fetchWithAuth: async (url, init) => {
    calls.push({ url, method: init?.method || 'GET' });
    if (url.includes('/capabilities?')) {
      const entity = new URL(url, location.origin).searchParams.get('entity_id');
      const print = entity === pid;
      return new Response(JSON.stringify({ schema_version: 1, domain: print ? 'ipp_print' : 'escl_scan', entity_id: entity, status: 'fresh',
        supported: print ? { sides: ['one-sided', 'two-sided-long-edge'], copies_max: 99 } : { manual_duplex: true, automatic_duplex: false },
        request_options: print ? ['copies','sides'] : [],
      }), { headers: { 'Content-Type': 'application/json' } });
    }
    return new Response(JSON.stringify({ message: 'Preview only; no device request sent', job_may_exist: false }), { status: 400, headers: { 'Content-Type': 'application/json' } });
  } };
  const cards = [];
  for (const host of ['tile', ...(customElements.get('mushroom-template-card') ? ['custom:mushroom-template-card'] : [])]) {
    const label = document.createElement('p'); label.textContent = host === 'tile' ? 'Home Assistant Tile' : 'Mushroom Template'; panel.append(label);
    const row = document.createElement('div'); row.style.cssText = 'display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;align-items:start;'; panel.append(row);
    for (const [entity, type, name, icon] of [[sid, 'escl-scan-feature', 'Scan', 'mdi:scanner'], [pid, 'ipp-print-feature', 'Print', 'mdi:printer']]) {
      const card = helpers.createCardElement({ type: host, entity, name, primary: name, icon, hide_state: true,
        tap_action: { action: 'none' }, icon_tap_action: { action: 'none' }, features_position: 'bottom',
        grid_options: { columns: 6, rows: 'auto' }, features: [{ type: 'custom:' + type }],
      });
      row.append(card); cards.push(card);
    }
  }
  function deep(root, tag) {
    root = root.shadowRoot || root;
    const found = root.querySelector(tag); if (found) return found;
    for (const node of root.querySelectorAll('*')) if (node.shadowRoot) { const found = deep(node.shadowRoot, tag); if (found) return found; }
  }
  const push = (scan = 'idle', print = 'idle', connected = true) => {
    hass.connected = connected;
    const connection = { state: 'reachable', checked_at: new Date().toISOString(), next_check_at: new Date(Date.now() + 60000).toISOString() };
    hass.states = {
      [sid]: { entity_id: sid, state: scan, attributes: { friendly_name: 'Scan', scan_id: scan === 'idle' ? null : 'preview-scan', pages_done: 2, front_pages: 2, duplex_mode: 'manual', source: 'Feeder', device_connection: connection } },
      [pid]: { entity_id: pid, state: print, attributes: { friendly_name: 'Print', job_id: print === 'idle' ? null : 42, submitted_at: '2026-10-09T12:00:00Z', filename: 'preview.pdf', pages_done: 2, pages_total: 0, page_count_unit: 'impressions', device_connection: connection } },
    };
    cards.forEach(card => card.hass = { ...hass });
  };
  app.shadowRoot.append(panel); push();
  await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  panel._test = { cards, hass, calls, push, get workflows() {
    const workflows = cards.map(card => deep(card, 'escl-scan-feature')?._workflow || deep(card, 'ipp-print-feature')?._workflow);
    // Print's standalone compatibility fallback can read the app root. Keep fixtures isolated.
    workflows.forEach(card => { if (card) { card._getHass = () => hass; card._apiFetch = hass.fetchWithAuth; card._authedFetch = hass.fetchWithAuth; } });
    return workflows;
  } };
  return { hosts: cards.map(card => card.localName), writes: calls.filter(call => call.method !== 'GET') };
})();
