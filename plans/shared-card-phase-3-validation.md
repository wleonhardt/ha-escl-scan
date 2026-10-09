# Phase 3 editors, accessibility and localization validation

Candidate pair: scan **0.9.0** / print **0.8.0**, 2026-10-08.
Implementation and live browser checks pass; HACS publication pending.

## Scope

- Matching native HA visual editors with readable labels, selector choices and
  help. Displayed defaults match card behavior; opening emits no config change.
  Clear optional scan DPI/print copies to remove the override. Preserve unknown
  config fields, existing card types, explicit titles and all wire values.
- User explicitly chose translation-ready English now and reviewed languages
  later. Inline catalogs preserve early registration and the one-asset loading
  model; region/base/English fallback, complete messages, placeholders and
  plurals are ready. No new dependency or asset request.
- Task-specific Options names, heading focus, field descriptions, logical
  alignment and no repeated live-region mutations for unchanged content.
  Editor controls remain native `ha-form`; no private component patching.
- Protocol values and device/backend diagnostic text stay unchanged. A test
  guards manual front-phase matching against translated-label comparisons.

## Automated checks

- Scan: 215 Python + 59 card tests. Print: 206 Python + 47 card tests.
  **527 total passing tests**, after `npm ci` in each repository.
- Ruff passes in both; print compileall and both card syntax checks pass.
- Locale coverage: region/base/missing/invalid locale, per-key English fallback,
  English and other-language plural rules, placeholder safety, literal HTML-like
  text, staged settings/focus/status preservation during language changes,
  manual reload guidance, editor normalization and no unintended submissions.
- Localization helper, shared base styles and Options lifecycle blocks match
  across the pair. Backend/protocol implementation is unchanged by this release.

## Live HA 2026.9.4 checks

- Installed while both tracked sensors were idle. Integration reloads returned
  200 with `require_restart: false`; no full HA restart or hardware job needed.
- Native `ha-form` editors tested in a temporary unsaved panel under HA's context
  provider. Entity selectors load; all readable choice labels/defaults/help
  render. Opening emits zero changes. Selecting Glass stores `Platen`; selecting
  Short edge stores `two-sided-short-edge`. Entering then clearing resolution or
  copies removes that setting. No dashboard configuration saved by the probe.
- Both editors fit 390 px without horizontal overflow; the longer scan editor
  scrolls. Print Options at 320 px with deliberately long heading/field labels
  wraps and scrolls vertically (284 px content width and scroll width).
- Options opens with the heading focused. Tab moves to Source; browser Back
  closes Scan Options, keeps `/lovelace/printer` and focuses its Options button.
  Escape does the same for Print Options. Existing phone Back acceptance from
  0.8.2/0.7.2 remains recorded separately; this check is browser automation.
- Reload clears temporary probes and labels. Verify the final content-hashed
  resources after reload; an already-open browser can briefly load the previous
  bootstrap asset once while HA refreshes its module list.

## Deployment and rollback

Backup before installation:
`/config/.document-card-backups/before-localization-v090-v080-20261008.tar.gz`.
Contains both complete components and Lovelace resources. Only card/manifest
files changed on the host for this release.

Final source hashes:
- scan: `09542c63616cc1199c228c0e221d7fc2f5195e14973569589a46a2ca2bce5ef3`
- print: `ae0fc5b82635e9db4dd98efe305af2cc99e57916fc2d61fc31c09be9746f58a3`

## Coverage limits and next phase

- English is the only shipped catalog. Fake test catalogs exercise fallback and
  layout; they are not translations offered to users. No screen-reader device
  acceptance was performed; semantics, focus and keyboard paths were checked.
- Minimum HA frontend source supports `computeHelper` and `{value,label}` select
  choices: [ha-form](https://github.com/home-assistant/frontend/blob/20241127.4/src/components/ha-form/ha-form.ts)
  and [ha-selector-select](https://github.com/home-assistant/frontend/blob/20241127.4/src/components/ha-selector/ha-selector-select.ts).
  This is source compatibility, not an older-version runtime test.
- HP physical acceptance was completed on the preceding protocol-identical pair:
  [compatibility validation](compatibility-validation-2026-10-08.md). Automatic
  duplex scanning, other vendors and software bridges need external hardware.
- Phase 4 remains: print recovery from pushed state/reconnect, entity/job-scoped
  stale-reply guards and checked availability. The dashboard's old printer-offline
  summary combines stale/inverted legacy sensors; keep this separate from job
  and capability results and replace it with checked availability in Phase 4.
