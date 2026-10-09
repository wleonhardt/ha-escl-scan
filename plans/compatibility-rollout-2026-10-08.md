# IPP and eSCL compatibility rollout

Status: accepted for implementation on 2026-10-08. Canonical plan for
ha-escl-scan and ha-ipp-print. Starting commits: scan cccdc47, print 0009f74.
Evidence: [cross-project research](ipp-escl-compatibility-research-2026-10-08.md).

Improve direct-device reliability, then expose settings the backend can honor.
Keep the visible Two-sided switch, independent HACS installations and plain-JS
cards. This extends the [shared card rollout](shared-card-rollout-2026-10-08.md):
compatibility stages A/B precede its Phase 3; stage C implements that phase.
Native Tile/Mushroom hosting and persistent history retain their existing gates.

## Invariants

- Preserve working default jobs when capability data is incomplete; distinguish
  unknown from known unsupported. Validate user selections on the server.
- Never replay an accepted or ambiguous print submission, or restart a consumed
  scan batch automatically. Never delete another client's scanner job.
- Keep print and scan capabilities independent, including duplex capability.
- Preserve scanner URL/origin/auth boundaries, bounded response parsing, async
  I/O, cancellation and private manual-duplex intermediate files.
- Extend schema 1 additively; existing cards, services and omitted-field requests
  remain compatible. New runtime dependencies require a recorded decision.
- Stable capabilities are cached; changing ready media and per-format settings
  have explicit freshness. Avoid device requests on every UI render.

## A Correctness and regression evidence

- [ ] A1 Distinguish explicit IPP format support, auto-sensing and unknown data;
  stop advertising octet-stream as every upload format.
- [ ] A2 Preserve successful-with-warning IPP statuses and unsupported settings;
  report accepted substitutions without inviting duplicate printing.
- [ ] A3 Add scanner fixtures for disjoint profiles, named references, ranges,
  asymmetric-only resolutions and missing metadata.
- [ ] A4 Add narrowly matched, bounded Brother/Xerox/Ricoh scan recovery with
  cancellation, true exhaustion and timeout tests; preserve normal HP behavior.
- [ ] A5 Add safe shared diagnostic redaction and an evidence-labelled device
  matrix; no credentials, documents, identifying paths/names in support data.

Gate: regressions demonstrate the previous errors and prevent false claims,
invalid known combinations, silent substitutions and premature scan success.

## B Capability and protocol foundation

- [ ] B1 Retain scanner profiles, bounded named references, formats, square
  discrete/range resolution support and per-source geometry/alignment.
- [ ] B2 Select source/color/duplex/format/DPI together; report requested and
  effective settings. Freeze the result across both manual scan passes.
- [ ] B3 Negotiate standard/extended eSCL format fields and separate acquisition
  format from PDF output. Retain a tested legacy fallback for unknown formats.
- [ ] B4 Preserve typed IPP groups, collections, resolutions and unknown values;
  bound nested parsing. Retain simple attribute access for current callers.
- [ ] B5 Query document-format-specific capabilities; distinguish media supported,
  default and ready; check explicit settings with Validate-Job and a documented
  fallback when the operation is unsupported.
- [ ] B6 Negotiate older IPP versions only on explicit version rejection during
  a read/preflight; never use a print retry to discover protocol support.
- [ ] B7 Normalize discovery TXT keys/UUIDs, preserve paths/ports and support an
  advanced manual scanner path. Cover IPv6 and changed addresses. Reconcile
  identities without merging unrelated print queues or changing existing IDs.
- [ ] B8 Record device quirks with matchers, evidence and tests; expose applied
  policies in diagnostics. Only implement Location repair with a scoped fixture
  that preserves origin/path restrictions.

Gate: bounded capability models produce honest, compatible schema-1 summaries
and full validated combinations; unknown data uses an explicit fallback policy.

## C Common settings and paper handling

- [ ] C1 Scan Options: Auto/Feeder/Glass, Color/Grayscale and dependent DPI choices.
- [ ] C2 Scan region: full area, Letter/A4 and validated custom dimensions with
  source bounds/alignment. Do not label full area as automatic size detection.
- [ ] C3 Print Options: explicit one-copy/one-sided defaults, copies, binding and
  target selection when needed; add paper/tray/color/quality only with complete
  backend validation and advertised support.
- [ ] C4 Shared compact panel/editor naming, focus handling, options-only duplex
  variant, explanations for adjusted values and frozen settings during jobs.
- [ ] C5 Revalidate dependent choices after source/duplex/file/target changes;
  preserve staging, download, resume, back-order and cancellation behavior.

Gate: controls describe what is submitted, unavailable options have reasons,
old backends remain usable, mobile/narrow layouts and keyboard behavior pass.

## D Format and bridge coverage

- [ ] D1 Record converter decision; support advertised JPEG/PNG scan acquisition
  with bounded image decoding/PDF assembly in the executor. Prefer native PDF.
- [ ] D2 Test native/image-only/mixed-profile scanners, malformed and oversized
  images, cancellation, duplex page order and physical page dimensions.
- [ ] D3 Add optional CUPS/Printer Application, AirSane and ipp-usb setup recipes
  with explicit endpoint, conversion, authentication and device limitations.
- [ ] D4 Exercise reachable software bridges/reference endpoints; record which
  are simulated, software-tested or physically tested. No unverified supported
  hardware claims and no mandatory bridge installation.
- [ ] D5 Record separate follow-on decisions for native WSD, new authentication
  schemes, multi-scanner routing and embedded print rendering if evidence later
  justifies them; none is required for the direct-client compatibility release.

## E Verification and delivery

- [ ] E1 Update README/examples, capability contract, diagnostics and change logs;
  bump user-facing versions and commit meaningful stages in each repository.
- [ ] E2 Run both Python/card suites, Ruff, print compileall and hosted validation.
- [ ] E3 Verify paired layouts using BrowserOS Neo; read-only HP capability probe
  and controlled physical jobs only when the relevant paper/device is ready.
- [ ] E4 Preserve outstanding four-sheet print confirmation and automatic-duplex
  hardware test as physical gates; track external-device limitations explicitly.
- [ ] E5 Push completed changes; release/install only a validated stage, with
  rollback and installed versions recorded separately from repository versions.

## Execution record

- 2026-10-08 — Plan accepted and implementation started. Baseline: scan 182
  Python/42 card tests; print 180 Python/29 card tests. No newly tested hardware.
