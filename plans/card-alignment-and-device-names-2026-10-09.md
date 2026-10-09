# Paired card alignment and device identity

Status: implementation and live validation in progress for scan 0.11.2 /
print 0.10.3. No backend or device job changes.

The phone screenshot exposed uneven headings and Two-sided rows. On the real
HA 2026.9.4 Tile host, Print's feature was 28 px taller: its file hint occupied
20 px below the switch and an empty warning element introduced another 8 px
flex gap. Tile centered its header in the remaining space, shifting Scan's
header and status downward. This is a shared layout defect, not phone caching.

Put Scan's hint on its own full-width row below the 44 px switch row, retain the
label and describe the switch with that hint for accessibility. Collapse empty
warnings and use the shared 40 px minimum status area for both native features,
allowing up to two idle lines without drift. Long warnings, filenames and manual
instructions still expand. No shadow-root host overrides, card-mod selectors,
fixed card heights or inter-card measurement/synchronization are introduced.
Different active workflows can have different heights; native hosts retain
control of their own headers and surfaces.

## Naming decision

Keep identity with the native host. Prefer a native Heading such as “Office
printer” over each Scan/Print pair. For ungrouped cards, use names such as
“Office · Print” and “Study · Print”, each with an explicit target sensor. Use
friendly names before model numbers, which can be identical across devices.
Keep names stable instead of hiding them based on global device counts; counts
do not describe which cards are visible on a given dashboard. Existing titles
remain supported. No automatic device-count/name policy is added to features.

Print already supports multiple entries and isolates native feature targets.
Scan currently rejects a second configured scanner. Before promising multiple
scanner cards, a separate backend phase must cover entry-scoped sensor IDs,
service/view routing, discovery, independent job/file retention and cancellation,
and rejection of ambiguous requests. Removing the config-flow guard alone is
not sufficient. Keep this follow-up separate from the Phase 6 history work.

## Validation

Local checks pass: Scan 225 Python / 72 card tests; Print 220 Python / 62 card
tests (579 total), npm ci, Ruff, print compileall, shared-core parity and YAML
example parsing. Final candidate assets align heading, status, switch and action
positions at 320, 390 and 768 px in the real HA Tile host with no horizontal
overflow. At 320 px, Choose file wraps: a shared container query allows a 56 px
action row on cards narrower than 150 px; wider cards retain 44 px controls.
A separate two-printer fixture shows Office / Study names and distinct sensor
targets, with all device requests blocked. Release/deployment checks pending.
