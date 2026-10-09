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
    disconnectedCallback() {
      this._requestEpoch = (this._requestEpoch || 0) + 1;
      this._lastSig = null;
      this._clearResultTimer?.();
      this._clearActivityTimer?.();
      this._toggleOptions?.(false, false);
      this._capabilityRequest?.abort();
    }
  });
}

const FEATURE_TAG = 'escl-scan-feature';
const FEATURE_DOMAIN = 'escl_scan';
if (!customElements.get(FEATURE_TAG)) {
  customElements.define(FEATURE_TAG, class extends HTMLElement {
    connectedCallback() { this._updateFeature?.(); }
  });
}

const C = customElements.get(TAG);

// BEGIN ENGLISH CATALOG
const CARD_TRANSLATIONS = {
  "en": {
    "activity.latest": "Latest scan",
    "activity.recent": "Recent activity",
    "activity.completed": "Scan completed",
    "activity.canceled": "Canceled",
    "activity.aborted": "Failed",
    "activity.unknown": "Outcome unknown — check the printer",
    "activity.finished": "Finished {time}",
    "activity.submitted": "Submitted {time}",
    "activity.pages": { "one": "{count} page", "other": "{count} pages" },
    "activity.sheets": { "one": "{count} sheet", "other": "{count} sheets" },
    "activity.available": "Available until {time}",
    "activity.expired": "File expired. Scan again or use your saved copy.",
    "activity.missing": "File unavailable. Scan again or use your saved copy.",
    "activity.scan_note": "Only the latest completed scan is shown.",
    "activity.print_note": "Up to 10 jobs for 7 days. Documents are not saved.",
    "activity.no_scan": "No completed scan yet.",
    "activity.no_print": "No recent print activity.",
    "activity.downloaded": "PDF handed to your browser.",
    "activity.download_failed": "Could not download the PDF. Try again.",
    "feature.config": "Invalid feature configuration.",
    "feature.host_config": "Set the device and title on the parent card.",
    "feature.target": "Select an eSCL Scan sensor on this card.",
    "feature.bottom": "Set Features position to Bottom to use these controls.",
    "action.options": "Options",
    "action.two_sided": "Two-sided",
    "action.done": "Done",
    "action.canceling": "Cancelling…",
    "choice.automatic": "Automatic",
    "choice.color": "Color",
    "choice.grayscale": "Grayscale",
    "choice.device_default": "Device default",
    "choice.integration_default": "Integration default",
    "choice.long_edge": "Long edge",
    "choice.short_edge": "Short edge",
    "field.color": "Color",
    "editor.title": "Title",
    "editor.duplex_options": "Show Two-sided inside Options",
    "error.retry": "Please try again.",
    "action.scan": "Scan",
    "action.cancel": "Cancel scan",
    "action.download": "Download PDF",
    "action.starting": "Starting…",
    "action.downloading": "Downloading…",
    "action.backs": "Scan back sides",
    "accessibility.two_sided": "Two-sided scan using feeder",
    "dialog.title": "Scan options",
    "config.duplex": "Two-sided default must be true or false.",
    "config.source": "Invalid scan source.",
    "config.color": "Invalid scan color.",
    "config.dpi": "DPI must be an integer from 50 to 1200.",
    "config.page_size": "Invalid default page size.",
    "config.layout": "Options layout must be true or false.",
    "editor.entity": "Scan sensor (optional)",
    "editor.duplex": "Two-sided by default (uses feeder)",
    "editor.source": "Default source",
    "editor.color": "Default color",
    "editor.dpi": "Default resolution",
    "editor.page_size": "Default page size",
    "choice.glass": "Glass",
    "choice.feeder": "Feeder",
    "choice.full": "Full scan area",
    "choice.letter": "Letter",
    "choice.a4": "A4",
    "choice.custom": "Custom",
    "status.auto_source": "Automatic source",
    "status.auto_duplex": "Feeder · Automatic duplex",
    "status.manual_duplex": "Feeder · Two passes required",
    "status.unknown_duplex": "Feeder · may need two passes",
    "status.start_backs": "Starting back sides…",
    "status.unavailable": "Scan status unavailable",
    "status.paused": "Scanner paused — check tray/jam",
    "status.canceled": "Scan canceled",
    "help.feeder": "Uses feeder",
    "help.select_feeder": "Select feeder to scan both sides",
    "help.unavailable": "Device settings are unavailable. Scanning with existing defaults still works.",
    "help.auto_source": "Source is chosen when scanning. Available resolution depends on the selected source and color.",
    "help.next_job": "Settings apply to the next scan.",
    "error.settings_load": "Scan settings could not be loaded. Open Options and check the scanner connection.",
    "error.busy": "The scanner is busy. Wait for the current scan to finish, or cancel it before starting a new scan.",
    "error.response": "Invalid response from scan service",
    "error.backs": "Cannot scan the backs yet. Check that the scanner is idle and the back sides are loaded, then try again.",
    "error.expired": "This PDF is no longer available. Scan the document again.",
    "error.pdf": "The server did not return a PDF. Please try again.",
    "error.feeder": "Choose Feeder or Automatic for a two-sided scan.",
    "error.source": "This scanner does not advertise the selected source.",
    "error.color": "This source does not support the selected color mode. Choose another color mode.",
    "error.region": "Enter a valid custom width and height within the scanner limits.",
    "error.update": "Update the scan integration to use the selected options.",
    "field.source": "Source",
    "field.dpi": "Resolution",
    "field.page_size": "Page size",
    "field.width": "Custom width (mm)",
    "field.height": "Custom height (mm)",
    "backs.order": "Back-side sheet order",
    "backs.same": "First sheet first (same sheet order)",
    "backs.reverse": "Last sheet first (flipped stack)",
    "picker.name": "eSCL Scan",
    "picker.description": "One-tap document scan via eSCL/AirScan with live status.",
    "card.title": "Scan",
    "status.cancel_failed": "Cancel failed: {error}",
    "editor.help.title": "Leave blank to use the translated card title.",
    "editor.help.entity": "Leave blank to use the configured scanner.",
    "editor.help.duplex_in_options": "Move the Two-sided switch into Options to keep the card more compact.",
    "editor.help.dpi": "Leave blank to use the integration default. The scanner may adjust unsupported resolutions.",
    "editor.help.source": "Automatic chooses the source when scanning. Two-sided scans use the feeder.",
    "editor.help.color": "Integration default uses the color setting configured for this scanner.",
    "editor.help.page_size": "Full scan area uses the source bounds; it does not detect the paper size.",
    "status.waiting": "Waiting for scanner…{hint}",
    "status.scanning": "Scanning{phase}{source}{progress}…{adjustment}{hint}",
    "status.source": " ({source})",
    "status.page": " page {count}",
    "status.phase": " {phase}",
    "phase.fronts": "fronts",
    "phase.backs": "backs",
    "source.platen": "platen",
    "source.feeder": "feeder",
    "help.wait_backs": " Wait for the reload prompt before flipping.",
    "help.adjusted": " Using {dpi} DPI; {requested} is unavailable.",
    "status.start_failed": "Cannot start scan: {error}",
    "status.download_failed": "Download failed. {error}",
    "status.complete": {
      "one": "Scan ready ✓ ({count} page)",
      "other": "Scan ready ✓ ({count} pages)"
    },
    "status.failed": "Scan failed{reason}",
    "status.reason": ": {reason}",
    "backs.ready": {
      "one": "Fronts ready ({count} sheet). Reload with backs facing the scanner. Choose which sheet feeds first: ",
      "other": "Fronts ready ({count} sheets). Reload with backs facing the scanner. Choose which sheet feeds first: "
    },
    "choice.dpi": "{dpi} DPI",
    "help.dpi_adjusted": "{requested} DPI is unavailable for these settings; using {dpi} DPI.",
    "connection.ha_lost": "Home Assistant disconnected. Reconnecting…",
    "connection.reachable": "Device reachable",
    "connection.unreachable": "Cannot reach this device. Check its power and connection.",
    "connection.unknown": "Device connection has not been confirmed recently.",
    "connection.checked": "Last checked: {time}"
  }
};
// END ENGLISH CATALOG

// BEGIN DOCUMENT CARD CORE v4
// Canonical source: ha-escl-scan/shared/card-core.js; synchronize with tools/sync-card-core.mjs.
// Shared localization contract v1. Keep this helper identical in both cards.
// Catalogs are bundled here: no build step, translation fetch or registration wait.
class LocalizedMessage {
  constructor(key, values) { this.key = key; this.values = values; }
}
function setText(element, value) {
  if (element.textContent !== value) element.textContent = value;
}
function hasOwn(object, key) { return Object.prototype.hasOwnProperty.call(object, key); }
let lastLanguageValue, lastLanguage = 'en';
function cardLanguage(hass) {
  const value = hass?.locale?.language || hass?.language || 'en';
  if (value === lastLanguageValue) return lastLanguage;
  lastLanguageValue = value;
  try { lastLanguage = Intl.getCanonicalLocales(String(value).replace(/_/g, '-'))[0].toLowerCase(); }
  catch { lastLanguage = 'en'; }
  return lastLanguage;
}
function localize(key, values = {}, hass = document.querySelector('home-assistant')?.hass) {
  const language = cardLanguage(hass);
  for (const locale of new Set([language, language.split('-')[0], 'en'])) {
    const catalog = hasOwn(CARD_TRANSLATIONS, locale) ? CARD_TRANSLATIONS[locale] : null;
    if (!catalog || !hasOwn(catalog, key)) continue;
    let message = catalog[key];
    if (message && typeof message === 'object') {
      const category = new Intl.PluralRules(locale).select(Number(values.count));
      message = hasOwn(message, category) ? message[category] : message.other;
    }
    if (typeof message !== 'string') continue;
    return message.replace(/\{(\w+)\}/g, (token, name) => {
      if (!hasOwn(values, name)) return token;
      const value = values[name];
      return value instanceof LocalizedMessage ? localize(value.key, value.values, hass) : String(value);
    });
  }
  return key;
}
function localizeElements(root, hass) {
  for (const el of root.querySelectorAll('[data-i18n]')) {
    el.textContent = localize(el.dataset.i18n, el._i18nValues || {}, hass);
  }
  for (const el of root.querySelectorAll('[data-i18n-label]')) {
    const label = localize(el.dataset.i18nLabel, {}, hass);
    el.setAttribute('aria-label', label);
    if (el.hasAttribute('title')) el.title = label;
  }
}
function translatedText(key, values = {}, hass) {
  const span = document.createElement('span');
  span.dataset.i18n = key; span._i18nValues = values;
  span.textContent = localize(key, values, hass);
  return span;
}
C.prototype._msg = function (key, values = {}) { return new LocalizedMessage(key, values); };
C.prototype._t = function (key, values) { return localize(key, values, this._hass); };
C.prototype._setMessage = function (key, values = {}, cls = '') {
  this._setStatus(this._t(key, values), cls);
  this._statusMessage = { key, values, cls };
};
C.prototype._applyLanguage = function () {
  if (!this.shadowRoot) return false;
  const language = cardLanguage(this._hass);
  if (language === this._language) return false;
  this._language = language;
  localizeElements(this.shadowRoot, this._hass);
  if (!this._config.title) this._titleEl.textContent = this._t('card.title');
  if (this._statusMessage) {
    const { key, values, cls } = this._statusMessage;
    this._setMessage(key, values, cls);
  }
  return true;
};
// Checked connection is independent of a job's idle/running state.
C.prototype._syncConnection = function () {
  if (!this._connectionEl) return;
  const offline = this._hass?.connected === false;
  const snapshot = this._connectionSnapshot();
  const checked = Date.parse(snapshot?.checked_at);
  const next = Date.parse(snapshot?.next_check_at);
  const fresh = Number.isFinite(checked) && Number.isFinite(next) && next + 30_000 > Date.now();
  const state = fresh && ['reachable','unreachable'].includes(snapshot?.state) ? snapshot.state : 'unknown';
  this._connectionEl.hidden = !offline && (!snapshot || state === 'reachable');
  setText(this._connectionEl, this._t(offline ? 'connection.ha_lost' : 'connection.' + state));
  let time = '';
  if (Number.isFinite(checked)) {
    try { time = new Date(checked).toLocaleString(cardLanguage(this._hass)); }
    catch { time = new Date(checked).toISOString(); }
  }
  this._connectionEl.title = time ? this._t('connection.checked', { time }) : '';
};
// End shared localization helper.

// Text stays text, including device-supplied errors. Long recovery guidance expands.
function renderStatus(element, message, cls) {
  const className = 'status' + (cls ? ' ' + cls : '');
  if (typeof message === 'string' && element.textContent === message && element.className === className) return;
  element.replaceChildren();
  if (message instanceof Node) element.appendChild(message);
  else {
    const split = cls === 'err' && message.length > 100 ? message.indexOf('. ') : -1;
    if (split > 0) {
      const details = document.createElement('details');
      const summary = document.createElement('summary');
      summary.textContent = message.slice(0, split + 2);
      const recovery = document.createElement('div');
      recovery.textContent = message.slice(split + 2);
      details.append(summary, recovery);
      element.appendChild(details);
    } else element.textContent = message;
  }
  element.className = className;
}

const DOCUMENT_CARD_STYLES = `/* Shared document-card contract v1. Keep this base identical in both cards. */
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
      .options-button { margin-inline-start: auto; flex: none; width: 44px; padding: 8px; }
      .options { box-sizing: border-box; display: grid; gap: 12px; width: min(400px, calc(100vw - 32px)); max-height: 85vh; overflow: auto; padding: 20px; border: 1px solid var(--divider-color); border-radius: var(--ha-card-border-radius, 12px); color: var(--primary-text-color); background: var(--card-background-color); }
      .options:not([open]) { display: none; }
      .options::backdrop { background: rgba(0, 0, 0, .45); }
      .options h2 { font-size: 20px; margin: 0 0 4px; }
      .option-field { display: grid; gap: 4px; min-width: 0; font-size: 14px; }
      .option-field select, .option-field input { box-sizing: border-box; width: 100%; min-width: 0; min-height: 44px; padding: 8px; font: inherit; color: var(--primary-text-color); background: var(--card-background-color); border: 1px solid var(--divider-color); border-radius: 8px; }
      .options-help { color: var(--secondary-text-color); font-size: 12px; line-height: 18px; overflow-wrap: anywhere; }
      .warning { color: var(--warning-color, var(--primary-text-color)); font-size: 14px; line-height: 20px; overflow-wrap: anywhere; }
      .warning:empty { display: none; }
      .activity { font-size: 14px; line-height: 20px; min-width: 0; }
      .activity > summary { min-height: 44px; align-content: center; cursor: pointer; }
      .activity-list { display: grid; gap: 12px; padding: 4px 0 8px; }
      .activity-item { display: grid; gap: 4px; overflow-wrap: anywhere; }
      .activity-item + .activity-item { border-top: 1px solid var(--divider-color); padding-top: 12px; }
      .activity-meta, .activity-note { color: var(--secondary-text-color); overflow-wrap: anywhere; }
      .activity-download { margin-top: 4px; }
      .activity-feedback { color: var(--secondary-text-color); overflow-wrap: anywhere; }
      .activity-feedback.err { color: var(--error-color); }
      /* End shared document-card base. */`;

// Shared document-card option helpers. Keep this small block identical in both cards.
function optionChoices(select, choices, value) {
  const signature = JSON.stringify(choices);
  if (select.dataset.choices !== signature) {
    select.replaceChildren(...choices.map(([key, label, disabled]) => {
      const option = document.createElement('option');
      option.value = String(key); option.textContent = label; option.disabled = !!disabled;
      return option;
    }));
    select.dataset.choices = signature;
  }
  select.value = String(value);
}
function addOptionField(panel, key, label, type = 'select') {
  const wrapper = document.createElement('label');
  wrapper.className = 'option-field';
  const caption = translatedText(label, {}, panel._hass); wrapper.append(caption);
  const input = document.createElement(type === 'select' ? 'select' : 'input');
  input.dataset.option = key;
  input.setAttribute('aria-describedby', 'options-help');
  if (type !== 'select') input.type = type;
  wrapper.append(input); panel.append(wrapper);
  return input;
}
// Let HA own Back navigation, including the Android app's dialog handling.
// The native panel stays in the card's shadow root to retain its theme/styles.
const OPTIONS_TAG = `${TAG}-options-dialog`;
if (!customElements.get(OPTIONS_TAG)) {
  customElements.define(OPTIONS_TAG, class extends HTMLElement {
    showDialog(params) {
      this._open = true;
      const card = params?.card;
      this._card = card;
      // Older HA history entries cannot serialize the live card reference.
      if (!card) { this.closeDialog(); return; }
      card._optionsDialog = this;
      // HA may finish loading the host after navigation or a quick dismissal.
      if (!card.isConnected || !card._optionsOpen) this.closeDialog();
    }
    closeDialog() {
      if (!this._open) return true;
      this._open = false;
      const card = this._card;
      this._card = null;
      if (card) {
        card._optionsDialog = null;
        card._toggleOptions(false, card.isConnected);
      }
      this.dispatchEvent(new CustomEvent('dialog-closed', {
        bubbles: true, composed: true, detail: { dialog: OPTIONS_TAG },
      }));
      return true;
    }
  });
}
C.prototype._toggleOptions = function (open, restoreFocus = true) {
  if (!this._optionsPanel || (open && (!this.isConnected || this._optionsOpen))) return;
  const wasOpen = this._optionsOpen;
  this._optionsOpen = open;
  this._optionsPanel.hidden = !open;
  this._optionsButton.setAttribute('aria-expanded', String(open));
  if (open) {
    this._refreshOptions();
    this._optionsButton.focus();
    this.dispatchEvent(new CustomEvent('show-dialog', {
      bubbles: true, composed: true,
      detail: {
        dialogTag: OPTIONS_TAG, dialogImport: () => Promise.resolve(),
        dialogParams: { card: this },
      },
    }));
    if (!this._optionsPanel.open) this._optionsPanel.showModal?.();
    this._optionsPanel.querySelector('h2')?.focus();
  } else {
    this._optionsPanel.close?.();
    this._optionsDialog?.closeDialog();
    if (wasOpen && restoreFocus && this.isConnected) this._optionsButton.focus();
  }
};
C.prototype._createOptionsPanel = function () {
  this._optionsButton = this.shadowRoot.querySelector('.options-button');
  this._optionsButton[Symbol.for('HA focus target')] = true;
  const panel = document.createElement('dialog');
  panel._hass = this._hass;
  panel.className = 'options'; panel.id = 'options'; panel.hidden = true;
  panel.setAttribute('aria-labelledby', 'options-heading');
  const heading = document.createElement('h2'); heading.id = 'options-heading'; heading.tabIndex = -1; heading.autofocus = true;
  heading.dataset.i18n = 'dialog.title'; heading.textContent = this._t('dialog.title');
  panel.append(heading); this.shadowRoot.append(panel);
  panel.addEventListener('cancel', event => { event.preventDefault(); this._toggleOptions(false); });
  // Native dismissals can close the panel without going through our buttons.
  panel.addEventListener('close', () => {
    if (!panel.open) this._toggleOptions(false);
  });
  this._optionsPanel = panel;
  this._optionsButton.addEventListener('click', () => this._toggleOptions(!this._optionsOpen));
  panel.addEventListener('keydown', event => {
    if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); this._toggleOptions(false); }
  });
  this._optionHelp = document.createElement('div');
  this._optionHelp.id = 'options-help'; this._optionHelp.className = 'options-help'; this._optionHelp.setAttribute('aria-live', 'polite');
  return panel;
};
C.prototype._finishOptionsPanel = function () {
  this._optionsPanel.append(this._optionHelp);
  const done = document.createElement('button'); done.type = 'button'; done.dataset.i18n = 'action.done'; done.textContent = this._t('action.done');
  done.addEventListener('click', () => this._toggleOptions(false));
  this._optionsPanel.append(done);
};
// Native hosts own identity/surface; the existing card still owns every workflow.
const DOCUMENT_FEATURE_STYLES = `
  :host { height: auto; min-width: 0; }
  .feature-body { display: flex; flex-direction: column; gap: 8px; min-width: 0; color: var(--primary-text-color); container-type: inline-size; }
  .feature-body .actions { display: flex; align-items: stretch; gap: 8px; }
  .feature-body .primary, .feature-body .cancel { flex: 1; width: auto; min-width: 0; }
  .feature-body button { border-radius: var(--feature-border-radius, 12px); min-height: max(44px, var(--feature-height, 42px)); }
  .feature-body .options-button { margin: 0; }
  /* Allow a two-line primary label on narrow half-width mobile cards. */
  @container (max-width: 150px) { .feature-body .actions { min-height: 56px; } }
`;
C.prototype._configureFeatureView = function () {
  if (!this._featureMode) return;
  this._card.classList.add('feature-body');
  this.shadowRoot.querySelector('.header').hidden = true;
  this.shadowRoot.querySelector('.actions').append(this._optionsButton);
};

function activityDate(value) {
  if (typeof value !== 'string' || value.length > 64) return null;
  const time = Date.parse(value);
  return Number.isFinite(time) ? time : null;
}
const ACTIVITY_OUTCOME = { completed: 'activity.completed', canceled: 'activity.canceled', aborted: 'activity.aborted', unknown: 'activity.unknown' };
const ACTIVITY_AVAILABILITY = { available: 'activity.available', expired: 'activity.expired', missing: 'activity.missing' };
function documentActivity(attrs, scan) {
  const field = scan ? 'latest_scan' : 'recent_activity';
  const raw = attrs?.[field];
  const values = scan ? [raw] : Array.isArray(raw) ? raw.slice(0, 10) : [];
  const records = [];
  for (const value of values) {
    if (!value || typeof value !== 'object' || typeof value.filename !== 'string' || value.filename.length > 160) continue;
    const expires = activityDate(value.expires_at), finished = activityDate(value.finished_at);
    const submitted = activityDate(value.submitted_at);
    if (expires === null || (scan ? finished === null : finished === null && submitted === null)) continue;
    let key, availability, url = null;
    if (scan) {
      if (typeof value.scan_id !== 'string' || !/^[a-f0-9]{12}$/.test(value.scan_id)
          || !['available', 'expired', 'missing'].includes(value.availability)) continue;
      key = value.scan_id;
      availability = expires <= Date.now() ? 'expired' : value.availability;
      if (availability === 'available' && value.file_url === `/api/escl_scan/file/${key}`) url = value.file_url;
      else if (availability === 'available') availability = 'missing';
    } else {
      if (!Number.isInteger(value.job_id) || value.job_id < 1 || submitted === null
          || !['completed', 'canceled', 'aborted', 'unknown'].includes(value.state) || expires <= Date.now()) continue;
      key = `${value.job_id}/${value.submitted_at}`;
    }
    records.push({ key, scanId: scan ? key : null, filename: value.filename, url,
      availability, expires, date: finished ?? submitted, finished: finished !== null,
      state: scan ? 'completed' : value.state,
      pages: Number.isInteger(value.pages_done) && value.pages_done >= 0 ? value.pages_done : null,
      unit: value.progress_unit === 'sheets' ? 'sheets' : 'pages' });
  }
  return { present: !!attrs && hasOwn(attrs, field), records };
}
C.prototype._activitySensor = function () {
  if (FEATURE_DOMAIN === 'escl_scan') return this._scanState();
  try { return this._hass?.states?.[this._sensorId()]; } catch { return null; }
};
C.prototype._activityTime = function (time) {
  try {
    return new Intl.DateTimeFormat(cardLanguage(this._hass), {
      dateStyle: 'medium', timeStyle: 'short', timeZone: this._hass?.config?.time_zone,
    }).format(time);
  } catch { return new Date(time).toLocaleString(); }
};
C.prototype._clearActivityTimer = function () {
  clearTimeout(this._activityTimer);
  this._activityTimer = null;
};
C.prototype._syncActivity = function () {
  if (!this._card) return;
  const scan = FEATURE_DOMAIN === 'escl_scan';
  const sensor = this._activitySensor(), entity = sensor?.entity_id || null;
  const data = documentActivity(sensor?.attributes, scan);
  if (!this._activityEl) {
    const details = document.createElement('details'); details.className = 'activity';
    const summary = document.createElement('summary');
    summary.textContent = this._t(scan ? 'activity.latest' : 'activity.recent');
    this._activityList = document.createElement('div'); this._activityList.className = 'activity-list';
    this._activityNote = document.createElement('div'); this._activityNote.className = 'activity-note';
    this._activityFeedback = document.createElement('div'); this._activityFeedback.className = 'activity-feedback';
    this._activityFeedback.setAttribute('aria-live', 'polite');
    details.append(summary, this._activityList, this._activityNote, this._activityFeedback);
    this._card.append(details); this._activityEl = details;
  }
  if (entity !== this._activityEntity) {
    this._activityEntity = entity; this._activityEl.open = false;
    this._activityMessage = null; this._expiredActivityId = null; this._historyDownload = null;
  }
  this._activityEl.hidden = !data.present;
  const records = data.records.map(record => record.key === this._expiredActivityId
    ? { ...record, availability: 'expired', url: null } : record);
  this._activityRecords = records;
  if (scan && this._completedScan && this._completedScan.scanId === records[0]?.key && !records[0].url) {
    this._downloadedScanId = this._completedScan.scanId;
    this._completedScan = null;
    this._setStatus('');
  }
  const signature = JSON.stringify([entity, cardLanguage(this._hass), this._hass?.config?.time_zone, records]);
  if (signature !== this._activitySignature) {
    this._activitySignature = signature;
    const hadFocus = this._activityList.contains(this.shadowRoot.activeElement);
    this._activityList.replaceChildren(); this._activityDownloadButton = null;
    this._activityEl.querySelector('summary').textContent = this._t(scan ? 'activity.latest' : 'activity.recent');
    for (const record of records) {
      const item = document.createElement('div'); item.className = 'activity-item';
      const title = document.createElement('div'); title.textContent = record.filename;
      const outcome = document.createElement('div');
      outcome.textContent = this._t(ACTIVITY_OUTCOME[record.state])
        + (record.pages === null ? '' : ' · ' + this._t(record.unit === 'sheets' ? 'activity.sheets' : 'activity.pages', { count: record.pages }));
      const time = document.createElement('time'); time.className = 'activity-meta';
      time.dateTime = new Date(record.date).toISOString();
      time.textContent = this._t(record.finished ? 'activity.finished' : 'activity.submitted', { time: this._activityTime(record.date) });
      item.append(title, outcome, time);
      if (scan) {
        const help = document.createElement('div'); help.className = 'activity-meta';
        help.textContent = this._t(ACTIVITY_AVAILABILITY[record.availability], { time: this._activityTime(record.expires) });
        item.append(help);
        if (record.url) {
          const button = document.createElement('button'); button.type = 'button'; button.className = 'activity-download';
          button.addEventListener('click', () => this._downloadLatest(record));
          item.append(button); this._activityDownloadButton = button;
        }
      }
      this._activityList.append(item);
    }
    this._activityNote.textContent = this._t(records.length ? (scan ? 'activity.scan_note' : 'activity.print_note')
      : (scan ? 'activity.no_scan' : 'activity.no_print'));
    if (hadFocus) this._activityEl.querySelector('summary').focus();
  }
  const pending = this._historyDownload?.record.key === records[0]?.key;
  if (this._activityDownloadButton) {
    this._activityDownloadButton.disabled = pending || !!this._downloadRequest || this._hass?.connected === false;
    this._activityDownloadButton.textContent = this._t(pending ? 'action.downloading' : 'action.download');
  }
  const message = this._activityMessage?.key === records[0]?.key ? this._activityMessage : null;
  setText(this._activityFeedback, message ? this._t(message.message) : '');
  this._activityFeedback.classList.toggle('err', !!message?.error);
  this._clearActivityTimer();
  const next = Math.min(...records.map(r => r.expires).filter(time => time > Date.now()));
  if (this.isConnected && Number.isFinite(next)) {
    this._activityTimer = setTimeout(() => this._syncActivity(), Math.min(86_400_000, Math.max(1, next - Date.now())));
  }
};

async function downloadScanPdf(owner, result, isCurrent) {
  const response = await owner._apiFetch(result.url);
  if (!isCurrent()) return 'abandoned';
  if (response.status === 404 || response.status === 410) return 'expired';
  if (!response.ok) throw new Error(owner._t('error.retry'));
  const blob = await response.blob();
  if (!isCurrent()) return 'abandoned';
  if (!blob.size || (blob.type && !['application/pdf', 'application/octet-stream'].includes(blob.type))) {
    throw new Error(owner._t('error.pdf'));
  }
  const url = URL.createObjectURL(blob), link = document.createElement('a');
  link.href = url; link.download = result.filename; link.hidden = true;
  document.body.appendChild(link);
  try { link.click(); } finally { link.remove(); setTimeout(() => URL.revokeObjectURL(url), 60_000); }
  return 'downloaded';
}
C.prototype._downloadLatest = async function (record) {
  if (!record.url || this._historyDownload || this._downloadRequest || this._hass?.connected === false) return;
  const token = { record, entity: this._activityEntity, epoch: this._requestEpoch || 0 };
  const current = () => this.isConnected && this._historyDownload === token
    && this._activityEntity === token.entity && (this._requestEpoch || 0) === token.epoch
    && this._activityRecords?.[0]?.key === record.key;
  this._historyDownload = token; this._activityMessage = null; this._syncActivity();
  try {
    const outcome = await downloadScanPdf(this, record, current);
    if (!current() || outcome === 'abandoned') return;
    if (outcome === 'expired') this._expiredActivityId = record.key;
    else if (this._completedScan?.scanId === record.scanId) {
      this._completedScan = null; this._downloadedScanId = record.scanId; this._setStatus('');
    }
    this._activityMessage = { key: record.key, message: outcome === 'expired' ? 'activity.expired' : 'activity.downloaded' };
  } catch {
    if (current()) this._activityMessage = { key: record.key, message: 'activity.download_failed', error: true };
  } finally {
    if (this._historyDownload === token) this._historyDownload = null;
    this._syncActivity(); this._syncControls();
  }
};

function supportsDocumentFeature(hass, context) {
  const id = context?.entity_id;
  if (typeof id !== 'string' || !id.startsWith('sensor.')) return false;
  const registered = hass?.entities?.[id];
  if (registered?.platform) return registered.platform === FEATURE_DOMAIN;
  // Older frontends can omit the registry; require the integration's enum shape.
  const attrs = hass?.states?.[id]?.attributes;
  return !!attrs && hasOwn(attrs, FEATURE_DOMAIN === 'escl_scan' ? 'scan_id' : 'job_id')
    && Array.isArray(attrs.options) && attrs.options.includes('processing-stopped')
    && attrs.options.includes(FEATURE_DOMAIN === 'escl_scan' ? 'awaiting-back-sides' : 'pending-held');
}

function preserveDocumentElements() {
  // A late scoped-registry polyfill can replace window.customElements after
  // this module has run. Native elements still exist, but HA's new registry
  // cannot find them. Keep the original constructors (and mounted workflows).
  const key = Symbol.for(TAG + '.element-registration');
  const tags = [TAG, FEATURE_TAG, TAG + '-editor', FEATURE_TAG + '-editor', OPTIONS_TAG];
  const definitions = tags.map(tag => [tag, customElements.get(tag)]);
  if (window[key]) {
    window[key].definitions = definitions;
    window[key].restore();
    return;
  }
  const state = { registry: customElements, definitions };
  state.restore = () => {
    const registry = window.customElements;
    if (registry === state.registry) return;
    for (const [tag, constructor] of state.definitions) {
      if (constructor && !registry.get(tag)) registry.define(tag, constructor);
    }
    state.registry = registry;
  };
  window[key] = state;
  // Capture script loads, including resources loaded after a slow first visit.
  // Normal loads cost only an identity check; no ongoing DOM scan or polling.
  document.addEventListener('load', state.restore, true);
  window.addEventListener('load', state.restore);
  window.addEventListener('pageshow', state.restore);
  window.addEventListener('location-changed', state.restore);
  customElements.whenDefined('home-assistant').then(state.restore);
}

function registerDocumentFeature() {
  const F = customElements.get(FEATURE_TAG);
  F.getStubConfig = () => ({ type: 'custom:' + FEATURE_TAG, duplex: false });
  const editorTag = FEATURE_TAG + '-editor';
  if (!customElements.get(editorTag)) {
    // Own tag and filtering also work when an older standalone editor loaded first.
    const Editor = customElements.get(TAG + '-editor');
    customElements.define(editorTag, class extends Editor {
      _render() {
        super._render();
        this._form.schema = this._form.schema.filter(field => !['title', 'entity'].includes(field.name));
      }
    });
  }
  F.getConfigElement = () => document.createElement(editorTag);
  F.prototype._t = C.prototype._t;
  F.prototype.setConfig = function (config) {
    if (!config || typeof config !== 'object') throw new Error(this._t('feature.config'));
    if (config.entity || config.title) throw new Error(this._t('feature.host_config'));
    C.prototype._validateConfig.call(this, config);
    this._config = { ...config };
    this._configRevision = (this._configRevision || 0) + 1;
    this._updateFeature();
  };
  for (const property of ['hass', 'context', 'stateObj', 'position']) {
    Object.defineProperty(F.prototype, property, {
      get() { return this['_' + property]; },
      set(value) {
        this['_' + property] = value;
        if (property === 'context') this._hasContext = true;
        this._updateFeature();
      },
      configurable: true,
    });
  }
  F.prototype._updateFeature = function () {
    if (!this._config || !this._hass) return;
    if (!this.shadowRoot) {
      const root = this.attachShadow({ mode: 'open' });
      const style = document.createElement('style');
      style.textContent = ':host { display: block; min-width: 0; } .guidance { font-size: 14px; line-height: 20px; color: var(--secondary-text-color); overflow-wrap: anywhere; }';
      this._container = document.createElement('div');
      root.append(style, this._container);
      // Control gestures must not also invoke the host's tap/hold/double action.
      for (const type of ['click', 'dblclick', 'pointerdown', 'pointerup', 'mousedown', 'mouseup', 'touchstart', 'touchend', 'keydown', 'keyup', 'action']) {
        root.addEventListener(type, event => event.stopPropagation());
      }
    }
    const context = this._hasContext ? this._context : this._stateObj;
    const entity = context?.entity_id;
    const supported = this._position !== 'inline' && supportsDocumentFeature(this._hass, context);
    if (!supported) {
      this._workflow?.remove();
      this._workflow = null;
      this._entity = null;
      this._container.className = 'guidance';
      this._container.textContent = this._t(this._position === 'inline' ? 'feature.bottom' : 'feature.target');
      return;
    }
    if (this._entity !== entity || !this._workflow) {
      this._workflow?.remove();
      this._workflow = document.createElement(TAG);
      this._workflow._featureMode = true;
      this._entity = entity;
      this._appliedRevision = null;
      this._container.className = '';
      this._container.replaceChildren();
    }
    if (this._appliedRevision !== this._configRevision) {
      this._workflow.setConfig({ ...this._config, type: 'custom:' + TAG, entity });
      this._appliedRevision = this._configRevision;
    }
    this._workflow.hass = this._hass;
    if (!this._workflow.parentNode) this._container.append(this._workflow);
  };
  window.customCardFeatures ||= [];
  if (!window.customCardFeatures.some(feature => feature.type === FEATURE_TAG)) {
    window.customCardFeatures.push({ type: FEATURE_TAG, name: localize('picker.name'), isSupported: supportsDocumentFeature, configurable: true });
  }
  preserveDocumentElements();
}
// END DOCUMENT CARD CORE v4


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

C.prototype._validateConfig = function (config) {
  if (config?.duplex !== undefined && typeof config.duplex !== 'boolean') {
    throw new Error(this._t('config.duplex'));
  }
  if (config?.source !== undefined && !['auto','Platen','Feeder'].includes(config.source)) throw new Error(this._t('config.source'));
  if (config?.color !== undefined && !['default','color','gray'].includes(config.color)) throw new Error(this._t('config.color'));
  if (config?.dpi !== undefined && (!Number.isInteger(config.dpi) || config.dpi < 50 || config.dpi > 1200)) throw new Error(this._t('config.dpi'));
  if (config?.page_size !== undefined && !['full','letter','a4'].includes(config.page_size)) throw new Error(this._t('config.page_size'));
  if (config?.duplex_in_options !== undefined && typeof config.duplex_in_options !== 'boolean') throw new Error(this._t('config.layout'));
};
C.prototype.setConfig = function (config) {
  this._validateConfig(config);
  const previousConfig = this._config;
  const previousDefault = this._config?.duplex;
  const previousEntity = this._config?.entity;
  this._config = Object.assign({ duplex: false, source: 'auto', color: 'default', dpi: 'default', page_size: 'full' }, config || {});
  if (this._duplex === undefined || previousDefault !== this._config.duplex) {
    if (this._busy || this._activeScanId) this._resetDuplex = true;
    else this._duplex = this._config.duplex;
  }
  this._settings ||= { source: 'auto', color: 'default', dpi: 'default', page_size: 'full' };
  for (const key of ['source', 'color', 'dpi', 'page_size']) {
    if (previousConfig?.[key] !== this._config[key]) {
      (this._pendingSettings ||= {})[key] = this._config[key];
    }
  }
  this._render();
  // _render() no-ops after the first call, so apply title changes (e.g. the
  // dashboard editor's live preview) directly to the already-rendered node.
  if (this._titleEl) this._titleEl.textContent = this._config.title || this._t('card.title');
  if (previousEntity !== this._config.entity) {
    this._lastSig = null;
    this._onHass();
  }
  this._syncControls();
};

Object.defineProperty(C.prototype, 'hass', {
  set(hass) {
    const connectionChanged = this._hass?.connected !== hass?.connected;
    this._hass = hass;
    // Lovelace pushes a fresh hass object on every state change. Drive all
    // progress rendering from here by diffing the scan sensor — no
    // subscribeEvents (which streamed every entity's changes to the browser
    // and raced the initial snapshot), and the card now also reflects scans
    // started from another device.
    const languageChanged = this._applyLanguage();
    this._onHass();
    if (languageChanged || connectionChanged) this._syncControls();
    else this._syncConnection();
  },
  get() { return this._hass; },
  configurable: true,
});

C.prototype.getCardSize = function () { return 3; };
C.prototype.getGridOptions = function () { return { columns: 6, rows: 'auto', min_columns: 6, min_rows: 4 }; };

// Dashboard picker support: a default config and a visual editor built on
// HA's own <ha-form>, so the card is configurable without YAML.
C.getStubConfig = function (hass) { return { title: localize('card.title', {}, hass) }; };
C.getConfigElement = function () { return document.createElement(TAG + '-editor'); };

if (!customElements.get(TAG + '-editor')) {
  customElements.define(TAG + '-editor', class extends HTMLElement {
    setConfig(config) { this._config = config || {}; this._render(); }
    set hass(hass) { this._hass = hass; if (this._form) this._render(); }
    _render() {
      if (!this._form) {
        this._form = document.createElement('ha-form');
        this._form.addEventListener('value-changed', event => {
          event.stopPropagation();
          const config = { ...this._config, ...event.detail.value };
          if (!config.entity) delete config.entity;
          if (!config.title) delete config.title;
          if (config.dpi == null || config.dpi === '') delete config.dpi;
          this._config = config;
          this.dispatchEvent(new CustomEvent('config-changed', { detail: { config }, bubbles: true, composed: true }));
        });
        this.append(this._form);
      }
      const language = cardLanguage(this._hass);
      if (language !== this._language) {
        this._language = language;
        const t = key => localize(key, {}, this._hass);
        const choices = entries => entries.map(([value, key]) => ({ value, label: t(key) }));
        this._form.schema = [
          { name: 'title', selector: { text: {} } },
          { name: 'entity', selector: { entity: { domain: 'sensor', integration: 'escl_scan' } } },
          { name: 'duplex', selector: { boolean: {} } },
          { name: 'duplex_in_options', selector: { boolean: {} } },
          { name: 'source', selector: { select: { options: choices([['auto','choice.automatic'],['Feeder','choice.feeder'],['Platen','choice.glass']]) } } },
          { name: 'color', selector: { select: { options: choices([['default','choice.integration_default'],['color','choice.color'],['gray','choice.grayscale']]) } } },
          { name: 'dpi', selector: { number: { min: 50, max: 1200, mode: 'box' } } },
          { name: 'page_size', selector: { select: { options: choices([['full','choice.full'],['letter','choice.letter'],['a4','choice.a4']]) } } },
        ];
        const labels = {"title": "editor.title", "entity": "editor.entity", "duplex": "editor.duplex", "duplex_in_options": "editor.duplex_options", "source": "editor.source", "color": "editor.color", "dpi": "editor.dpi", "page_size": "editor.page_size"};
        this._form.computeLabel = field => t(labels[field.name]);
        this._form.computeHelper = field => {
          const key = 'editor.help.' + field.name;
          const help = t(key); return help === key ? '' : help;
        };
      }
      this._form.hass = this._hass;
      this._form.data = { ...{ duplex: false, duplex_in_options: false, source: 'auto', color: 'default', page_size: 'full' }, ...this._config };
    }
  });
}

C.prototype._render = function () {
  if (this._rendered) return;
  const root = this.attachShadow({ mode: 'open' });
  const shell = this._featureMode ? 'div' : 'ha-card';
  root.innerHTML = `
    <style>
      ${DOCUMENT_CARD_STYLES}
      ${this._featureMode ? DOCUMENT_FEATURE_STYLES : ''}
      .toggle { display: grid; grid-template-columns: minmax(0, 1fr) auto; grid-template-rows: minmax(44px, auto) auto; align-items: center; column-gap: 8px; font-size: 14px; line-height: 20px; cursor: pointer; }
      .toggle small { grid-column: 1 / -1; color: var(--secondary-text-color); font-size: 14px; line-height: 20px; overflow-wrap: anywhere; }
      .two-sided { appearance: none; position: relative; margin: 0; width: 36px; height: 22px; flex: none; border-radius: 12px; background: var(--disabled-text-color); cursor: pointer; }
      .two-sided::before { content: ''; position: absolute; width: 16px; height: 16px; left: 3px; top: 3px; border-radius: 50%; background: var(--card-background-color); }
      .two-sided:checked { background: var(--primary-color); }
      .two-sided:checked::before { left: 17px; }
      .two-sided:disabled { opacity: .5; cursor: default; }
      .status select { display: block; width: 100%; min-height: 44px; margin: 8px 0; padding: 4px; color: var(--primary-text-color); background: var(--card-background-color); border: 1px solid var(--divider-color); border-radius: 8px; }
      .status button { width: 100%; margin-top: 4px; }
    </style>
    <${shell} class="document-body">
      <div class="header"><ha-icon class="icon" icon="mdi:scanner" aria-hidden="true"></ha-icon><div class="title"></div><button class="options-button" type="button" aria-expanded="false" aria-controls="options" data-i18n-label="dialog.title" title=""><ha-icon icon="mdi:tune" aria-hidden="true"></ha-icon></button></div>
      <div class="status" aria-live="polite" aria-atomic="true"></div>
      <div class="connection warning" aria-live="polite" hidden></div>
      <div class="controls">
        <label class="toggle"><span data-i18n="action.two_sided"></span><input class="two-sided" type="checkbox" role="switch" data-i18n-label="accessibility.two_sided" aria-describedby="feeder-hint"><small id="feeder-hint" data-i18n="help.feeder"></small></label>
      </div>
      <div class="actions">
        <button class="primary" type="button"></button>
        <button class="cancel" type="button" data-i18n="action.cancel"></button>
      </div>
    </${shell}>
  `;
  this._card = root.querySelector('.document-body');
  this._titleEl = root.querySelector('.title');
  this._statusEl = root.querySelector('.status');
  this._connectionEl = root.querySelector('.connection');
  this._cancelEl = root.querySelector('.cancel');
  this._primaryEl = root.querySelector('.primary');
  this._twoSidedEl = root.querySelector('.two-sided');
  this._titleEl.textContent = this._config.title || this._t('card.title');
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
  this._installOptions();
  this._configureFeatureView();
  this._rendered = true;
  this._syncControls();
  this._onHass();
};

C.prototype._syncControls = function () {
  if (!this._primaryEl) return;
  this._applyLanguage();
  this._syncConnection();
  const offline = this._hass?.connected === false;
  this._cancelEl.disabled = offline;
  if (this._backButton) this._backButton.disabled = offline || !!this._resuming;
  if (this._backOrderEl) this._backOrderEl.disabled = offline || !!this._resuming;
  const locked = !!this._busy || !!this._activeScanId;
  if (!locked && this._pendingSettings) { Object.assign(this._settings, this._pendingSettings); this._pendingSettings = null; }
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
  this._primaryEl.disabled = locked || !!downloading || offline;
  this._primaryEl.hidden = !!this._showCancel;
  this._primaryEl.textContent = this._busy ? this._t('action.starting') : downloading ? this._t('action.downloading')
    : this._completedScan ? this._t('action.download') : this._t('action.scan');
  this._syncOptions(locked || !!this._completedScan || offline);
  if (!locked && !this._completedScan && this._settingsError) this._primaryEl.disabled = true;
  if (this._showingIdle) setText(this._statusEl, this._idleStatus());
  this._syncActivity();
};

C.prototype._idleStatus = function () {
  if (!this._duplex) return this._settings?.source === 'Platen' ? this._t('choice.glass')
    : this._settings?.source === 'Feeder' ? this._t('choice.feeder') : this._t('status.auto_source');
  const caps = this._capabilities;
  if (caps?.expires > Date.now()) {
    if (caps.automatic === true) return this._t('status.auto_duplex');
    if (caps.automatic === false && caps.manual === true) return this._t('status.manual_duplex');
  }
  return this._t('status.unknown_duplex');
};

// Read only when the two-sided option is relevant. Cache per selected sensor,
// coalesce hass pushes, and retry unknown/older backends without blocking Scan.
C.prototype._refreshCapabilities = function () {
  if (this._hass?.connected === false) return Promise.resolve();
  if (this._capabilityRequest && !this._capabilityRequest.signal.aborted) return this._capabilityTask;
  this._capabilityTask = this._fetchCapabilities();
  return this._capabilityTask;
};
C.prototype._fetchCapabilities = async function () {
  const entity = this._scanState()?.entity_id;
  if (!this.isConnected || (!this._duplex && !this._optionsOpen && !this._hasExplicitSettings()) || !entity || !this._hass
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
    caps.body = body;
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
  this._statusMessage = null;
  this._showingIdle = !text;
  renderStatus(this._statusEl, text || this._idleStatus(), cls);
};

C.prototype._setCancelVisible = function (visible) {
  this._showCancel = !!visible;
  this._cancelEl.classList.toggle('show', !!visible);
  this._syncControls();
};

C.prototype._startScan = async function (overrides) {
  if (this._busy || this._activeScanId || this._completedScan || this._hass?.connected === false) return;
  const before = this._scanState();
  this._lockedScanEntity = before?.entity_id || this._config?.entity || null;
  const previousId = before?.attributes?.scan_id;
  const epoch = this._requestEpoch || 0;
  const currentRequest = () => this.isConnected && epoch === (this._requestEpoch || 0);
  this._busy = true;
  this._backError = null;
  this._reverseBackOrder = false;
  this._card.classList.add('busy');
  this._setMessage('action.starting');
  this._setCancelVisible(false);
  this._clearResultTimer();
  try {
    if (!overrides && this._hasExplicitSettings()) {
      await this._refreshCapabilities();
      if (!this._capabilities?.body) throw new Error(this._t('error.settings_load'));
    }
    if (!currentRequest() || this._hass?.connected === false) return;
    const request = { ...(overrides || this._scanRequest()) };
    if (this._lockedScanEntity) request.entity_id = this._lockedScanEntity;
    const resp = await this._apiFetch('/api/escl_scan/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });
    let body = null;
    try { body = await resp.json(); } catch {}
    if (!resp.ok) {
      throw new Error(responseErrorMessage(resp, body,
        this._t('error.busy')));
    }
    if (typeof body?.scan_id !== 'string' || !body.scan_id) {
      throw new Error(this._t('error.response'));
    }
    if (!currentRequest()) return;
    const observedId = this._scanState()?.attributes?.scan_id;
    if (observedId && observedId !== previousId && observedId !== body.scan_id) return;
    this._activeScanId = body?.scan_id ?? null;
    const src = this._sourceText(body.source);
    const adjusted = body.requested_dpi && body.dpi !== body.requested_dpi
      ? this._msg('help.adjusted', { dpi: body.dpi, requested: body.requested_dpi }) : '';
    this._setMessage('status.scanning', { phase: '', source: src, progress: '', adjustment: adjusted, hint: '' });
    this._setCancelVisible(true);
    // A fast scan can already be terminal before its POST response arrives.
    const current = this._scanState();
    if (current?.attributes?.scan_id === this._activeScanId) {
      this._lastSig = null;
      this._onHass();
    }
    // From here on, the hass setter drives progress via _onHass().
  } catch (err) {
    if (!currentRequest()) return;
    if (this._activeScanId) {
      this._lastSig = null;
      this._onHass();
    } else {
      this._setMessage('status.start_failed', { error: err?.message || err }, 'err');
    }
  } finally {
    this._busy = false;
    if (!currentRequest()) { this._lastSig = null; this._onHass(); }
    this._card.classList.remove('busy');
    this._syncControls();
  }
};

C.prototype._scanToken = function () {
  return JSON.stringify([this._lockedScanEntity || this._scanState()?.entity_id, this._activeScanId, this._requestEpoch || 0]);
};
C.prototype._scanBacks = async function () {
  const current = this._scanState();
  const scanId = current?.attributes?.scan_id;
  const token = this._scanToken();
  if (current?.state !== 'awaiting-back-sides' || !scanId || this._resuming?.token === token || this._hass?.connected === false) return;
  const operation = { token };
  this._resuming = operation;
  const isCurrent = () => this.isConnected && token === this._scanToken();
  this._backError = null;
  if (this._backButton) this._backButton.disabled = true;
  if (this._backOrderEl) this._backOrderEl.disabled = true;
  const request = { scan_id: scanId, reverse_back_order: !!this._reverseBackOrder };
  if (current.entity_id) request.entity_id = current.entity_id;
  try {
    const r = await this._apiFetch('/api/escl_scan/scan_backs', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(request),
    });
    if (!r.ok) {
      let body = null;
      try { body = await r.json(); } catch {}
      throw new Error(responseErrorMessage(r, body, this._t('error.backs')));
    }
    if (isCurrent() && this._scanState()?.state === 'awaiting-back-sides') this._setMessage('status.start_backs');
  } catch (err) {
    const st = this._scanState();
    if (isCurrent() && st?.state === 'awaiting-back-sides') {
      this._backError = String(err?.message || err);
      this._renderScanState(st.state, st.attributes);
    }
  } finally {
    if (this._resuming === operation) {
      this._resuming = null;
      if (isCurrent()) {
        if (this._backButton) this._backButton.disabled = this._hass?.connected === false;
        if (this._backOrderEl) this._backOrderEl.disabled = this._hass?.connected === false;
      } else { this._lastSig = null; this._onHass(); }
    }
  }
};

C.prototype._cancelScan = async function () {
  if (!this._activeScanId || this._hass?.connected === false) return;
  const scanId = this._activeScanId, token = this._scanToken();
  if (this._canceling?.token === token) return;
  const operation = { token };
  this._canceling = operation;
  const isCurrent = () => this.isConnected && token === this._scanToken();
  const request = { scan_id: scanId };
  const entity = this._lockedScanEntity || this._scanState()?.entity_id;
  if (entity) request.entity_id = entity;
  try {
    const r = await this._apiFetch('/api/escl_scan/cancel', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(request),
    });
    const body = r.ok ? '' : await r.text();
    if (!isCurrent()) return;
    if (!r.ok) this._setMessage('status.cancel_failed', { error: body.slice(0, 80) }, 'err');
    else this._setMessage('action.canceling');
  } catch (err) {
    if (isCurrent()) this._setMessage('status.cancel_failed', { error: err?.message || err }, 'err');
  } finally {
    if (this._canceling === operation) this._canceling = null;
  }
};

const SCAN_SENSOR = 'sensor.printer_current_scan';

// Resolve the scan sensor: explicit `entity:` config wins; otherwise the
// default id; otherwise find the (single) escl_scan sensor by its enum
// options so a user-renamed entity still works. Result is cached.
C.prototype._scanState = function () {
  const states = this._hass?.states;
  if (!states) return null;
  const id = (this._busy || this._activeScanId) && this._lockedScanEntity || this._config?.entity;
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
  if (!this._rendered || !this.isConnected || this._hass?.connected === false) return;
  this._syncActivity();
  const st = this._scanState();
  const entity = st?.entity_id || this._config?.entity || null;
  if (this._resultEntity !== entity) {
    this._resultEntity = entity;
    this._lockedScanEntity = entity;
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
      this._setMessage('status.unavailable', {}, 'err');
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
      this._resuming = null;
      this._canceling = null;
      this._reverseBackOrder = false;
    }
    this._lockedScanEntity = entity;
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
    if (state === 'unavailable' || state === 'unknown') this._setMessage('status.unavailable', {}, 'err');
    else this._setStatus('');
    this._setCancelVisible(false);
  }
};

C.prototype._downloadScan = async function () {
  const result = this._completedScan;
  if (!result || this._busy || this._activeScanId || this._historyDownload || this._downloadRequest === result) return;
  const epoch = this._requestEpoch || 0;
  const currentDownload = () => this.isConnected && epoch === (this._requestEpoch || 0) && this._completedScan === result;
  this._downloadRequest = result;
  this._syncControls();
  try {
    const outcome = await downloadScanPdf(this, result, currentDownload);
    if (!currentDownload() || outcome === 'abandoned') return;
    if (outcome === 'expired') {
      this._completedScan = null;
      this._downloadedScanId = result.scanId;
      this._expiredActivityId = result.scanId;
      this._setMessage('error.expired', {}, 'err');
      return;
    }
    // Browsers do not report whether the user ultimately saves the file.
    // Consume only after the authenticated PDF has been handed to Downloads.
    this._completedScan = null;
    this._downloadedScanId = result.scanId;
    this._setStatus('');
  } catch (err) {
    if (currentDownload()) {
      this._setMessage('status.download_failed', { error: err?.message || this._t('error.retry') }, 'err');
    }
  } finally {
    if (this._downloadRequest === result) this._downloadRequest = null;
    this._syncControls();
  }
};

C.prototype._sourceText = function (source) {
  if (typeof source !== 'string' || !source) return '';
  const key = 'source.' + source.toLowerCase();
  const label = this._t(key);
  return this._msg('status.source', { source: label === key ? source : this._msg(key) });
};

C.prototype._renderScanState = function (state, attrs) {
  const pagesDone = attrs?.pages_done || 0;
  const source = this._sourceText(attrs?.source);
  const reloadHint = attrs.duplex_mode === 'manual' && attrs.scan_phase === 'fronts'
    ? this._msg('help.wait_backs') : '';
  if (state === 'pending') {
    this._setMessage('status.waiting', { hint: reloadHint });
    this._setCancelVisible(true);
  } else if (state === 'processing') {
    const src = source;
    const pages = pagesDone > 0 ? this._msg('status.page', { count: pagesDone }) : '';
    const phase = attrs.duplex_mode === 'manual' ? this._msg('status.phase', { phase: this._msg(attrs.scan_phase === 'backs' ? 'phase.backs' : 'phase.fronts') }) : '';
    this._setMessage('status.scanning', { phase, source: src, progress: pages, adjustment: '', hint: reloadHint });
    this._setCancelVisible(true);
  } else if (state === 'processing-stopped') {
    this._setMessage('status.paused', {}, 'err');
    this._setCancelVisible(true);
  } else if (state === 'awaiting-back-sides') {
    const wrap = document.createElement('span');
    wrap.append(translatedText('backs.ready', { count: attrs.front_pages || pagesDone }, this._hass));
    const order = document.createElement('select');
    order.dataset.i18nLabel = 'backs.order'; order.setAttribute('aria-label', this._t('backs.order'));
    for (const [value, text] of [['same', 'backs.same'], ['reverse', 'backs.reverse']]) {
      const option = document.createElement('option');
      option.value = value;
      option.dataset.i18n = text; option.textContent = this._t(text);
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
    button.dataset.i18n = 'action.backs'; button.textContent = this._t('action.backs');
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
    this._setMessage('status.complete', { count: pages }, 'ok');
    this._setCancelVisible(false);
  } else if (state === 'canceled') {
    this._setMessage('status.canceled', {}, 'err');
    this._setCancelVisible(false);
  } else if (state === 'aborted' || state === 'failed') {
    const reason = attrs?.state_reasons || attrs?.error;
    this._setMessage('status.failed', { reason: reason ? this._msg('status.reason', { reason }) : '' }, 'err');
    this._setCancelVisible(false);
  } else {
    this._setCancelVisible(false);
  }
};

window.customCards = window.customCards || [];
if (!window.customCards.find((c) => c.type === TAG)) {
  window.customCards.push({
    type: TAG,
    name: localize('picker.name'),
    description: localize('picker.description'),
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



C.prototype._installOptions = function () {
  const panel = this._createOptionsPanel();
  this._optionFields = {
    source: addOptionField(panel, 'source', 'field.source'),
    color: addOptionField(panel, 'color', 'field.color'),
    dpi: addOptionField(panel, 'dpi', 'field.dpi'),
    page_size: addOptionField(panel, 'page_size', 'field.page_size'),
    width: addOptionField(panel, 'width', 'field.width', 'number'),
    height: addOptionField(panel, 'height', 'field.height', 'number'),
  };
  for (const [key, field] of Object.entries(this._optionFields)) {
    field.addEventListener('change', () => {
      if (field.disabled || this._busy || this._activeScanId) return;
      this._settingsAdjustment = '';
      this._settings[key] = ['width', 'height'].includes(key) ? Math.round(Number(field.value) * 300 / 25.4) : field.value;
      this._syncControls();
    });
  }
  this._finishOptionsPanel();
};
C.prototype._refreshOptions = function () { return this._refreshCapabilities(); };
C.prototype._syncOptions = function (locked) {
  if (!this._optionFields) return;
  const settings = this._settings;
  if (locked) { for (const field of Object.values(this._optionFields)) field.disabled = true; return; }
  const caps = this._capabilities?.expires > Date.now() ? this._capabilities.body : null;
  const supported = caps?.supported;
  const available = Array.isArray(caps?.request_options) ? caps.request_options : [];
  const fields = this._optionFields;
  this._settingsError = '';
  const toggle = this._twoSidedEl.closest('label');
  const parent = this._config.duplex_in_options ? this._optionsPanel : this.shadowRoot.querySelector('.controls');
  if (toggle.parentElement !== parent) parent.prepend(toggle);
  this._twoSidedEl.disabled = locked || settings.source === 'Platen';
  toggle.querySelector('small').textContent = settings.source === 'Platen' ? this._t('help.select_feeder') : this._t('help.feeder');
  const sourceKnown = Array.isArray(supported?.sources);
  optionChoices(fields.source, [['auto', this._t('choice.automatic')], ['Feeder', this._t('choice.feeder'), sourceKnown && !supported.sources.includes('Feeder')],
    ['Platen', this._t('choice.glass'), this._duplex || (sourceKnown && !supported.sources.includes('Platen'))]], settings.source);
  if (this._duplex && settings.source === 'Platen') this._settingsError = this._t('error.feeder');
  else if (sourceKnown && settings.source !== 'auto' && !supported.sources.includes(settings.source)) this._settingsError = this._t('error.source');
  const key = settings.source === 'Platen' ? 'Platen' : (this._duplex && supported?.automatic_duplex === true) ? 'FeederDuplex' : 'Feeder';
  const profile = supported?.profiles?.[key];
  const combinations = Array.isArray(profile?.combinations) ? profile.combinations.filter(p => p && typeof p === 'object' && (!Array.isArray(p.formats) || p.formats.some(f => ['application/pdf','image/jpeg','image/png'].includes(f)))) : [];
  const autoSource = settings.source === 'auto' && !this._duplex;
  let colors = !autoSource && Array.isArray(profile?.colors) ? profile.colors : ['color', 'gray'];
  if (settings.color !== 'default' && !colors.includes(settings.color)) {
    this._settingsError = this._t('error.color');
    colors = [...colors, settings.color];
  }
  optionChoices(fields.color, [['default', this._t('choice.integration_default')], ...colors.filter(x => ['color', 'gray'].includes(x)).map(x => [x, x === 'gray' ? this._t('choice.grayscale') : this._t('field.color')])], settings.color);
  let resolutions = !autoSource && Array.isArray(profile?.resolutions) ? profile.resolutions : [150, 200, 300, 600];
  if (!autoSource && combinations.length && settings.color !== 'default') {
    const matching = combinations.filter(p => p.colors == null || (Array.isArray(p.colors) && p.colors.includes(settings.color)));
    if (matching.length && matching.every(p => Array.isArray(p.resolutions))) {
      resolutions = [...new Set(matching.flatMap(p => p.resolutions))].sort((a,b) => a-b);
    }
  }
  resolutions = resolutions.filter(dpi => Number.isInteger(dpi) && dpi >= 50 && dpi <= 1200);
  if ((autoSource || !Array.isArray(profile?.resolutions)) && settings.dpi !== 'default') resolutions = [...new Set([...resolutions, Number(settings.dpi)])].sort((a,b) => a-b);
  let adjustment = this._settingsAdjustment ? this._t('help.dpi_adjusted', this._settingsAdjustment) : '';
  if (settings.dpi !== 'default' && resolutions.length && !resolutions.includes(Number(settings.dpi)) && !autoSource) {
    const nearest = [...resolutions].sort((a,b) => Math.abs(a-Number(settings.dpi))-Math.abs(b-Number(settings.dpi)) || a-b)[0];
    this._settingsAdjustment = { requested: settings.dpi, dpi: nearest };
    adjustment = this._t('help.dpi_adjusted', this._settingsAdjustment);
    if (!locked) settings.dpi = String(nearest);
  }
  optionChoices(fields.dpi, [['default', this._t('choice.integration_default')], ...resolutions.map(dpi => [dpi, this._t('choice.dpi', { dpi })])], settings.dpi);
  optionChoices(fields.page_size, [['full',this._t('choice.full')],['letter',this._t('choice.letter')],['a4',this._t('choice.a4')],['custom',this._t('choice.custom')]], settings.page_size);
  for (const [name, field] of Object.entries(fields)) {
    const defaultValue = ({source:'auto',color:'default',dpi:'default',page_size:'full'})[name];
    field.disabled = locked || (!available.includes(name) && settings[name] === defaultValue);
    if (name === 'width' || name === 'height') {
      field.closest('label').hidden = settings.page_size !== 'custom';
      field.min = '0.1'; field.step = '0.1';
      field.dataset.maxUnits = String(profile?.maximum_region?.[name === 'width' ? 0 : 1] || 60000);
      field.max = String(Math.floor(Number(field.dataset.maxUnits) * 25.4 / 30) / 10);
      if (document.activeElement !== this || this.shadowRoot.activeElement !== field) field.value = settings[name] ? (settings[name] * 25.4 / 300).toFixed(1) : '';
    }
  }
  if (settings.page_size === 'custom' && ['width','height'].some(name => !Number.isInteger(settings[name]) || settings[name] < 1 || settings[name] > Number(fields[name].dataset.maxUnits))) {
    this._settingsError = this._t('error.region');
  }
  setText(this._optionHelp, this._settingsError || adjustment || (!caps ? this._t('help.unavailable')
    : autoSource ? this._t('help.auto_source') : this._t('help.next_job')));
};
C.prototype._scanRequest = function () {
  if (this._settingsError) throw new Error(this._settingsError);
  const request = { duplex: !!this._duplex };
  const settings = this._settings;
  const available = this._capabilities?.body?.request_options || [];
  for (const name of ['source','color','dpi','page_size']) {
    const isExplicit = settings[name] !== ({source:'auto',color:'default',dpi:'default',page_size:'full'})[name];
    if (isExplicit && !available.includes(name)) throw new Error(this._t('error.update'));
  }
  if (this._duplex) request.source = 'Feeder';
  else if (settings.source !== 'auto' && available.includes('source')) request.source = settings.source;
  if (settings.color !== 'default' && available.includes('color')) request.color = settings.color;
  if (settings.dpi !== 'default' && available.includes('dpi')) request.dpi = Number(settings.dpi);
  if (available.includes('page_size')) {
    request.page_size = settings.page_size;
    if (settings.page_size === 'custom') { request.width = settings.width; request.height = settings.height; }
  }
  return request;
};

C.prototype._hasExplicitSettings = function () {
  return this._settings && (this._settings.source !== 'auto' || this._settings.color !== 'default'
    || this._settings.dpi !== 'default' || this._settings.page_size !== 'full');
};

C.prototype._connectionSnapshot = function () {
  return this._scanState()?.attributes?.device_connection;
};

registerDocumentFeature();
