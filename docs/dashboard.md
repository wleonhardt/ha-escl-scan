# Dashboard cards

[Documentation](README.md) · [Next: scanning](scanning.md)

## Native Tile card — recommended

Add a **Tile** card, select this integration's **Current scan** sensor, then add
**eSCL Scan** in its **Features** picker. Keep **Features position: Bottom** and,
in Sections, **Rows: Auto**. Choose the job sensor, not the Connection sensor.

Or use the card editor's YAML mode:

```yaml
type: tile
entity: sensor.printer_current_scan
name: Scan
icon: mdi:scanner
hide_state: true
tap_action:
  action: none
icon_tap_action:
  action: none
features_position: bottom
grid_options:
  columns: 6
  rows: auto
features:
  - type: custom:escl-scan-feature
    duplex: false
```

Replace `entity` with the actual sensor ID from your device page. The feature
inherits its device from the parent card; set the title with the parent's `name`.
Inline feature placement is not supported.

## Standalone card

The standalone card includes its own heading. Add **eSCL Scan**
from the card picker, or use:

```yaml
type: custom:escl-scan-card
entity: sensor.printer_current_scan
title: Scan
grid_options:
  columns: 6
  rows: auto
```

With one scanner, `entity` can be omitted for automatic selection.
A renamed sensor can also be set explicitly.
Existing standalone cards continue to work; updates do not migrate your dashboard.

## Put Scan and Print beside each other

Wrap **each card in its own Vertical stack**. This prevents an expanded history
section from stretching the neighboring card. In Sections, size each stack to
**6 columns / Rows: Auto**; in a Horizontal stack, place one Vertical stack on
each side. No card-mod or CSS is needed.

Use a Heading card such as **Office printer** above the pair, or name separate
cards **Office · Scan** and **Office · Print**. Friendly room/device names are
clearer than model numbers when devices share a model.

Print supports several printers, but Scan currently supports only one scanner per Home Assistant instance.

- [Paired native Sections layout](../examples/dashboard-native-sections.yaml)
- [Paired standalone Sections layout](../examples/dashboard-sections.yaml)
- [All dashboard examples](../examples/README.md)

## Mushroom

The current **Mushroom Template** card can host the same feature. Use the
[Mushroom example](../examples/dashboard-mushroom.yaml), not Legacy Template.
Mushroom is optional; the Tile and standalone cards do not require it.

## Card defaults

The visual editor exposes the defaults below. On a native Tile or Mushroom
card, put these under the feature configuration. On a standalone card, put them
at the top level alongside `type` and `entity`.

| Option | Default | Meaning |
| --- | --- | --- |
| `duplex` | `false` | Initial Two-sided switch; on selects the feeder. |
| `source` | `auto` | `auto`, `Platen` (glass), or `Feeder`. |
| `color` | `default` | `default`, `color`, or `gray`. |
| `dpi` | Omitted | Integration default; set an integer from 50–1200 to override. |
| `page_size` | `full` | `full`, `letter`, or `a4`. Custom dimensions are chosen in the Options dialog. |
| `duplex_in_options` | `false` | Move the Two-sided switch into Options. |

The card explicitly chooses one-sided or two-sided scanning; it overrides the integration’s duplex default. Omitted color and DPI still use the integration defaults.
Changes made in Options affect subsequent jobs while the card stays mounted;
reloading restores the configured card defaults. Settings are locked during
active work. The sliders button opens Options; **Done** or browser Back closes it.

## Resources and themes

The integration registers the card module automatically using a content-hashed
URL, and provides global loading for YAML resource configurations. Do not add a
second copy of the JavaScript through HACS or a manual resource entry.

Cards inherit the dashboard theme. Leave height automatic so errors, filenames
and activity can expand. For loading problems, see
[card troubleshooting](troubleshooting.md#card-does-not-load).
