// Development-only host experiment. No device API or service calls.
(() => {
  const tag = 'document-card-host-probe-v1';
  if (!customElements.get(tag)) {
    customElements.define(tag, class extends HTMLElement {
      constructor() {
        super();
        this.attachShadow({ mode: 'open' });
        this.actions = 0;
      }
      setConfig(config) { this.config = config; this.render(); }
      set context(value) { this._context = value; }
      get context() { return this._context; }
      set stateObj(value) { this._stateObj = value; }
      get entityId() { return this.context?.entity_id || this._stateObj?.entity_id; }
      render() {
        this.shadowRoot.innerHTML = `
          <style>
            :host { display: block; }
            .row { display: flex; gap: 8px; height: var(--feature-height, 42px); }
            button, label { font: inherit; font-size: 14px; box-sizing: border-box; border: 0; border-radius: var(--feature-border-radius, 12px); color: var(--primary-text-color); background: var(--secondary-background-color); }
            button { min-width: 42px; cursor: pointer; }
            .action { flex: 1; }
            label { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 0 12px; width: 100%; }
            dialog { max-width: min(320px, 80vw); color: var(--primary-text-color); background: var(--card-background-color); border: 1px solid var(--divider-color); border-radius: var(--ha-card-border-radius, 12px); }
          </style>
          <div class="row">${this.config.kind === 'intent'
            ? '<label>Two-sided<input type="checkbox" role="switch" aria-label="Two-sided host probe"></label>'
            : '<button class="action" type="button">Scan</button><button class="options" type="button" aria-label="Probe options">⋯</button>'}</div>
          <dialog><p>Host compatibility experiment. No device action is connected.</p><form method="dialog"><button>Close</button></form></dialog>`;
        this.shadowRoot.addEventListener('click', event => event.stopPropagation());
        this.shadowRoot.querySelector('.action')?.addEventListener('click', () => { this.actions++; });
        this.shadowRoot.querySelector('.options')?.addEventListener('click', () => this.shadowRoot.querySelector('dialog').showModal());
      }
    });
  }
  window.mountDocumentHostProbe = async (hass) => {
    document.getElementById('document-host-probe')?.remove();
    const panel = document.createElement('section');
    panel.id = 'document-host-probe';
    panel.style.cssText = 'position:fixed;inset:8px;z-index:10000;padding:12px;background:var(--primary-background-color);overflow:auto;display:grid;gap:12px;align-content:start';
    const close = document.createElement('button');
    close.textContent = 'Close host experiment';
    close.addEventListener('click', () => panel.remove());
    panel.append(close);
    const helpers = await window.loadCardHelpers();
    for (const type of ['tile', 'custom:mushroom-template-card']) {
      const card = helpers.createCardElement({
        type, entity: 'sensor.printer_current_scan', name: 'Scan', primary: 'Scan',
        icon: 'mdi:scanner', tap_action: { action: 'none' },
        features: ['intent', 'action'].map(kind => ({ type: `custom:${tag}`, kind })),
        features_position: 'bottom',
      });
      card.hass = hass;
      card.style.maxWidth = '183px';
      panel.append(card);
    }
    document.body.append(panel);
  };
})();
