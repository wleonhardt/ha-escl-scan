# IPP and eSCL compatibility rollout

Status: stages A–E complete. Software released/installed and available-HP
physical acceptance passed; final UI/localization audit shipped in Phase 3.
Other hardware/bridge acceptance remains external. Canonical plan for
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

- [x] A1 Distinguish explicit IPP format support, auto-sensing and unknown data;
  stop advertising octet-stream as every upload format.
- [x] A2 Preserve successful-with-warning IPP statuses and unsupported settings;
  report accepted substitutions without inviting duplicate printing.
- [x] A3 Add scanner fixtures for disjoint profiles, named references, ranges,
  asymmetric-only resolutions and missing metadata.
- [x] A4 Add narrowly matched, bounded Brother/Xerox/Ricoh scan recovery with
  cancellation, true exhaustion and timeout tests; preserve normal HP behavior.
- [x] A5 Add safe shared diagnostic redaction and an evidence-labelled device
  matrix; no credentials, documents, identifying paths/names in support data.

Gate: regressions demonstrate the previous errors and prevent false claims,
invalid known combinations, silent substitutions and premature scan success.

## B Capability and protocol foundation

- [x] B1 Retain scanner profiles, bounded named references, formats, square
  discrete/range resolution support and per-source geometry/alignment.
- [x] B2 Select source/color/duplex/format/DPI together; report requested and
  effective settings. Freeze the result across both manual scan passes.
- [x] B3 Negotiate standard/extended eSCL format fields and separate acquisition
  format from PDF output. Retain a tested legacy fallback for unknown formats.
- [x] B4 Preserve typed IPP groups, collections, resolutions and unknown values;
  bound nested parsing. Retain simple attribute access for current callers.
- [x] B5 Query document-format-specific capabilities; distinguish media supported,
  default and ready; check explicit settings with Validate-Job and a documented
  fallback when the operation is unsupported.
- [x] B6 Negotiate older IPP versions only on explicit version rejection during
  a read/preflight; never use a print retry to discover protocol support.
- [x] B7 Normalize discovery TXT keys/UUIDs, preserve paths/ports and support an
  advanced manual scanner path. Cover IPv6 and changed addresses. Reconcile
  identities without merging unrelated print queues or changing existing IDs.
- [x] B8 Record device quirks with matchers, evidence and tests; expose applied
  policies in diagnostics. Only implement Location repair with a scoped fixture
  that preserves origin/path restrictions.

Gate: bounded capability models produce honest, compatible schema-1 summaries
and full validated combinations; unknown data uses an explicit fallback policy.

## C Common settings and paper handling

- [x] C1 Scan Options: Auto/Feeder/Glass, Color/Grayscale and dependent DPI choices.
- [x] C2 Scan region: full area, Letter/A4 and validated custom dimensions with
  source bounds/alignment. Do not label full area as automatic size detection.
- [x] C3 Print Options: explicit one-copy/one-sided defaults, copies, binding and
  target selection when needed; add paper/tray/color/quality only with complete
  backend validation and advertised support.
- [x] C4 Shared compact panel/editor naming, focus handling, options-only duplex
  variant, explanations for adjusted values and frozen settings during jobs.
- [x] C5 Revalidate dependent choices after source/duplex/file/target changes;
  preserve staging, download, resume, back-order and cancellation behavior.

Gate: controls describe what is submitted, unavailable options have reasons,
old backends remain usable, mobile/narrow layouts and keyboard behavior pass.

## D Format and bridge coverage

- [x] D1 Record converter decision; support advertised JPEG/PNG scan acquisition
  with bounded image decoding/PDF assembly in the executor. Prefer native PDF.
- [x] D2 Test native/image-only/mixed-profile scanners, malformed and oversized
  images, cancellation, duplex page order and physical page dimensions.
- [x] D3 Add optional CUPS/Printer Application, AirSane and ipp-usb setup recipes
  with explicit endpoint, conversion, authentication and device limitations.
- [x] D4 Exercise reachable software bridges/reference endpoints; record which
  are simulated, software-tested or physically tested. No unverified supported
  hardware claims and no mandatory bridge installation.
- [x] D5 Record separate follow-on decisions for native WSD, new authentication
  schemes, multi-scanner routing and embedded print rendering if evidence later
  justifies them; none is required for the direct-client compatibility release.

## E Verification and delivery

- [x] E1 Update README/examples, capability contract, diagnostics and change logs;
  bump user-facing versions and commit meaningful stages in each repository.
- [x] E2 Run both Python/card suites, Ruff, print compileall and hosted validation.
- [x] E3 Verify paired layouts using BrowserOS Neo; read-only HP capability probe
  and controlled physical jobs only when the relevant paper/device is ready.
- [x] E4 Preserve outstanding four-sheet print confirmation and automatic-duplex
  hardware test as physical gates; track external-device limitations explicitly.
- [x] E5 Push completed changes; release/install only a validated stage, with
  rollback and installed versions recorded separately from repository versions.

## Execution record

- 2026-10-08 — Plan accepted and implementation started. Baseline: scan 182
  Python/42 card tests; print 180 Python/29 card tests. No newly tested hardware.

- Implementation complete: stages A–D include runtime changes, scoped tests,
  common Options dialogs, optional bridge recipes and separate follow-on decisions.
  B8 deliberately retains strict Location rejection pending a device fixture;
  D4 exercised the available CUPS endpoint, with AirSane/ipp-usb explicitly untested.
  D5 records proposals, not implementation of those additional transports.
- E3 covers the browser fixture and read-only HP checks. E4 is complete as tracking
  of external gates, not a claim that the physical tests passed. No live installation
  or new physical job occurred. [Validation record](compatibility-validation-2026-10-08.md).

- Hosted verification complete on implementation heads: scan `a0f2e46`, print
  `74878df`; all six jobs passed in each repository. 496 local tests pass
  (scan 209 Python/46 card; print 206 Python/35 card). Changes are on both main
  branches. E5's push is complete; tags/installation remain pending the physical
  acceptance stage. No release tags were created in this rollout.

- Live acceptance: installed scan 0.8.1 / print 0.7.0 with backup and verified
  hashes. Real card duplex printing and Letter/grayscale/300 DPI scan/download
  pass. Fixed scanner-side 409 guidance after an empty-feeder rejection; 502
  combined tests and hosted scan checks pass. E5 installation is complete;
  two-sheet manual duplex also passed with 1F,1B,2F,2B upright. Tags remain.
  See the current validation record for external hardware and remaining gates.

- Final HP acceptance: installed scan 0.8.2 / print 0.7.2. User confirmed the
  mobile Back fix and job 370's two correctly oriented short-edge duplex copies.
  All available-HP physical gates are closed. Phase 3's final editor label/help
  and string-centralization audit is tracked in the shared rollout; E5 release
  tags remain pending. Other hardware/bridge claims remain evidence-limited.

- Closeout, 2026-10-09: E5's release gate was completed by Phase 3's paired
  Scan 0.9.0 / Print 0.8.0 release and installation, followed by Phases 4–6.
  [Phase 3 validation](shared-card-phase-3-validation.md) records the final
  editor/localization audit and successful hosted/release workflows. Current
  installed pair is Scan 0.12.1 / Print 0.11.1; the
  [compatibility follow-up](compatibility-follow-up-2026-10-09.md) closes available
  HP discovery and card-mod checks and records the remaining external gates.
