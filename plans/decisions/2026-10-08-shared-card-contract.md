# Shared document card contract

Status: accepted for the first standalone card release. Contract version 1.

## Distribution and compatibility

Keep `custom:escl-scan-card` and `custom:ipp-print-upload-card`, their entity
routing and early registration. Both remain plain JavaScript, independently
installed through their integrations, with no new runtime dependency.

Phase 1 shares a specification, identical base styling and visual fixtures.
Keep that base styling in each card's single served module so the existing
content hash covers every runtime asset. A later shared module requires an
asset registration/cache decision; do not extract one prematurely.

Native Tile/current Mushroom Template features remain experimental until the
host/version/mobile checks pass. The existing minimum HA version stays 2024.12.
The prototype has no device actions and never alters saved dashboard config.

## Presentation

Use a neutral `ha-card`, inherited surface/border/radius/shadow, a 24px native
icon, 16px medium title, 14px readable status and 12px padding. Use an 8px layout
gap and a 44px minimum action/label target. The switch itself is compact.
Cards share a 200px minimum height; details and manual reload may expand.
Sections defaults are six columns and four rows; masonry sizing remains three.

Primary text, secondary text, primary, error, success and divider colors come
from HA theme variables. No fixed scan tint, RGB fallback, card hover glow,
outer button role, custom SVG icon paths or shrinking mobile text. Use visible
focus and semantic buttons, labelled switches and polite status announcements.
Only action/control elements are interactive. Keep host theme surfaces intact.

Ready, Preparing, Running, Needs attention, Complete, Error and Unavailable
are the common presentation vocabulary. Idle is not evidence of reachability.
Keep the existing backend lifecycles and domain-specific progress adapters.
No fabricated percentage or unconditional online claim.

## Scan intent

One Scan button submits. Two-sided is a next-job switch and never calls the
server itself. Off explicitly sends `duplex: false`; on sends `duplex: true`
and `source: Feeder`. The feeder requirement is visible beside the setting,
including the possibility of two passes until capabilities can be shown.

Add a boolean `duplex` card default (false), editable visually. This card
default intentionally overrides the integration's duplex default so the switch
always describes the request. Other scan defaults still come from the backend.
Remember the switch only for the current card instance, reset on a new explicit
card default or remount, and freeze it from submission through job completion.
Source selection and capability-specific method labels belong to later phases.

## Print intent

Choose file only stages a PDF/JPEG/PNG locally. Show the filename with Replace
and Clear, then require Print. Canceling a replacement picker preserves the
staged file. Lock file changes while submitting or following an active job.
Keep the existing server size/format validation as the authority.

Release the selected file after an accepted submission. An ambiguous transport
failure must not auto-retry or leave an inviting repeat-Print action: clear the
staged selection and explain that the printer queue must be checked. A known
validation rejection can retain the file for correction. Print copies/sides
controls wait for the upload API extension.

## Capability boundary

Phase 2 will use authenticated, entity-scoped capability views with compact
versioned responses and backend caching. Stable job attributes stay compatible;
large capability sets do not belong in every sensor state/recorder update.
The backend validates settings and reports unknown/stale capabilities honestly.

## Verification

Use the same fixture scenarios and inspect both cards together at narrow mobile
and wider widths, in light/dark/custom themes. Behavior tests cover action
separation, staged file lifecycle, duplicate prevention, frozen options, stale
responses and existing manual duplex/cancel guarantees. Native-host and physical
Android results are recorded separately from simulated browser layouts.
