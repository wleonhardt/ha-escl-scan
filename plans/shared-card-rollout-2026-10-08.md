# Shared scan and print card rollout plan

Status: Phases 0–6 are complete. Current pair: scan 0.12.1 / print 0.11.1,
including the subsequent discovery/card-mod compatibility fixes.
HP scan/print, refresh/restart retention and physical phone acceptance passed.
The approved native cards were promoted to the main Printer dashboard on
2026-10-09 at the user's request, retaining connection tiles and navigation.
Standalone cards remain supported; integration updates never migrate dashboards
implicitly. [Phase 6 validation](shared-card-phase-6-validation.md) and
[rollout closeout / compatibility follow-up](compatibility-follow-up-2026-10-09.md).

Bring scanning and printing onto one Home Assistant visual and interaction
contract, starting with the visible Two-sided switch selected in the design
preview. Ship the mobile improvements early, add settings only when their
backend paths work, and introduce native Tile features after compatibility is
proven. Each integration must continue to work when installed on its own.

This is the canonical cross-project plan. The
[design review](design-review-2026-10-08.md) records the findings and reference
designs. The [printer work queue](https://github.com/wleonhardt/ha-ipp-print/blob/main/plans/2026-10-08-shared-card-rollout.md)
tracks the corresponding printer work. Starting baselines are scan v0.5.2
(`d7272bb`) and print v0.4.1 (`764fe71`).

## Product rules

- One primary action: Scan, or Choose file followed by an explicit Print.
  Selecting a file stages it locally; toggling Two-sided never submits a job.
- Two-sided is visible by default. An options-only layout is an optional compact
  configuration introduced with the settings panel. No essential action depends
  on long press, hover, or an icon without a label.
- Settings apply to the next job and freeze when submitted. Card defaults take
  precedence over integration defaults when explicitly supplied. Initially,
  changes last for the card instance and reset to documented defaults on reload;
  persistent browser preferences and presets are separate later work.
- Two-sided scanning requires the feeder. With explicit Glass selected, disable
  Two-sided with an explanation. With Auto selected, label the switch as using
  the feeder and set the next job's source to Feeder when enabled. Never
  silently override an explicit Glass choice.
  Show automatic or manual scanning when known, and an honest unknown state
  when capabilities are unavailable. Backend selection remains authoritative.
- Print controls describe what will be sent. Until the upload endpoint accepts
  sides, do not show a functional-looking duplex switch or promise one-sided
  output from the printer's implicit defaults. Once supported, new UI defaults
  are one copy and one-sided, with explicit long-edge or short-edge binding for
  two-sided jobs. Existing API calls with omitted fields keep their behavior.
- Installation settings such as credentials, output folder and retention stay
  in integration configuration. Ordinary jobs do not expose host or entry IDs.
- Existing card types, entity IDs and working YAML remain supported. The staged
  print flow is a deliberate, documented interaction change. Quick-print may
  return later as an explicit opt-in setting; it is not the initial default.

## Milestones and dependencies

| Phase | Deliverable | Dependency | Shipping boundary |
| --- | --- | --- | --- |
| 0 | Shared contract and native host compatibility experiment | None | Decision and fixtures; no required production UI change |
| 1 | Smaller duplex switch and consistent mobile cards | Phase 0 contract | First paired UI release, using existing APIs |
| 2 | Cached capabilities and validated print upload options | Phase 0 contract | Additive backend releases; old cards continue working |
| 3 | Common options panel and visual editors | Phases 1 and 2 | Capability-aware settings release |
| 4 | Consistent job state, availability and recovery | Phase 1; metadata from Phase 2 | Reliability release with the same card configuration |
| 5 | Native Tile custom features and optional Mushroom hosting | Phase 0 experiment; Phases 3 and 4 | Additive dashboard integration release |
| 6 | Durable latest scan and bounded recent activity | Stable Phase 4 state contract | Result access release, separately from the visual redesign |

Complete Phase 0 first, then prioritize Phase 1. Phase 2 backend work can proceed
independently of Phase 1 styling. Phase 4 can proceed alongside Phase 3 once its
metadata dependency exists. Neither native hosting nor history blocks the
initial mobile improvement. These are milestones, not promised dates or a
requirement to release both repositories at precisely the same time.

## Phase 0 Shared contract and host experiment

Agree on the small reusable surface before extracting production code.

- [x] Record a structural decision covering independent distribution, legacy
  wrappers, domain-specific adapters and the shared contract version.
- [x] Define presentation states: Ready, Preparing, Running, Needs attention,
  Complete, Error and Unavailable. Keep device availability separate from job
  activity; map unknown backend states conservatively.
- [x] Define common spacing, typography, icons, action hierarchy, status text,
  options entry, cancellation and disabled behavior. Inherit host surfaces,
  borders, radius and shadow. Inventory existing custom styling and require a
  concrete layout or accessibility reason for retained overrides.
- [x] Create common fixtures for idle, selected file, running, manual reload,
  errors, unavailable and completion. Include long names and narrow cards.
- [x] Prototype a plain-JS custom feature in native Tile and current Mushroom
  Template. Check entity context, action/switch separation, feature row sizing,
  options panel, keyboard behavior and registration on refresh/update.
- [x] Test the current installed HA frontend and confirm standalone card loading
  on the physical phone after the paired release.
- [x] Native feature runtime passed on HA 2024.12.5/frontend 20241127.8 and
  current HA 2026.9.4. The user confirmed Android registration/navigation after
  the registry fix. [Evidence](shared-card-phase-5-validation.md).

Exit: a decision with tested host/version limits and fixtures both repositories
can consume. Do not couple this experiment to private Tile shadow DOM, a Lit
rewrite, a required HACS card, or a remote shared script. The minimum HA version
must not rise silently to accommodate the redesign.

## Phase 1 Mobile polish using existing APIs

Deliver the improvement the user can see first, within the existing standalone
cards. Share conventions and fixtures now; extract code only where both cards
actually use the same behavior.

- [x] Replace Scan Duplex with a compact labelled Two-sided switch and one Scan
  button. Keep existing manual reload, back-order and cancel paths intact.
  Show the feeder/manual-pass explanation before starting when applicable.
- [x] Give print the same header, status, main action and control treatment.
  Rename Print PDF to Print and stage PDF/JPEG/PNG selection with filename,
  Replace/Clear and explicit Print. Handle file-picker cancellation without
  clearing an already staged file. Keep the file local until Print is pressed.
- [x] Replace nested clickable card regions and the small cancel div with
  separate real controls. Prevent duplicate starts and keyboard/toggle events
  from triggering the outer action. Snapshot next-job settings on submission
  and disable changes while that job runs.
- [x] Remove permanent scan tint and fixed scan radius. Use theme text and
  status colors, native icons, visible focus and comfortable touch targets.
  Reflow long text instead of shrinking essential text to 11px.
- [x] Add matching standalone Sections sizing through `getGridOptions`, retain
  masonry sizing, and publish direct Sections examples plus existing stack
  examples. Use consistent idle and ordinary running dimensions. Attention
  and detailed error content may expand for readability.
- [x] Keep a concise readable error summary and a discoverable detail action.
  Surface actionable scan conflicts already supported by v0.5.1; a generic
  HTTP code must not be the only recovery guidance.

Exit: both cards fit the agreed layouts, existing YAML loads, and setting/file
changes cause zero job submissions. Scan one-sided and manual duplex still
work. Printing submits once only after Print. Test physical Android loading;
the earlier Configuration error must not be considered resolved solely from
a desktop viewport simulation.

## Phase 2 Backend capability and upload contracts

Add the missing data and request support before showing additional controls.
Keep capability reads shared and cached in the backend, rather than initiating
device probes on every card render or separately in each dashboard card.

- [x] Publish a bounded, versioned capability snapshot available while idle:
  identity, supported/unknown sources and resolutions, automatic/manual scan
  method, supported print sides, copies limit and accepted formats. Define
  fetched time, refresh policy and missing/stale semantics. Represent source
  and duplex-dependent resolution lists accurately.
- [x] Choose compact sensor attributes or an authenticated capability view in
  the Phase 0 decision. Avoid large raw capability blobs and unnecessary
  recorder churn. Preserve existing job sensor attributes for automations.
- [x] Extend print multipart upload with optional `copies` and `sides`, routing
  by the existing sensor `entity_id`. Reject duplicate/unexpected fields,
  malformed or out-of-range copies and invalid sides before submission. Copies
  must be a positive decimal integer, not a coerced float or boolean value.
  Preserve bounded metadata, the 50 MiB document limit and format sniffing.
- [x] Reuse `_submit` for service/upload validation, advertised printer limits
  and fresh default media on explicit sides requests. Keep the sized streaming
  payload and do not retry an ambiguous accepted print automatically.
- [x] Use additive response metadata to advertise available request options.
  An older backend must leave unsupported controls unavailable with useful
  guidance, rather than receiving newly invented fields.
- [x] Cover unknown capabilities and device refresh failures without claiming
  unsupported hardware. Validate all overrides on the server even when a
  frontend selector has already restricted them.

Exit: old uploads and service calls behave as before; valid copies/sides reach
the selected printer; invalid input submits no job. Capability metadata exists
with no active job, is safe for non-admin dashboard use, and has bounded refresh
cost. Verify one-sided and both binding modes on the HP where supported.

## Phase 3 Options panels and visual editors

Build one interaction pattern with different supported settings for each task.

- [x] Scan panel: Auto/Feeder/Glass, Color/Grayscale and supported DPI. Preserve
  backend DPI snapping as a safety fallback and show the effective value.
- [x] Print panel: copies, Two-sided binding and a printer selector only when
  more than one printer exists. Route upload, progress and cancel to the same
  selected sensor. Require a clear selection when the target is ambiguous.
- [x] Keep back order in the manual reload step, with First sheet first and
  Last sheet first guidance. Do not move it into ordinary print/scan defaults.
- [x] Add the optional options-only duplex layout without changing the default
  visible switch. Keep panel contents usable at mobile widths without clipping.
- [x] Match editor naming, entity selection, defaults, visibility and help text.
  Provide new-card stubs and preserve old configurations through normalization.
- [x] Freeze settings and target during upload/submission/running jobs. Snapshot
  the submitted options so later default changes cannot change the current job.
- [x] Preserve focused controls on state updates, return focus after closing
  options and announce status politely. Phone Back navigation confirmed.
- [x] Centralize strings for later translation.

Final audit complete: readable choice labels and helper text, correct displayed
defaults, safe clearing of optional overrides, English catalog/fallback/plurals,
heading focus, stable fields and live browser Back/Escape/narrow-label checks.
See the Phase 3 validation record for automated evidence and coverage limits.

Exit: every visible setting has an implemented backend path and supported
choices; stale metadata produces a useful rejection without a wrong job.
Switching printers resets or validates staged options. Reloading defaults is
predictable, and keyboard/screen-reader order follows the visible hierarchy.

## Phase 4 Job state and recovery consistency

Keep scan and print workflow logic separate while sharing how states are
presented. This phase covers jobs tracked by these integrations, including
service calls and another card/browser. Discovering unrelated jobs submitted
directly to a device is a separate protocol feature.

- [x] Make print follow pushed sensor state before a local submission, matching
  scan. Recover the tracked job after reconnect or dashboard reload; clean up
  listeners when detached and prevent duplicate subscriptions.
- [x] Identify jobs by integration/entity plus job ID and request generation.
  Guard start, resume, cancel, target changes and delayed replies against stale
  updates. A cancellation must never apply to another printer's equal job ID.
- [x] Use actual page counts; show indeterminate progress when total is unknown.
  Preserve manual-front/back counts and the explicit waiting state.
- [x] Add checked availability with bounded polling/backoff, a last-check time,
  and distinct unknown/unreachable states. Idle alone does not mean online.
  Reuse identity from the selected integration instead of combining unrelated
  legacy printer availability entities into a single claim.
- [x] Align completion acknowledgement and error/detail behavior. Keep actionable
  configuration/load failures distinguishable from device/job failures.
  Show recovery guidance for busy/empty feeder, unavailable device, mismatched
  backs and ambiguous print submission; never encourage blind resubmission.
- [x] Extract only proven common presentation helpers into a small canonical
  plain-JS core, vendored at a pinned contract version in each integration.
  Add fixture/parity checks and a documented update procedure. Avoid globally
  shared custom element names that collide when versions differ.
- [x] If helpers become separate assets, hash and register the whole asset set.
  Core remains inline; no extra asset set is required. Test upgrade, integration
  reload, restore to an earlier release, duplicate
  resource cleanup and early element registration in both integrations.

Exit: two cards and two browsers agree on the same tracked job; reconnects,
target changes and delayed responses cannot corrupt the active state. Offline
and unknown are honest. Existing cancellation, scanner ownership, two-pass
privacy, timeout and file cleanup guarantees remain intact.

Validation and explicit live-test limits: [Phase 4 record](shared-card-phase-4-validation.md).

## Phase 5 Native Tile and optional Mushroom features

Move shell responsibility to the supported host once behavior is stable.

- [x] Register domain-specific scan and print custom features using the
  documented feature context, support checks, editor and default configuration.
  Reuse Phase 4 presentation helpers and adapters; avoid a second state machine.
- [x] Let Tile supply identity and surface styling. Features supply task controls
  and options. Check narrow feature rows without squeezing controls below usable
  targets or duplicating the host header.
- [x] Test current Mushroom Template as an optional alternate host. Document
  tested versions and distinguish it from legacy Template behavior. Bubble and
  Button card remain visual references unless separately verified as hosts.
- [x] Keep both old standalone types as supported wrappers, using the same
  presentation contract. Supply side-by-side Sections, native Tile and optional
  Mushroom examples. Migration is optional and does not rewrite dashboards.
- [x] Verify both integrations alone, both together and differing shared-core
  versions. Keep assets local and independently installable.

Exit: refresh/update and Android registration work, native hosts remove shell
styling, and standalone configurations retain their behavior. Promote the native
feature example to the recommended new-dashboard path only after this gate.

Implementation, host and physical Android acceptance: [Phase 5 validation](shared-card-phase-5-validation.md).

## Phase 6 Durable results and recent activity

Implemented and installed as scan 0.12.0 / print 0.11.0.
[Validation, storage and release evidence](shared-card-phase-6-validation.md).
Phone acceptance and the HP refresh/restart/download test passed.
[Live test evidence](phase-6-hp-live-tests-2026-10-09.md).

- [x] Preserve discoverable latest completed scan metadata beyond the active
  sensor's completion timer. Reconcile metadata against stored files and
  retention on restart; expire dead links without extending retention silently.
- [x] Provide authenticated Open/Download actions and clear expired/unavailable
  handling. Never expose private front-side files from an incomplete duplex job.
- [x] Keep the completion acknowledgement transient while latest-result access
  remains available. Do not rely on a longer frontend timer for durability.
- [x] Add bounded print activity metadata with a documented lifetime. Do not
  retain uploaded documents or offer reprint unless a separate storage policy
  is designed. Printer success describes reported device completion.
- [x] If scan history expands beyond Latest scan, define record limits, cleanup,
  restart recovery, permissions and storage migration in a separate decision.

Exit: latest scan remains accessible after card/HA reload while retained; purge
removes its action; incomplete/canceled results never appear. Print and scan
activity use the same presentation without claiming identical file retention.

## Follow on options

The six-phase rollout is closed. The next authorized work is compatibility:
real HP discovery in an isolated setup, the card-mod Options warning, and
structured reports for additional devices/bridges. See the
[bounded follow-up plan](compatibility-follow-up-2026-10-09.md). Multiple scanner
entries, presets and reviewed translations remain separately scoped follow-ons.

These have their own backend or product decisions and must not delay the common
card platform. Add each only after capability handling and an end-to-end path
exist; use the Phase 3 panel rather than adding competing main buttons.

| Option | Required work and acceptance gate |
| --- | --- |
| Per-job back rotation | Add service/start override and snapshot it for both passes; verify upright labeled backs in both input orders |
| Scan paper size or region | Model per-source geometry and device limits; verify Letter/A4 without clipping or the HP's extra Legal-height space |
| Print paper, color and quality | Parse supported/default IPP attributes, validate explicit choices and verify actual output; keep fresh media behavior |
| JPEG scan output or image-to-PDF | Decide conversion/dependency and output contract; bound memory and validate multi-page results |
| Presets and remembered settings | Define per-card/device scope, storage, reset and migration; never reuse invalid settings on a different device |
| Localization | Translate centralized strings, editor labels and recovery guidance; exercise long translated text |
| Optional quick print | Clearly label immediate submission, define defaults, and test cancellation/duplicate prevention |

## Work packages and release process

Keep changes reviewable: contract/fixtures, scan polish, print staging/polish,
capability metadata, upload validation, settings/editor, job state, resource
loading, feature hosts and latest result should be separate meaningful commits
or PRs. A milestone can contain several; every merged increment stays usable.
API support merges before its controls. Do not combine protocol, storage and
visual rewrites into one release.

Track phase checkboxes here and project-specific status in each `next-up.md`.
Pin the shared contract/core revision in both repositories and record tested
scan/print release pairs when shared behavior changes. Independent releases
must remain compatible with old API clients and the other installed card version.

For each behavior release, update that project's manifest version, changelog,
README and examples. Run its required checks and all hosted CI jobs, then publish
the matching HACS release tag. Documentation-only planning needs no version bump
or release tag. Choose version numbers at release time rather than reserving
a series that may be interrupted by bug fixes.

## Validation and rollback

Use focused behavior tests for changed logic and shared visual fixtures for the
design. Do not create tests that merely mirror CSS declarations.

| Area | Release gate |
| --- | --- |
| Automated checks | Scan pytest, Ruff, and card tests after npm ci; print compileall, pytest, Ruff, and card tests after npm ci; both hosted validation workflows green |
| Layout and themes | 320/390/768px viewport, narrow side-by-side cards and direct Sections, light/dark/custom themes, long names and readable expanded attention states |
| Accessibility | Keyboard activation, focus/return, labelled switches/buttons, no nested action targets, usable touch targets, polite status and reduced motion |
| Compatibility | Existing YAML/types/entities, declared minimum/current HA, non-admin dashboard access, Android app, refresh/reload/update and separate installs |
| Behavior | No submission from settings/file selection; one submission from action; settings frozen; external integration jobs, reconnect, cancel, stale replies and multi-printer routing |
| Hardware | HP simplex and labeled two-pass scan, both back orders, print copies/one-sided/long-edge/short-edge; inspect page count/order/orientation and reported completion |
| Unsupported hardware | Automatic duplex needs a capable scanner; fixtures cover selection until hardware is available, and release notes state that limit |

Before live installation, record installed versions and back up both integrations
and dashboard YAML. Install only when scan/print work is idle, then verify the
new resource URLs and physical phone before starting a job. Retain the known
working releases and standalone examples so an optional host failure does not
require redesigning the dashboard again.

Rollback restores the affected integration and its dashboard example. Keep APIs
additive through Phases 1–5, preserve entity IDs, and test old/new frontend and
backend combinations. Phase 6 persistence needs an explicit backward-compatible
storage decision before release. Never restart during a manual reload pause or
automatically replay a scan/print as part of rollback.

## Implementation starting points

Line references describe the baselines above and may move during implementation.

| Work | Scan repository | Print repository |
| --- | --- | --- |
| Controls and sizing | `custom_components/escl_scan/static/card.js:32`, `:56`, `:95` | `custom_components/ipp_print/static/card.js:29`, `:42`, `:44` |
| Capability metadata | `custom_components/escl_scan/coordinator.py:362`, `sensor.py:72` | `custom_components/ipp_print/printer.py:140`, `sensor.py:99` |
| Job options | `custom_components/escl_scan/coordinator.py:415` | `custom_components/ipp_print/__init__.py:349`, `:537` |
| State and retention | `custom_components/escl_scan/static/card.js:421`, `coordinator.py:936`, `:1013` | `custom_components/ipp_print/coordinator.py:149`, `static/card.js:203` |
| Resource loading | `custom_components/escl_scan/__init__.py:65` | `custom_components/ipp_print/__init__.py:99`, `:236` |

Preserve the accepted [manual duplex decision](decisions/2026-10-08-manual-duplex.md)
and the printer's [sensor routing](https://github.com/wleonhardt/ha-ipp-print/blob/main/plans/decisions/2026-10-08-multiple-printers.md)
and [bounded payload](https://github.com/wleonhardt/ha-ipp-print/blob/main/plans/decisions/2026-10-08-bounded-print-payload.md)
decisions. The design references and their checked dates remain in the linked
review; this plan uses their documented extension points without adding a
frontend runtime dependency.
