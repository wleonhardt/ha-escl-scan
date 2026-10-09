# Compatibility foundation

Accepted during the user-authorized compatibility rollout, 2026-10-08.

- Preserve complete eSCL setting profiles internally. Publish additive bounded
  setting combinations alongside schema-1 source summaries. Client-supported
  square resolutions remain 50–1200 DPI; asymmetric-only support is a known
  incompatibility, not unknown. Named references are bounded and cycle-checked.
- Select a native PDF profile first; otherwise acquire an advertised JPEG/PNG
  profile and convert to PDF. Unknown format metadata retains legacy PDF.
  Send standard DocumentFormat and the extension only when advertised or unknown.
- Use Pillow for image decoding/PDF encoding in executor work, with explicit
  encoded-byte and pixel limits, single-image checks and requested-DPI physical
  page sizing. Keep pypdf for PDF validation/merging. This is the one added scan
  runtime dependency; no print rendering stack or card build is introduced.
- Retain a bounded local IPP codec, adding typed groups/collections and preserving
  unknown values. The current public parse_response helper remains compatible.
- IPP auto-sensing is distinct from explicit file-format support. Never promote
  octet-stream-only advertising to confirmed PDF/JPEG/PNG support.
- Probe the actual document format and validate explicit options before Print-Job.
  Unsupported Validate-Job may fall back to existing attribute-fidelity behavior;
  rejected settings or uncertain preflight transport do not upload a document.
  Version fallback occurs only after explicit rejection of a read-only probe.
- Firmware quirks require a named matcher, public evidence and regression test.
  Preserve default HP behavior and strict scanner origins/paths. Unproven broad
  host-rewriting or security downgrades are not enabled.
- Default paper remains the explicit HP sides workaround; ready paper is separate
  metadata. Existing omitted-field submissions retain device-default semantics.

Implementation evidence: routine HP media-col-database requests returned 938,053
bytes and could not complete inside the per-read budget. Query media/source
keywords and the small default collection instead; retain full collection parsing
for received data and targeted future diagnostics. Validate tray/paper together.

Single-scanner enforcement moves into the flow so discovery can reconcile saved
or live UUID evidence before rejecting a second scanner. This is not multi-scanner
support. Existing unique/entity IDs remain unchanged. Different print queue paths
are distinct even if a server repeats its UUID.
