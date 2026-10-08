# Shared card foundation and mobile release validation

Status: implementation ready for release; live installation and physical phone
confirmation pending. Scan v0.6.0 and print v0.5.0, 2026-10-08.

## Implemented

The [version 1 contract](decisions/2026-10-08-shared-card-contract.md) governs
both standalone cards. A compact Two-sided switch sets scan intent; Scan submits
once and freezes controls. Print stages files locally, preserves selection when
the picker is canceled, and submits only from Print. Accepted or uncertain
submissions release the browser's staged file. Uncertain outcomes explain that
the printer queue should be checked before retrying.

Both cards use the same neutral base styling, native icons, theme colors, 44px
action/label targets, readable text and Sections dimensions. Existing explicit
titles and card types are preserved. Source/color/resolution and print settings
remain the later API/options phases.

## Findings repaired during implementation

- A title/default editor update could reprocess an old sensor snapshot and
  reset active scan controls. Reprocess the sensor only when its configured
  entity changes; a new duplex default waits until the current job finishes.
- Native custom-element lifecycle callbacks are captured at registration.
  Assigning print callbacks to the prototype afterward did not register them.
  Early forwarding callbacks now actually clean up and reconnect subscriptions
  and remove open file inputs when the card disconnects.
- A malformed successful print response could leave no usable job handle.
  Require a positive integer ID and explain the uncertain outcome without
  inviting an immediate duplicate print.
- A manual duplex job begun elsewhere now displays its actual mode on the
  disabled switch, then restores this card's next-job preference afterward.

## Native host experiment

`tests/card/native-feature-probe.js` is a development-only experiment with no
device action. Mounted two feature rows in native Tile and the installed
Mushroom Template on HA 2026.9.4. Both supplied `hass`, `context.entity_id` and
the legacy `stateObj`. At a 183px card width, both feature rows were 159px wide
and 42px high with no horizontal overflow. Switches did not trigger actions;
the Tile action accepted Enter. A native options dialog opened and returned
focus to its trigger. No saved dashboard configuration was changed.

HA 2024.12.0 declares frontend 20241127.4. Its published feature host source
supports custom features but passes `stateObj`, not `context`. The probe adapter
accepts either. This is source compatibility evidence, not a full runtime test
of that older frontend or an Android app test. Native features remain a later
optional release; the standalone minimum version remains 2024.12.

Sources: [HA minimum-version frontend manifest](https://github.com/home-assistant/core/blob/2024.12.0/homeassistant/components/frontend/manifest.json),
[older feature host](https://github.com/home-assistant/frontend/blob/20241127.4/src/panels/lovelace/card-features/hui-card-feature.ts),
[current custom feature contract](https://developers.home-assistant.io/docs/frontend/custom-ui/custom-card-feature/).

## Automated and browser checks

- Scan: 166 Python tests, 35 card tests and Ruff passed.
- Print: 135 Python tests, 28 card tests, compileall and Ruff passed.
- Both card suites ran after npm ci. No new runtime dependencies or separate
  imported card assets were introduced; existing resource hashing still covers
  the complete shipped module.
- Ran 63 paired layout cases: seven fixtures at 320/390/768px container widths,
  in light/dark/custom themes, inside the real HA frontend. No horizontal
  overflow or visible button targets below 44px; idle/running card heights
  matched. Narrowest cards were 144px wide and 202px high in the current theme.
- Fixtures cover idle, long staged filename, running, manual reload, error,
  completion and unavailable state. Native status detail and file controls keep
  separate action targets. Updated README screenshot shows the actual cards.

The fixture renderer blocks all network and service operations. It validates
presentation without consuming paper or changing device jobs. Physical one-sided
and manual-duplex workflows retain their earlier backend verification; this
release's request construction and control behavior have automated coverage.

## Reproducing the paired preview

The canonical cases are `tests/card/document-card-fixtures.json`, copied into
the printer repository at the same contract version. The shared base CSS is
marked in both `static/card.js` files and must stay identical.

Use a disposable HA browser page. Load the two card modules under
`escl-scan-preview` and `ipp-print-upload-preview` tags, then load
`tests/card/paired-preview.js` and call `mountDocumentCardPreview` with the
fixture JSON and a case ID. The preview uses stubbed state and rejects device
requests. Remove the overlay or reload the page afterward. Native host probing
uses `mountDocumentHostProbe`; it also has no device action.

## Remaining release gates

- Hosted validation on both final commits and HACS release workflows.
- Back up installed integrations, confirm both jobs are idle, install the two
  card releases, and verify current content-hashed resources after reload.
- Reopen the physical Android dashboard and confirm both cards load and the
  Two-sided switch is visible. Desktop mobile emulation does not close this gate.
- A complete runtime test on HA 2024.12 and automatic-duplex scanner hardware
  remain outside this local environment; do not promote native features on
  the basis of the current-host experiment alone.
