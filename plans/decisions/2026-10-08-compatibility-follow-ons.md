# Compatibility follow-ons and evidence gates

Recorded 2026-10-08. These are separate future proposals, not implicit additions
to the direct eSCL/IPP compatibility release.

| Proposal | Evidence required before implementation |
|---|---|
| Native WSD scan transport | Representative WSD-only device, maintained implementation/library assessment, HA dependency and cancellation/retry tests |
| Authentication beyond HTTP Basic | Actual server challenge/capture and supported HA credential flow; no guessing or automatic security downgrade |
| Multiple scanner entries | Entity-scoped services/views, independent storage/lifecycle/locks, migration and paired-card routing design |
| Embedded print rendering | Concrete unsupported-file demand, converter sandbox/resource/dependency review; compare an external configured queue first |
| Xerox malformed IPv6 Location repair | A scoped response fixture and exact repair rules that preserve configured origin and ScanJobs path checks; ordinary foreign hosts remain rejected |
| Additional vendor workarounds | Model/firmware evidence, failure reproduction, narrow matcher and a bounded regression test |

Current direct clients, optional bridge recipes and source-attributed recovery
regressions improve coverage without claiming these untested transports or devices.
