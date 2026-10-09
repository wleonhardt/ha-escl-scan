# Compatibility rollout validation

Repository target versions: scan 0.8.0 / print 0.7.0. Installed versions remain
scan 0.7.1 / print 0.6.1, verified from their deployed manifests. Release tags and
installation are a separate gate after the pending physical check; no production
files or running jobs were changed during this implementation.

## Automated checks

- Scan: 208 Python tests, 45 card tests; Ruff passes.
- Print: 202 Python tests, 34 card tests; Ruff and compileall pass.
- Both npm dependencies installed with npm ci; JSON/service definitions parse;
  diff whitespace checks clean. Hosted validation is checked on the pushed heads.
- Total: 489 tests. Fixtures distinguish a redacted live HP capability capture
  from synthetic devices. Tests include profile references/ranges/combinations,
  image conversion dimensions and manual-duplex order, conversion cancellation,
  origin/port restrictions, recovery exhaustion/deadlines, IPP collection bounds,
  read-only version negotiation, preflight rejection, queue identity and UI races.

## Read-only device and bridge probes

- HP M283fdw eSCL: both source profiles parse; color/gray at 300 DPI select native
  PDF with the extension. Simplex feeder remains independent of duplex printing.
- HP direct IPP: PDF settings query and Validate-Job for one copy/one-sided with
  default paper pass. Advertises PDF/JPEG (not PNG), 25 media keywords, four media
  sources, auto/auto-monochrome/monochrome/color and qualities 3/4.
- Found a live compatibility regression before delivery: requesting
  media-col-database returned Content-Length 938053 and stalled after 226902
  bytes within the read budget. Removed that expansion from routine reads.
  The smaller queries and preflight then passed. No response-bound increases.
- Local CUPS queue to HP: format-specific PDF settings parse, including typed
  collections; Validate-Job succeeds. This does not verify physical conversion
  output or remote HA network reachability to the local queue.
- No physical print or scan jobs were submitted by these probes.

## Browser verification

BrowserOS Neo isolated local fixture with simulated APIs: paired narrow/wide cards,
light/dark themes and native Options dialogs checked visually. Controls remain
inside the card/dialog width; Escape returns focus to Options. The modal avoids
expanding a fixed-height Sections tile. Native icons are supplied by HA in the real
host; this standalone fixture stubs the host surface. This is not phone hardware or
an installed-version check.

## Physical and external gates

1. Preserve the Phase 2 four-sheet output confirmation. Installation was previously
   tested; the human output-order/copy/binding confirmation remains outstanding.
2. On the new release candidate, one Letter scan, one manual duplex batch and one
   print with selected options. Confirm output dimensions, page order/orientation,
   Download PDF, filename clearing and no extra jobs on rejection.
3. Automatic-duplex ADF requires different hardware; this HP scans one side only.
4. Brother/Xerox/Ricoh quirks, image-only hardware, AirSane and ipp-usb require
   actual device/bridge runs before claiming physical support.
5. Native hosting/history remain in later shared-card phases. Native WSD, new
   authentication and embedded rendering have separate evidence-gated proposals.

Rollback when installation is undertaken: back up both deployed integrations and
Lovelace resources first; restore the prior pair and restart HA if setup fails.
Retain the existing card/entity IDs and document the actual installed hashes.
