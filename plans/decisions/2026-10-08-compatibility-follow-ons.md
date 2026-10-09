# Compatibility follow-ons and evidence gates

Recorded 2026-10-08. These are separate future proposals, not implicit additions
to the direct eSCL/IPP compatibility release.

| Proposal | Evidence required before implementation |
|---|---|
| Native WSD scan transport | Representative WSD-only device, maintained implementation/library assessment, HA dependency and cancellation/retry tests |
| Authentication beyond HTTP Basic | Actual server challenge/capture and supported HA credential flow; no guessing or automatic security downgrade |
| Multiple scanner entries — deferred by user, 2026-10-09 | Concrete second-scanner use case and tester, then entity-scoped services/views, independent storage/lifecycle/locks, migration and paired-card routing design |
| Embedded print rendering | Concrete unsupported-file demand, converter sandbox/resource/dependency review; compare an external configured queue first |
| Xerox malformed IPv6 Location repair | A scoped response fixture and exact repair rules that preserve configured origin and ScanJobs path checks; ordinary foreign hosts remain rejected |
| Additional vendor workarounds | Model/firmware evidence, failure reproduction, narrow matcher and a bounded regression test |

Current direct clients, optional bridge recipes and source-attributed recovery
regressions improve coverage without claiming these untested transports or devices.

## Scope preference and recommended next work — 2026-10-09

The user confirmed the main dashboard looks good and explicitly chose to keep
multiple-scanner support in the backlog to avoid unnecessary complexity.
Compatibility with other device models can progress independently.

Recommended next work, pending implementation selection:

1. Audit existing diagnostic downloads for the minimum useful failure evidence:
   operation stage, bounded error category/status, capability freshness and
   whether a job could have been accepted. Start with the unresolved JPEG
   settings lookup recorded in the Print project's format-rejection plan.
   Add only demonstrably missing fields; preserve redaction and bounded storage.
   Do not infer a cause from a successful retry or change submission retries.
2. Use existing device report forms to obtain model/firmware-specific evidence.
   Review the existing Epson report's available evidence first. Add redacted
   protocol captures as test fixtures, keeping actual captures distinct from
   synthetic tests and successful parsing distinct from physical output.
3. Fix reproduced faults in existing discovery, capability selection and job
   handling. Test timeout, authentication/TLS, incomplete capabilities and device
   sleep/recovery at the affected boundary. Avoid another broad test matrix that
   repeats existing coverage without a concrete gap.

Keep the existing cards, setup flow and diagnostic-download action. Prefer tests,
documentation and small corrections with no new runtime dependencies or tuning
options. Other-vendor, automatic-duplex and bridge acceptance still requires
appropriate devices/reporters; no outreach is authorized by this recommendation.
