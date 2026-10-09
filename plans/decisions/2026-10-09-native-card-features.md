# Native scan and print features

Status: released and installed as scan 0.11.1 / print 0.10.1. Keep standalone cards supported and the visible
Two-sided switch as the default. Host and physical Android acceptance are
recorded; native Tiles are recommended for new dashboards. Migration stays optional.

Register `escl-scan-feature` and `ipp-print-feature` in the existing, independently
served card modules. A small domain-scoped adapter owns host context and embeds
the existing workflow element in a surface-free presentation. The native Tile
or current Mushroom Template owns the only header, background and border.
No second job state machine, global cross-integration element, dependency or
runtime asset is introduced. Vendor the shared adapter/styles as core v3.

The parent must target the integration's job sensor. Consume modern `context`
and legacy `stateObj`; once modern context has been supplied, it is authoritative
even when empty. Area-only and unrelated entities show guidance without an
action. Never infer a different printer or honor a nested feature entity override.
Replace the embedded workflow when the parent entity changes, so staged files,
unfinished requests and completed downloads cannot migrate to another device.
Keep the instance stable for normal state pushes and host disconnect/reconnect.

Feature defaults and the visual editor reuse the standalone schema, omitting
the host-owned title/entity. Bottom-position features can expand for progress,
errors, staged documents and manual-back instructions. Native examples use auto
height in Sections; inline placement is unsupported and explains the correction.
Stop control gestures from also triggering the host card's tap/hold actions.
Options keeps the existing HA dialog/Back-navigation contract.

Primary references checked 2026-10-09:
- [Official feature contract](https://developers.home-assistant.io/docs/frontend/custom-ui/custom-card-feature/)
- [HA 2024.12 feature host](https://github.com/home-assistant/frontend/blob/20241127.4/src/panels/lovelace/card-features/hui-card-feature.ts)
- [Current feature host](https://github.com/home-assistant/frontend/blob/dev/src/panels/lovelace/card-features/hui-card-feature.ts)
- [Current Mushroom Template](https://github.com/piitaya/lovelace-mushroom/blob/main/docs/cards/template.md)

Validate routing, stale legacy context, entity changes while submitting, remount,
manual duplex/download, visual editor defaults, events, independent installs and
mixed core versions. Inspect real native Tile and installed Mushroom at narrow
and desktop widths. Record actual minimum/current runtime and Android evidence
separately; source inspection alone does not establish minimum-version runtime
or physical phone acceptance. No physical job is needed for host layout testing.
