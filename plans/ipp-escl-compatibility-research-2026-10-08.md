# IPP and eSCL compatibility research

Research and recommendations, 2026-10-08. Local code reviewed: ha-escl-scan
`d82242f` and ha-ipp-print `c945729`. This is a proposed prerequisite and
extension to Phase 3, not a new accepted protocol contract.

The largest compatibility gains come from preserving the device's actual
capability combinations, selecting a supported transfer format, and handling
proven firmware exceptions. More controls alone will expose more ways to submit
invalid jobs. Keep the simple cards, improve their capability and submission
layers, and offer optional standard-protocol bridges for hardware that needs
conversion or a different driver.

## Comparable projects and useful patterns

| Project | What it does | Useful lesson for these integrations |
| --- | --- | --- |
| [OpenPrinting CUPS](https://openprinting.github.io/cups/doc/cupspm.html#detailed-destination-information) | Queries supported, default and ready values; exposes option conflicts and media dimensions/margins | Settings need dependencies and provenance, not just independent lists |
| [HP JIPP](https://github.com/HPInc/jipp) | Separates IPP packet parsing/building from PDL generation; demonstrates PDF-to-PWG-Raster/PCLm rendering | Speaking IPP and rendering a document are separate capabilities; a richer parser alone does not add PDF support |
| [sane-airscan](https://github.com/alexpevzner/sane-airscan) | eSCL and WSD client, source-specific capabilities and device workarounds | Best reference here for real scanner interoperability; use its documented exceptions to design targeted fixtures |
| [NAPS2](https://github.com/cyanfish/naps2/tree/master/NAPS2.Escl) | Explicit eSCL input capabilities, setting profiles, formats and resolution ranges, alongside a profile-based scanning application | Preserve profiles and references; keep ordinary scan intent separate from compatibility settings |
| [scanservjs](https://github.com/sbs20/scanservjs) | Browser UI over SANE with discovered settings, output processing and device overrides | Separate acquisition from output and keep overrides scoped to devices; its SANE/processing stack is substantial |
| [AirSane](https://github.com/SimulPiscator/AirSane) | Publishes SANE scanners through eSCL and supports JPEG, PNG and PDF/raster output | A possible optional route to older/USB/SANE-supported scanners while our integration remains an eSCL client |
| [ipp-usb](https://github.com/OpenPrinting/ipp-usb) | Proxies IPP/eSCL over USB and advertises network services; maintains device quirks | Support advertised endpoints and paths; an external bridge can handle IPP-over-USB-capable devices |
| [Home Assistant IPP](https://www.home-assistant.io/integrations/ipp/) | Discovers printers and monitors state, consumables and counters | Useful HA discovery/status precedent; its monitoring support does not establish print-job compatibility |
| [PWG IPP samples](https://github.com/istopwg/ippsample) and [ipptool](https://openprinting.github.io/cups/doc/man-ipptool.html) | Reference implementations, protocol test files and repeatable checks | Use as development/test counterparts; ippsample explicitly describes itself as non-production sample code |

These are complementary references, not interchangeable drop-in dependencies.
For example, scanservjs is a SANE frontend, AirSane is an eSCL server, and
sane-airscan is a scanner client. Their supported-device lists do not become
our supported-device list merely by adopting a similar design.

## Findings in the current clients

### 1 Format support is the biggest coverage boundary

IPP Everywhere requires PWG Raster, with JPEG required for color printers;
PDF is recommended. Therefore, a conforming driverless printer need not accept
our PDFs directly. Our print integration transfers PDF/JPEG/PNG without a
renderer. It cannot turn a PDF into PWG Raster, Apple Raster or PCLm.
[PWG requirements](https://www.pwg.org/ipp/everywhere.html),
[JIPP transport and rendering separation](https://github.com/HPInc/jipp).

A concrete correctness problem exists in `ipp_print/printer.py`:
`PrinterInfo.supports_format()` treats `application/octet-stream` as support
for every format. `test_supports_format_octet_stream_means_anything` currently
enshrines that assumption. The standard defines octet-stream as auto-sensing;
the device may still reject an unrecognized document, even after accepting the
job. Moreover, we currently send the explicit PDF/JPEG/PNG MIME type, not an
auto-sensing request. The capability API can consequently overstate support.
[RFC 8011 section 5.1.10.1](https://www.rfc-editor.org/rfc/rfc8011.html#section-5.1.10.1).

Recommended first fix: distinguish explicit format support, auto-sensing support,
and unknown support. An auto-sensing-only advertisement must not produce three
confirmed supported upload formats. A future opt-in auto-sensing path should be
reported honestly and must never retry an ambiguously accepted job.

Scanning has the inverse boundary. `escl_scan/scanner.py` defaults to requesting
PDF, emits only `scan:DocumentFormatExt`, and does not parse advertised transfer
formats. The coordinator accepts and assembles PDFs only. A scanner that offers
usable image formats can therefore still fail through our integration.
sane-airscan parses both format elements and writes `pwg:DocumentFormat`, adding
the extension when indicated; NAPS2 also models standard and extended formats.
[sane-airscan format handling](https://github.com/alexpevzner/sane-airscan/blob/master/airscan-escl.c),
[NAPS2 setting profile](https://github.com/cyanfish/naps2/blob/master/NAPS2.Escl/EsclSettingProfile.cs).

Recommended next capability: separate scanner transfer format from user output.
Keep PDF output and prefer native PDF when supported; allow JPEG/PNG acquisition
followed by bounded, off-event-loop PDF assembly. Specify a converter/dependency
and image size limits in a decision record before implementation. pypdf does not
by itself provide a general image decoder or PDF-to-printer raster pipeline.
Verify format element selection against fixtures before changing every device's
XML request.

### 2 Scanner settings need complete profiles

Our source separation for Platen, Feeder and FeederDuplex is a useful foundation.
Within each source, however, `parse_scanner_capabilities()` combines all descendant
colors and discrete resolutions into independent lists. It neither resolves
named profile references nor retains each profile's relationships. It only keeps
square discrete resolutions and does not model resolution ranges.

NAPS2's eSCL model preserves a list of setting profiles, each with color modes,
formats, discrete X/Y resolution pairs and X/Y ranges. Its parser resolves named
profiles through `ref`. This is a better representation to study before exposing
our DPI/color settings.
[NAPS2 input capabilities](https://github.com/cyanfish/naps2/blob/master/NAPS2.Escl/EsclInputCaps.cs),
[profile parser](https://github.com/cyanfish/naps2/blob/master/NAPS2.Escl/Client/CapabilitiesParser.cs).

Two read-only synthetic probes reproduced gaps in our current parser:

| Synthetic capability input | Current result | Compatibility risk |
| --- | --- | --- |
| One profile offers color at 300 DPI; another offers gray at 600 DPI | Color validation passes and DPI selection returns 600 | We can assemble a combination that no profile advertises |
| Source refers to a named top-level 300-DPI color profile | Source DPI/color lists remain empty; requested 275 remains 275 | We lose real restrictions and treat them as unknown |

These demonstrate parser behavior, not a claim that a particular physical model
has failed with these exact documents. Add these shapes as regression fixtures,
then collect actual capabilities from different manufacturers.

Preserve profile membership, resolve bounded references, handle documented range
forms and keep missing data distinct from an empty supported set. Select a valid
combination of source, duplex, color, transfer format and resolution. If square
DPI is our supported subset, report that subset explicitly; do not turn known
asymmetric-only support into unknown unrestricted support.

Keep our tolerant local-name XML parsing. Upstream implementations are useful
references, but their parsing assumptions and workarounds should not be copied
without independent tests.

### 3 End-of-scan handling can prematurely stop some feeders

Our `ScannerClient.iter_next_document()` ends unconditionally on HTTP 404 or
410. It retries 500/503 using job state. sane-airscan documents two relevant
exceptions: a delay between Brother feeder page requests, and temporary 404/410
responses from Xerox B205/B215 devices. It also has a status-before-download
path for certain Ricoh devices.
[sane-airscan eSCL implementation](https://github.com/alexpevzner/sane-airscan/blob/master/airscan-escl.c).

This creates a plausible incomplete-document risk: valid earlier PDF pages can
be assembled after we interpret a temporary page response as completion. The
risk is grounded in our control flow and upstream device evidence; it has not
been reproduced on those physical printers in this project.

Add narrowly selected, bounded recovery policies with job-status evidence,
cancellation and timeout checks. Fixtures must cover both transient failure and
true end-of-document, so recovery cannot become an endless feeder loop. Test
several pages with slow feeds; a valid PDF header and EOF alone do not prove that
all sheets were acquired.

### 4 Printer settings depend on the document and loaded media

Our print probe requests a small global attribute set. It does not specify the
job's document format. IPP supports format-dependent capability responses;
copy/page-range support can differ between document formats. If the query omits
the format, a printer whose default is auto-sensing can return a union of its
formats' capabilities.
[PWG capability guidance](https://www.pwg.org/ipp/ippguide.html#printer-capability-attributes),
[RFC 8011 section 4.2.5.1](https://www.rfc-editor.org/rfc/rfc8011.html#section-4.2.5.1).

Also, `media-default` is a configured default, not proof of what is loaded.
Our fresh default-paper request is a useful HP workaround, but cannot replace
`media-ready`/`media-col-ready` when reporting available paper or validating a
selected tray. CUPS keeps supported, default and ready values separate, and
reports relationships between settings.
[CUPS destination information](https://openprinting.github.io/cups/doc/cupspm.html#detailed-destination-information),
[PWG job attributes](https://www.pwg.org/ipp/ippguide.html#common-job-attributes).

Recommended model: cache stable identity/capabilities separately from format-
specific options and more changeable ready media. Request attributes in bounded
sets, preserving the existing concern about firmware that dislikes large probes.
Add defaults, readiness and constraints only where advertised. Absence must not
mean every tray is empty or every option is unsupported.

For settings selected by the user, introduce Validate-Job before the document
upload. It checks attributes without creating a job or sending document data.
It cannot validate the PDF's contents or guarantee a later physical outcome.
Handle devices that omit or mishandle the operation through an explicit tested
policy rather than making it a new unconditional compatibility barrier.
[RFC 8011 section 4.2.3](https://www.rfc-editor.org/rfc/rfc8011.html#section-4.2.3).

### 5 The IPP parser loses information needed for accurate settings

`ipp_print/printer.py` currently flattens attribute groups into one dictionary.
It decodes integers, enums, booleans and integer ranges, but treats other value
syntax as text. That is insufficient for nested `media-col` collections,
resolution values and faithful preservation of unsupported attributes.

The submission path accepts IPP 0x0001 and 0x0002 like ordinary success. The
standard gives these statuses specific meanings: ignored/substituted settings
and conflicting settings. Although our explicit settings request fidelity,
we should retain and surface what the printer actually returned. An accepted
job still needs tracking; reporting a warning must not prompt automatic reprint.
[RFC status definitions](https://www.rfc-editor.org/rfc/rfc8011.html#appendix-B.1.2.2).

Before adding paper/tray/quality controls, introduce a bounded typed response
representation that preserves groups and collections, or evaluate a maintained
codec against the existing async/dependency constraints. JIPP is a reference
for this separation, not a recommendation to add a Java runtime to HA.
Keep the public capability API small; raw protocol structures stay internal.

Our request version is also hard-coded to IPP 2.0. A scoped compatibility probe
can try a supported older version after an explicit version-not-supported
response, and remember it for that endpoint. Never replay Print-Job after a
transport timeout to discover which version might work.
[RFC version behavior](https://www.rfc-editor.org/rfc/rfc8011.html#section-4.1.8).

### 6 Paper size and alignment affect compatibility and usability

The scanner uses the source's maximum region, with fixed zero offsets. On our
HP this has already produced Legal-sized results when feeding Letter sheets.
It is not the same as automatic page-size detection. NAPS2 exposes page size
and horizontal alignment, and sane-airscan models minimum/maximum dimensions
and image positioning.
[NAPS2 basic settings](https://www.naps2.com/doc/profile-settings#basic-settings),
[sane-airscan geometry handling](https://github.com/alexpevzner/sane-airscan/blob/master/airscan-escl.c).

Add Letter/A4/custom-region support against the selected source's bounds and
alignment. Offer automatic detection only when an implemented device capability
supports it; otherwise distinguish full scan area from a selected page size.
Do not rely on all firmware safely clamping oversized requests. Freeze region,
alignment and effective resolution across both manual-duplex passes.

### 7 Discovery and quirks should be deliberate compatibility features

Preserve DNS-SD resource paths and advertised ports, normalize TXT keys and
UUIDs consistently, reconcile HTTP/HTTPS advertisements by device identity,
and test IPv4/IPv6 and changed addresses. NAPS2 retains advertised service
addresses and resource paths in its discovery model. Our scanner lowercases TXT
keys; print discovery currently reads `UUID` and other keys directly. The scan
client accepts a base path internally and from discovery, but manual setup does
not expose it.
[NAPS2 discovery](https://github.com/cyanfish/naps2/blob/master/NAPS2.Escl/Client/EsclServiceLocator.cs).

Keep connection repair in installation settings, not the ordinary job panel.
An advanced scanner path override and consistent identity normalization would
help proxy/bridge and manually configured installations.

Treat print and scan as separate services even when they belong to one physical
device. Duplex printing does not establish automatic duplex scanning, and a
CUPS queue's identity need not equal the scanner's identity. Associate them only
with trustworthy identity evidence or an explicit user choice; retain separate
capabilities, endpoints and job state.

Use a small documented device-quirk registry for proven exceptions: matcher,
affected firmware when known, behavior, evidence link and regression fixture.
Show applied quirks in diagnostics; allow a deliberate advanced override when
necessary. Do not apply every vendor workaround to every device. scanservjs
allows per-device capability/default overrides, while ipp-usb maintains explicit
quirk files.
[scanservjs configuration](https://github.com/sbs20/scanservjs/blob/master/docs/10-configuration.md),
[ipp-usb](https://github.com/OpenPrinting/ipp-usb).

For incorrect scanner Location hostnames, consider an evidence-backed path-only
repair onto the already configured origin. Preserve our origin/path/authentication
boundaries; simply following arbitrary returned hosts would be the wrong fix.
Keep TLS exceptions explicit per device. Preserve current protections around
other clients' scanner jobs and ambiguous print submissions.

## Common settings design

Use one shared presentation contract over separate scan/print protocol adapters.
The capability layer should provide:

- A value's support state: supported, unsupported or unknown, with freshness.
- Device defaults, integration/card defaults and the user's current intent as
  separate concepts.
- Valid combinations and dependencies, not just dropdown choices.
- Requested versus effective settings for the submitted job, including any
  resolution adjustment or device-reported substitution.
- Separate device transfer formats and the output formats our integration can
  produce, with a reason when conversion is unavailable.

Extend schema 1 additively where possible. If an existing field changes shape
or meaning, introduce a new schema contract and retain compatibility with old
cards. The current source-level summary should not become the authority for
validating combinations once complete setting profiles exist.

Do not make incomplete capability reports a blanket rejection of a previously
working device. Preserve a conservative default path when data is unknown,
explain uncertainty for optional settings, and use a documented override only
where needed. Known unsupported combinations should fail before submission;
unknown support must not be advertised as confirmed support.

Keep the main cards compact. Retain Scan/Download PDF, Two-sided and explicit
file staging/Print. A shared Options panel can then expose:

| Scan | Print |
| --- | --- |
| Auto, feeder or glass | Printer selection when multiple targets exist |
| Color or grayscale; black-and-white only after backend support | Copies |
| DPI supported by the current source/mode/profile | One-sided, long-edge or short-edge binding |
| Page size once region handling exists | Paper/tray and color/quality only after their backend paths exist |

Changing source, duplex or file type should revalidate dependent selections
before submission. Explain a changed value in plain language, such as "600 DPI
is unavailable for two-sided scans; using 300 DPI." Never silently change
simplex/duplex, copy count or target printer. Offer Device default only as an
explicit choice whose behavior is distinguishable from the card's own default.
Preserve the planned one-copy/one-sided defaults when new print controls ship;
existing omitted-field API requests keep their current semantics.

Protocol versions, transfer formats, vendor timing workarounds and TLS details
belong in diagnostics or advanced installation settings, not routine job UI.

## Broader hardware through optional bridges

| Route | Coverage opportunity | Boundary |
| --- | --- | --- |
| Direct IPP/eSCL | Compatible network printers/scanners with the least setup | Improve negotiation and targeted quirks first |
| Configured CUPS or Printer Application endpoint | Devices needing document conversion or a printer driver | Optional external service with its own queue, credentials and capabilities; verify its advertised formats |
| AirSane backed by SANE | SANE-supported legacy/USB scanners; potentially WSD via a suitable SANE backend | Needs a host running the bridge; test its paths and source/format behavior before claiming support |
| ipp-usb endpoint | USB hardware implementing IPP-over-USB, including exposed eSCL services | Does not support every USB printer/scanner; the endpoint must be reachable from HA |

A CUPS bridge is preferable to embedding a whole print rendering stack into the
HACS integration as the first broad-format expansion. Keep it optional so
working direct devices stay simple. CUPS documentation now deprecates the old
filter/driver interfaces, so avoid building a new HA dependency around direct
PPD/cupsfilter orchestration; use the stable network protocol boundary and
validate the selected bridge deployment.
[CUPS filtering and deprecation notes](https://openprinting.github.io/cups/doc/man-cupsfilter.html).

AirSane and ipp-usb already describe the relevant bridge roles above. This is
an architectural opportunity, not a claim that these bridges have been tested
with our integrations. Multiple exposed scanners also need explicit scan-target
routing; the scan integration is currently single-entry.

## Recommended order and acceptance gates

| Order | Work | Gate |
| --- | --- | --- |
| 1 Before Phase 3 | Correct octet-stream support claims; preserve/report IPP substitution warnings; reproduce scanner completion exceptions and profile gaps in fixtures | No advertised false format support, no silent setting substitution, no premature success in the recorded feeder scenarios; no duplicate job submission |
| 2 Capability foundation | Complete scanner profiles/references/ranges/formats; typed IPP groups/collections; format-specific queries and bounded validation | Advertised combinations are validated; missing data stays unknown with an explicit fallback policy; schema 1 clients continue to function |
| 3 Planned options panel | Shared Options UI, dependent choices, effective settings, page size when implemented | Settings agree with backend behavior, freeze during jobs, and remain usable on the phone |
| 4 Coverage expansion | Image-to-PDF scan path; optional CUPS/AirSane/ipp-usb recipes and tests | Native-PDF and image-only scanner fixtures; a raster-only print path through a verified bridge; consistent page order/dimensions |
| Continuous | Sanitized device fixtures, diagnostics and compatibility matrix | Each advertised device/mode claim has evidence and regressions reproduce reported failures |

Do not combine these into a protocol rewrite plus a UI redesign. The first
batch can fix misleading support claims and add regression evidence while
retaining the installed card behavior. Image conversion, bridge deployment,
new authentication schemes and WSD support are separate decisions.

## Testing and community support

Add a capability/response corpus with source, model, firmware when available,
transport and expected normalized values. Start with our verified HP, then
seek Brother, Canon, Epson, Xerox/Ricoh, an image-only eSCL device, an IPP raster-
only printer, and software endpoints. Brand variety is useful, but capability
and failure-mode variety is the real coverage target.

Run three distinct levels:

1. Parser/selection fixtures: references, ranges, incompatible profile
   combinations, collections, unknown attributes, octet-stream-only capability
   reports, format-dependent copies, malformed/bounded responses and versions.
2. Protocol simulations and reference tools: transient 404/410/503, slow pages,
   true feeder exhaustion, substitutions/conflicts, unsupported validation,
   paper changes, disconnects after submission, and cancellation. Use ipptool
   for controlled protocol checks and ippsample as a development counterpart.
3. Physical outcomes: correct page count/order/orientation, paper size, copies,
   feeder behavior, long-edge/short-edge printing, and download on the phone.
   A completed protocol job alone does not establish every physical property.

Publish matrix labels such as physical test passed, fixture tested, community
reported and known issue, with the particular modes covered. Do not label a
whole brand supported because one device passes.

Make a bounded, redacted support bundle containing capability shape, effective
settings, applied quirks, protocol status/reason and timing. Exclude credentials,
document contents and identifying paths/names by default. Existing print
`diagnostics.py` redacts passwords but otherwise retains entry/URI/identity/job
metadata; it should be reviewed before encouraging public uploads. Scanner
redaction is broader, but a shared support-bundle policy is still needed.

## Evidence limits

The two scanner parser probes used constructed capability documents and did not
operate hardware. No new physical scan or print was performed for this research.
Upstream source/docs were read on 2026-10-08 from their default branches; the
recommendations distinguish source behavior from our own proposed architecture.
The public Mopria specification landing page was inspected, but its download
requires license acceptance and a CAPTCHA; the specification text was not
accessed. Detailed eSCL findings here come from public client implementations,
not a claimed full normative conformance review.

This research changes documentation only. Baseline verification on 2026-10-08:
scan 182 Python and 42 card tests; print 180 Python and 29 card tests; Ruff in
both repositories and print compileall pass. These existing checks do not yet
cover the newly identified compatibility gaps.
