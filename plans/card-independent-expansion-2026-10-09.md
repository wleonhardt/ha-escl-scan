# Independent expansion of paired document cards

Status: dashboard fix applied on HA 2026.9.4; browser validation passed.
Installed integrations remain scan 0.12.0 / print 0.11.0. This changes dashboard
configuration, examples and documentation only; no runtime update or tag is needed.
Physical phone acceptance passed: on 2026-10-09 the user supplied a follow-up
recording and confirmed the layout looks good and expansion is very smooth.

## Cause and correction

The phone video shows Recent activity expanding Print and pulling Scan's header
and controls down. Sections stretches both direct children to the taller row.
The native Tile fills that height and distributes surplus space above its
features. The standalone horizontal-stack pair has the same coupling through
its full-height surfaces and bottom-aligned actions. Rows: Auto allows growth
but does not stop the shorter card stretching with its neighbour.

Place each card in its own built-in Vertical stack. For Sections, move the
six-column / Auto row sizing to the stack. For horizontal-stack layouts, make
the two children Vertical stacks, each containing its original document card.
The inner cards then size to their own contents. This also works with current
Mushroom Template hosts. Keep native host styling, independent card lifecycles,
entity targets, history details and browser Back behavior intact.

No card-mod, CSS overrides, runtime host shadow-root traversal, height syncing,
fixed heights or new dependency is introduced. Users of existing paired layouts
need to apply this dashboard configuration once; updating an integration alone
does not rewrite their dashboard. Examples and both READMEs show the correction.

## Validation

- Reproduced in the real Sections Tile layout and standalone horizontal stack.
  At 390 px, opening Print moved the neighbouring Scan actions down 200 px.
- Verified each independently open, both open, both closed, and collapse after
  expansion at 320, 390 and 768 px. Native Tile, current Mushroom Template and
  standalone cards all pass: no horizontal overflow, unchanged card top,
  unchanged status/switch/action/summary positions, and unchanged height of a
  collapsed neighbour. At 390 px the native cards stay 284 px tall when closed;
  Scan alone grows to 560 px and Print alone to 484 px with the retained records.
- Checked actual Home Assistant layout hosts. Earlier isolated preview fixtures
  used `align-items: start`, which prevented this coupling and hid the defect.
  Future paired-layout acceptance must include the actual dashboard containers
  and asymmetric expansion, not only equal-height or both-open fixtures.
- Backed up dashboard storage before saving:
  `/config/.document-card-backups/before-independent-expansion-20261009.json`.
- Updated only the document-card pairs on `/lovelace/native-documents` and
  `/lovelace/printer`. Preserved original child settings and all other views.
  Read-back matches the intended configuration; fresh loads of both views pass
  the same expansion checks. No device job was submitted or service restarted.
- Scan and Print Options open in the wrapped native cards; browser Back closes
  each dialog while preserving the dashboard and disclosure state.
- All dashboard YAML examples parse. All required local checks pass after
  `npm ci`: Scan 240 Python + 77 card; Print 229 Python + 64 card (610 total),
  Ruff in both repositories and Print compileall. Runtime assets are unchanged.
