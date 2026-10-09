# Card localization and editor accessibility

Status: implemented for scan 0.9.0 / print 0.8.0. User chose translation-ready English for
this release; additional languages require reviewed translations.

Keep each English catalog inside its existing `static/card.js`, immediately
after early custom-element registration. No build, framework, remote translation
service, extra asset request or dependency is introduced. This preserves the
content-hashed single-asset loading contract and independent installations.

Use stable semantic keys, whole-message placeholders and plural forms through
Intl.PluralRules. Resolve the HA selected language (locale.language, then language),
regional/base fallback, then English per missing key. Missing/invalid locales and
unknown keys must not crash the card. Wire values, entity IDs, user titles, file
names and device/backend error details are data; never translate or interpolate
them as HTML. Publish contribution instructions with catalog/placeholder checks.

Card actions, options, editor labels/help/choices, client-side errors and status
messages use the catalog. Backend integration strings/translations remain in
HA's existing mechanism; server/device error text remains original diagnostic
data inside localized frontend messages. This release claims English only.

Keep focused form fields and staged settings on HA updates. Editor defaults must
match actual card defaults without rewriting saved YAML merely by opening the
editor. Clearing optional numeric DPI removes its override. Use readable labels
for selectors while preserving exact request values. Name Options buttons by
task, focus the dialog heading on open (no unsolicited phone keyboard), and
associate option guidance with fields. Verify keyboard focus, Back, narrow/long
labels, markup-shaped translations, fallback, plurals and default preservation.


Validation and contributor workflow: see
[Phase 3 validation](../shared-card-phase-3-validation.md) and each README's
Card translations section. The helper keeps only the last parsed locale;
normal HA state pushes do not rebuild scan controls or repeat live-region text.
Backend scan phases remain protocol values regardless of language.
