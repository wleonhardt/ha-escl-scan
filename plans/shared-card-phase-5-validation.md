# Phase 5 native feature validation — 2026-10-09

Status: released and installed; local/hosted checks and minimum/current host
runtime checks pass. Physical Android acceptance remains open; native examples
stay opt-in. Released pair: scan 0.11.0 / print 0.10.0.

## Implementation

Both integrations register independent native custom features from their existing
single content-hashed module. Each feature embeds the existing workflow with a
plain div instead of a second ha-card. Tile/current Mushroom supplies identity
and surface; visible Two-sided, status, Options and explicit primary actions are
shared with standalone cards. Vendored core v3 is identical in both repositories.

The host's integration job sensor is authoritative. Modern context wins over
legacy stateObj, including an explicitly empty context; area-only/wrong-domain
hosts and inline placement display guidance. Changing the host device detaches
old requests, staged files and results. Print's standalone device selector is
hidden and disabled inside a feature. Control gestures stop at the feature.

Native feature editors have domain-specific tags and reuse the standalone
schema while excluding title/entity, including when an older standalone editor
was registered first. A live same-page upgrade exposed that case; regression
tests now cover it. No backend protocol or stored job lifecycle changed.

## Automated checks

- Scan: 225 Python + 70 card tests pass. Ruff passes.
- Print: 217 Python + 60 card tests pass. Ruff and compileall pass.
- Total: **572 tests**, after npm ci. Shared-core parity and syntax checks pass.
- Both release commits passed all six hosted validation jobs. Both tag workflows
  published non-draft, non-prerelease HACS releases.
- Scan commit `cca6945a792f6962199f5c781d1dfcd3c0e2ad77`, validation run
  `37943266020`, release run `37943467728`, tag `v0.11.0`.
- Print commit `7445c5a30e0ddaae1682d72eaf1b6a187ff7ae35`, validation run
  `37943270180`, release run `37943467319`, tag `v0.10.0`.
- Added tests cover feature picker/defaults, editor ownership, invalid options,
  old/new context, stale legacy delivery, unsupported/inline hosts, remount/local
  intent, control events, frozen target submission, stale reply detachment,
  manual-back/download retention, and print file/device isolation.
- Isolated combined-module checks pass for scan alone, print alone, both new,
  new scan with print 0.9.1/core v2, and scan 0.10.0/core v2 with new print.

## Real host runtime checks

Current: HA **2026.9.4**, installed Mushroom **5.2.3** resource. Both native Tile
and current Mushroom Template render the real feature implementation with scoped
simulated states and transport. Fixtures never replace HA state or send a device
job. Checked 320/390 px side-by-side controls, long staged filenames, running
counts, expanded manual-back instructions, HA disconnection controls/warnings,
768 px layout with light/custom surface variables, and the current dark theme.
No horizontal overflow; native surfaces remain owned by their host. Options
measures 354 px inside a 390 px viewport, and browser Back closes it correctly.

Minimum: a separate local HA **2024.12.5** instance with its actual frontend
**20241127.8**, listening only on 127.0.0.1:8124. No printer integrations or device
access were configured there. Scan registers before Print is loaded. Both Tile
features render with legacy stateObj delivery at 390 px, including manual-back
controls and print progress. Native Options fits at 354 px and Back closes it.
A fresh authenticated reload of the final assets also renders both features
using stateObj (without modern context), and both distinct editors exclude host
identity. This is runtime frontend coverage, not a physical device/backend test
on old HA. The temporary local instance is stopped after verification.

The disposable preview and optional examples use bottom-position features with
Sections rows set to auto; fixed-height rows can clip expanded instructions.
Legacy Mushroom Template, inline features, unrelated hosts and area-only cards
are not supported. Physical Android acceptance remains required before promoting
native features as the recommended new-dashboard path.

## Deployment and rollback

Both production job sensors were idle before installation. Backup:
`/config/.document-card-backups/before-phase5-v0110-v0100-20261009.tar.gz`.
It contains both integrations, Lovelace resources and the original dashboard.
Both entry reloads succeeded without an HA restart. The original Printer view
and all other existing views were verified unchanged; a separate Native documents
view at `/lovelace/native-documents` contains the paired native Tiles for phone
acceptance. A fresh production page loads both real features and their distinct
editors with the correct sensors. Both job sensors remain idle; no device job was
submitted in Phase 5.

Installed assets match source:
- Scan: `/escl_scan/card-280c069e070d.js` (SHA-256 `280c069e070dd7e41015bc2b75a251f9321b4448a1754416062f2317ebc638dd`)
- Print: `/ipp_print/card-224ad3307c63.js` (SHA-256 `224ad3307c63233cd0436a9019cde5435db16e3114a1164345fa312e06b2dca0`)

The user has been asked to check both features and Options/Back on the phone.
Retain the standalone view regardless of the phone result; migration stays optional.

## Android startup regression — patch pair 0.11.1 / 0.10.1

The physical phone check exposed an intermittent Scan feature Configuration
error; the user reports working/error results alternating across refreshes.
A fresh browser load with service-worker/cache bypass reproduced the cause:
the asset downloaded with the expected hash and its native constructor existed,
but a late scoped custom-element registry polyfill replaced window.customElements.
The new registry could not find the earlier Scan registrations. A later Print
module could escape the race. Delaying the module alone did not reproduce it.

The shared core retains each integration's five constructors and restores only
missing definitions when the registry identity changes. Script/page load,
page restoration, HA readiness and navigation cover startup and returning views.
Normal events do one identity check; there is no ongoing timer/DOM scan and no
replacement of mounted workflows or definitions supplied by another version.

Both new regression tests fail against each released module and pass with the
patch. They check non-bubbling script load, original constructor identity,
retained scan intent / staged print file, Options, already-registered versions,
and page restoration. All 576 tests pass (Scan 225 Python / 72 card; Print
217 Python / 62 card), plus Ruff, compileall and shared-core parity.

A scoped live preview loaded both patched modules before the native registry
was replaced: both were initially present, briefly absent in the replacement,
then restored automatically. Both native controls rendered and Options/Back
worked at 390 px. No print/scan job was submitted; both sensors stayed idle.
The browser also logged card-mod's requestUpdate error after Options, although
both dialogs closed correctly; that separate compatibility observation remains
to investigate. Physical phone acceptance needs a retry after patch installation.
