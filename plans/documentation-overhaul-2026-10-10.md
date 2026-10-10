# Paired documentation overhaul — 2026-10-10

## Scope and structure

The user requested a complete documentation overhaul with short installation/use
READMEs and deeper reference pages, then confirmed that it covers both Scan and
Print. This work changes documentation and sample YAML only. Runtime versions
remain Scan 0.12.4 / Print 0.11.5; no live configuration or release is required.

Both landing READMEs are 70 lines, down from Scan's 604 and Print's 593. The
common path is requirements → HACS installation/device setup → native Tile card
→ first document → task-based guide links. Protocol calls, option reference,
recovery details and development instructions no longer interrupt that path.

Each repository has a documentation index and matching guides for installation,
dashboard, scanning/printing, automations, troubleshooting, compatibility and
HTTP API. CONTRIBUTING.md owns development/tests/translations; examples/README.md
explains where each YAML sample belongs. Maintainer plans remain historical
records rather than the primary user manual. Existing card-picker links to
`#adding-the-card-to-a-dashboard` continue to resolve.

## Reference patterns

Reviewed these rendered project READMEs on 2026-10-10:

- [Mushroom](https://github.com/piitaya/lovelace-mushroom): direct HACS entry,
  visual-editor usage steps and links to per-card documentation. Adopted the
  setup-first path and focused references, without copying its prose.
- [Spook](https://github.com/frenck/spook): concise project introduction with a
  clear route to separate documentation. Adopted that separation using ordinary
  repository Markdown; no documentation site generator or hosting is needed.
- [Adaptive Lighting](https://github.com/basnijholt/adaptive-lighting): explicit
  configuration/service tables and examples. Retained those useful reference
  forms in deeper pages rather than repeating a long all-in-one README.

Editorial rules: explain user actions before implementation, use numbered steps
for workflows and tables for fields/symptoms, keep one purpose per page, avoid
unsupported brand-wide claims, and link to canonical advanced explanations.
The old screenshot assets remain available, but the quick start no longer shows
an earlier card layout that omits current Options/activity controls.

## Corrections made while reorganizing

- Replaced the broken scan-to-print example (`escl_scan_job_completed` and
  `path`) with `escl_scan_completed`, a successful-result/copy condition, and
  `copied_to` from an explicitly configured readable folder. Explained why a
  consumer-owned folder can race printing and why private Scan storage is not
  automatically an allowed Print input.
- Distinguished durable completed scan/activity metadata from active jobs that
  cannot resume after restart. Removed the obsolete “later phase” statement.
- Included `failed` in Scan terminal events and corrected Print unreachable-job
  guidance to an unknown outcome rather than asserting abortion.
- Corrected the Print HTTP endpoint count/field list, including option fields,
  scoped cancellation and where `job_may_exist` is actually present.
- Documented actual card DPI inheritance, all start/action fields, scan units,
  service-vs-HTTP scan ID requirements, and zero retention meaning immediate
  expiry. Removed claims that every 200 setup response is sufficient.
- Replaced speculative truncated-PDF causes and “expected configuration error”
  guidance with symptom-based recovery and diagnostic collection.
- Made native Tile the first path; explained optional standalone/Mushroom hosts
  and kept resource registration automatic. Fixed the multiple-printer YAML
  example to use independent Vertical stacks and automatic sizing.
- Moved the sample scheduled print input to `/media/reports/today.pdf`, and
  explained that `www/` is web-served when discussing private local files.
- Kept verified HP evidence, qualified Epson reports and untested bridges/models
  distinct. Each compatibility page focuses on its own protocol, linking to the
  sister guide for the other bridge recipes.

## Validation

- Scan: 295 Python tests, 78 card tests, Ruff and compilation pass.
- Print: 292 Python tests, 65 card tests, Ruff and compilation pass.
- Both card suites ran after `npm ci`; dependency audits report no vulnerabilities.
- Checked 22 user documentation pages, 198 links, heading anchors, 30 YAML blocks/
  example files and five JSON examples. All local and paired-repository link
  targets resolve. Documentation action examples pass the real integration
  service schemas; no action was executed or document submitted.
- Runtime source, dependency manifests and card assets are unchanged. Scan's
  pre-existing untracked `output/` is untouched.
- Publication checks: verify the rendered GitHub READMEs and navigation, and
  require both hosted validation workflows to pass before final handoff.
