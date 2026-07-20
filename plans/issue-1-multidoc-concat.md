# Issue #1 — multi-document ADF concatenation

Status: DONE (v0.3.0). Implemented per the plan below: per-document scratch
writers in `_stream_documents`, validate+merge in `_assemble_result`,
`_merge_pdfs` via pypdf (lazy import, executor), single-doc keeps the rename
fast path. `pypdf>=4.0` added to manifest requirements. Tests: merge,
chunked-merge, truncated-part-dropped (tests/test_coordinator.py).
Remaining: confirm against the real printer whether it is bundle- or
per-page-mode (live test).

## Problem
eSCL `NextDocument` is pulled in a loop until 404. Two vendor behaviours:
- **Bundle mode** — whole ADF batch arrives as ONE PDF on the first
  `NextDocument`. (Common: HP/Canon/Epson.)
- **Per-page mode** — each `NextDocument` returns one page as its own PDF.

Today `coordinator._drive_scan` saves only the **first** document and drains
(discards) the rest (`doc_index == 0` guard). On per-page scanners the user
gets page 1 only.

## Fix
Stream every document to its own scratch `.partN` file (keeps the P1
OOM-safety — never buffer a whole PDF in RAM), then after the loop:
- 0 valid PDFs → `failed` (as today).
- 1 valid PDF → rename into place (fast path; the bundle-mode case, incl. the
  huge-single-PDF case, never touches the merge path).
- >1 valid PDFs → **merge with pypdf** into the final file (in an executor —
  pypdf is sync/CPU), set `pages_done` to the merged page count.

"Valid" = starts with `%PDF-` and has `%%EOF` in the tail (per-part reuse of
the existing check). A truncated final part is dropped with a warning; the
rest still merge.

Non-PDF (image-mode) multi-doc is NOT concatenated — logged, first part kept.
Converting JPEG→PDF would need Pillow/img2pdf; out of scope.

## Dependency decision
Add `"requirements": ["pypdf>=4.0"]` to `manifest.json`. pypdf is pure-Python
(no native/qpdf dep), the de-facto HA choice for PDF work, installed into HA's
venv on setup. Rejected: pikepdf (needs qpdf native lib), hand-rolled merge
(fragile).

## Touch points
- `manifest.json` — requirements.
- `coordinator.py` — per-document scratch writers; post-loop merge branch;
  `_merge_pdfs(parts, dest) -> int` helper (executor); cleanup all parts.
- `scanner.py` — no change (`iter_next_document` already per-document).
- tests — multi-doc merge yields a valid N-page PDF; truncated-tail part
  dropped; single-doc fast path unchanged; non-PDF multi-doc keeps first.

## Sequencing
Test v0.2.0 on the real printer FIRST — its logs reveal whether 10.11.40.190
is bundle- or per-page-mode ("scanner returned document #2" ⇒ per-page),
which tells us if this issue even bites this device and gives a real fixture.
