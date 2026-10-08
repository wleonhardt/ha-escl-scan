# Shared scan and print card design review

Status: proposal for ha-escl-scan and ha-ipp-print, 2026-10-08.

Use Home Assistant Tile as the shared visual foundation. Keep one primary action
per task, expose Two-sided as a setting, and put occasional settings in an
options panel. Prefer custom card features hosted by native Tile or compatible
Mushroom cards for the smallest styling surface. Keep the existing standalone
card types as compatible wrappers while this path is validated. Both integrations
remain independently installable, with plain JavaScript and no required HACS
frontend dependency.

## Problems in the current cards

The live dashboard at 390px viewport width gives each card 183px. The scan card
is about 160px tall and the print card 130px. Duplex is a second start action
inside a card whose surrounding surface is also a start action. Enlarging it
improved the target but made the action hierarchy and unequal heights more
obvious. A Two-sided setting followed by one Scan action expresses intent better.

The scanner overrides the card radius with 18px and adds permanent accent fill
and border. The printer inherits the card surface and radius. The scan tint also
falls back to blue independently of the theme's primary color. A shared neutral
surface would remove these differences and let active state accents carry meaning.
Both cards use centered 20px bold headings and large blank click areas, then
shrink essential text to 11px at narrow widths. Reflowing content is preferable
to reducing readability. Cancel is an 11px div acting as a button; replace it
with a real button and adequate touch target.

Both outer cards have button semantics, and the scan card nests controls and
links inside that button-like region. Separate navigation, settings and action
targets. Changing a switch must never start a job. Keyboard activation and
screen-reader order should follow native control semantics.

Print PDF is inaccurate because the upload card already accepts JPEG and PNG.
Use Scan and Print as task names; use Choose file before a print document is
selected. Default print flow should stage the selected file and settings before
an explicit Print action. Retaining an optional quick-print flow is possible,
but its immediate submission must be clear.

The frontend behavior has also drifted. Scan follows pushed sensor state,
including jobs begun elsewhere; print starts its progress subscription after
this card submits a job. Print completion clears after 10 seconds, scan after
30 seconds, and the scan's Open scan link disappears with that presentation
latch even while its file can remain valid. Common state rendering should cover
external jobs, reconnection and discoverable results. A durable latest-result
feature needs backend support beyond extending a frontend timer.

The dashboard's separate printer-offline presentation uses another integration.
Job idle does not establish device availability. The shared cards should use
consistent device identity and distinguish idle, unreachable and unknown status.

Source: `custom_components/escl_scan/static/card.js` and
`../ha-ipp-print/custom_components/ipp_print/static/card.js`, including their
rendering, click handlers, progress handling and result timers.

## Patterns to borrow

| Reference | Useful pattern | Application |
| --- | --- | --- |
| [Home Assistant Tile](https://www.home-assistant.io/dashboards/tile/) | Entity identity and state, separate actions, bottom or inline features | Primary visual foundation and host-owned appearance |
| [Mushroom](https://github.com/piitaya/lovelace-mushroom) | Visual configuration, restrained identity and state, light and dark support | Friendly editor and sensible defaults |
| [Current Mushroom Template](https://github.com/piitaya/lovelace-mushroom/blob/main/docs/cards/template.md) | Tile-based design and feature support | Optional alternate host; legacy Mushroom theme compatibility differs |
| [Bubble Card](https://github.com/Clooos/Bubble-Card) | Sub-buttons and pop-ups for secondary controls | Options entry point and mobile detail flow, without making pill styling mandatory |
| [Button card](https://github.com/custom-cards/button-card) | Reusable layouts, configurable actions and templates | Design contract and action consistency; do not require users to author CSS |

These are reference patterns, not runtime dependencies. Matching every custom
dashboard perfectly would require dashboard-specific configuration; using the
same host and theme settings for both tasks provides a much stronger default.

## Two sided control and options

Prefer the visible Two-sided switch when duplex is used often. A settings-only
version is smaller and useful for dashboards where defaults rarely change.
A One-sided / Two-sided segmented choice is clearer for unfamiliar users but
costs more width. An icon-only toggle and a long-press-only option are weak
defaults because their meaning and availability are harder to discover.

The switch sets the next job's intent and performs no network operation.
Initialize it from explicit card or integration defaults; make any remembered
preference policy visible and consistent. Freeze job settings after submission.
On this HP, Two-sided scanning means Feeder and two manual passes; say this
before starting. Never silently turn a glass scan into a feeder scan. On automatic
duplex scanners, show the detected automatic method. Unknown capabilities should
remain unknown until checked rather than masquerading as unsupported hardware.

| Option | Placement | Current implementation boundary |
| --- | --- | --- |
| Scan Two-sided | Visible switch or options panel | Start API supports it; automatic versus manual selected by backend |
| Scan source | Options: Auto, Feeder, Glass | Auto maps to omitted source; Glass maps to Platen |
| Scan color | Options: Color, Grayscale | Both supported by start API |
| Scan resolution | Options, with device-supported choices | DPI override exists; frontend needs capability information for valid choices |
| Back-side order | Only while waiting for backs | Existing resume API supports same or reversed order |
| Rotate backs | Advanced, later | Integration option exists; per-job override does not |
| Print device | Options, only with multiple printers | Backend selection by sensor exists; card editor and runtime selection need improvement |
| Print copies | Options | Print service supports copies; multipart upload endpoint currently accepts only file and entity_id |
| Print Two-sided and binding | Switch plus advanced long/short edge choice | Print service supports sides; upload endpoint requires extension and validation |
| Paper size, print color and quality, scan image output | Later capability work | Do not expose working-looking controls until these paths are implemented |
| Save folder, credentials, retention | Integration settings | Installation concerns and path policy should stay out of ordinary job controls |

Idle sensors currently expose only null job/scan IDs, not usable capability
metadata. Add cached capability access or suitable attributes before promising
capability-aware selectors. Keep backend validation authoritative.

## Shared appearance and behavior contract

Use the same header, icon size, spacing, status placement, options affordance,
main action and cancellation treatment in both cards. Neutral idle surfaces
inherit the host's background, border, radius and shadow. Accent the icon or
active control; avoid a permanent tinted scan surface. Use native Home Assistant
icons, theme text/status colors, and component tokens instead of authored icon
paths, RGB fallbacks or a required card-mod stylesheet.

For custom features, Home Assistant documents `--feature-height`,
`--feature-border-radius` and `--feature-button-spacing`. These provide the
shared control geometry. Effective mobile targets should remain about 44px even
when visible icons and switches are small. Respect reduced motion, preserve
focus styling and pair state colors with text.

Put each card directly in a Sections grid with matching span and sizing rules;
the current horizontal stack cannot independently reflow its two children.
Add `getGridOptions` to standalone wrappers, alongside masonry `getCardSize`.
Match idle and ordinary running heights. Long reload instructions and errors
should move into a clearly discoverable detail panel or an expanded active card,
where readability is more important than forcing equal heights.

Normalize presentation into Ready, Preparing, Running, Needs attention, Complete,
Error and Unavailable. Map integration states into these categories without
changing their backend lifecycles. A manual reload pause is Needs attention.
Preserve job IDs and stale-response protection; shared appearance must not
discard cancellation and progress guarantees. Show real page counts and use
indeterminate progress when a total is unknown. Do not invent percentages.

Keep concise recovery text on the card, with details available in the panel.
Use accessible native buttons and switches, polite status announcements, real
disabled states and focus return after closing options. All essential controls
must work without hover or long press.

## Shared implementation platform

[Custom card features](https://developers.home-assistant.io/docs/frontend/custom-ui/custom-card-feature/)
are a documented extension point. A scan feature and print feature can share
their presentation and consume the host's entity context while adapters provide
their different requests, capabilities and workflow actions. Native Tile supplies
the visual shell; current Mushroom Template supports features too. Bubble is a
design reference, not an assumed compatible feature host.

Preserve `custom:escl-scan-card` and `custom:ipp-print-upload-card` as wrappers
for existing dashboards. Validate the feature path against supported HA versions
and the actual Android app before making it the default. Reusing documented
feature contracts is preferable to accessing private Tile shadow DOM or relying
on undocumented internal components that happen to exist in a recent release.

Initially share a versioned specification, minimal presentation helpers and
the same preview fixtures. A small canonical plain-JS core can be vendored at a
pinned version into both independently distributed integrations, with parity
checks preventing accidental drift. Keep scan/print transport and workflow
adapters separate. Avoid a third required integration, a remote runtime script,
a framework rewrite or a large universal configuration schema. If shared files
are imported separately, registration and content hashing must cover every
asset; otherwise mobile update/cache failures will return.

## Delivery order and acceptance criteria

1. Replace competing duplex start action with next-job setting and one Scan
   action. Unify neutral surfaces, labels, touch controls and idle dimensions.
2. Add a shared options panel and matching visual editors. Expose existing scan
   request options first; extend print upload metadata before adding copies/sides.
3. Validate native custom feature hosting and keep compatible wrappers. Add
   capability discovery, consistent external-job state and reconnect behavior.
4. Add durable latest-result/history access after storage and API support exist.

Accept both cards together across 320, 390 and 768px layouts, direct Sections
placement and horizontal stacks, light/dark/custom themes, supported HA versions,
keyboard and Android app usage. Exercise idle, upload, scanning/printing, manual
reload, cancel, offline, failure, completion and another device starting a job.
Visual fixtures should catch mismatched surfaces, radii, dimensions and controls;
behavior checks should catch switch clicks starting jobs and stale replies
changing current state. Feature registration must survive refresh and updates.

The interactive concept illustrates visible switches and options on demand.
Its print settings describe proposed functionality rather than installed upload
API support. The concept is separate from the deployed integration UI.

References checked 2026-10-08. Home Assistant's
[custom card documentation](https://developers.home-assistant.io/docs/frontend/custom-ui/custom-card/)
also documents Sections sizing and card editors.
