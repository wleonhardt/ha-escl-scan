// Development-only fixture renderer for a real HA frontend. All I/O is blocked.
// Load both cards under their -preview tags, then call mountDocumentCardPreview.
window.mountDocumentCardPreview = async (fixtures, selected = 'idle') => {
  document.getElementById('document-host-probe')?.remove();
  document.getElementById('document-card-preview')?.remove();
  const root = document.createElement('section');
  root.id = 'document-card-preview';
  root.style.cssText = 'position:fixed;inset:0;z-index:10000;padding:12px;box-sizing:border-box;background:var(--primary-background-color);overflow:auto';
  root.innerHTML = '<style>#document-card-preview .toolbar{display:flex;gap:12px;align-items:center;margin-bottom:12px}#document-card-preview .pair{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;align-items:start}#document-card-preview button,#document-card-preview select{min-height:44px;font:inherit}</style><div class="toolbar"><select aria-label="Fixture"></select><button type="button">Close preview</button></div><div class="pair"></div>';
  const selector = root.querySelector('select');
  for (const fixture of fixtures.cases) {
    const option = document.createElement('option');
    option.value = fixture.id;
    option.textContent = fixture.id;
    selector.append(option);
  }
  selector.value = selected;
  root.querySelector('button').addEventListener('click', () => root.remove());
  const draw = async () => {
    const fixture = fixtures.cases.find(item => item.id === selector.value);
    const pair = root.querySelector('.pair');
    pair.replaceChildren();
    const scan = document.createElement('escl-scan-preview');
    const print = document.createElement('ipp-print-upload-preview');
    scan.setConfig({}); print.setConfig({});
    const scanId = 'sensor.printer_current_scan';
    const printId = 'sensor.printer_current_job';
    const hass = {
      states: {
        [scanId]: { entity_id: scanId, ...fixture.scan },
        [printId]: { entity_id: printId, ...fixture.print },
      },
      entities: { [printId]: { platform: 'ipp_print', entity_id: printId } },
      fetchWithAuth: async () => { throw new Error('Preview only: device requests disabled'); },
      connection: { subscribeMessage: async () => () => {} },
    };
    pair.append(scan, print);
    scan.hass = hass;
    print._getHass = () => hass;
    print.hass = hass;
    if (fixture.filename) print._stageFile(new File(['preview'], fixture.filename, { type: 'application/pdf' }));
    if (fixture.print.attributes.job_id) {
      print._activeJobId = fixture.print.attributes.job_id;
      print._activeSensorId = printId;
      await print._trackPrintProgress(printId);
    }
  };
  selector.addEventListener('change', draw);
  document.body.append(root);
  await draw();
};
