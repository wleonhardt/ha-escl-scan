# Phase 4 HP live tests — 2026-10-09

Status: in progress; print passed, awaiting user confirmation that the two fronts
are loaded before scanning. Starting installed pair: scan 0.10.0 / print 0.9.0.
HP Color LaserJet MFP M283fdw, HA 2026.9.4. The user requested physical tests and
confirmed Letter paper and a clear output tray.

## Print job 371

Submitted once through the real Print card: the existing four-page numbered
compatibility PDF, renamed `phase4-hp-state-test.pdf`, 6496 bytes. One copy, Letter,
automatic tray, color, normal quality, long-edge duplex: two physical sheets.
The PDF's four pages were visually inspected before reuse.

A separate dashboard tab recorded real pushed states and UI changes without
submitting a job. Backend state sequence (UTC):

| Time | State | Completed / reported total | Unit |
| --- | --- | --- | --- |
| 12:59:30.531 | pending | unknown | unknown |
| 12:59:30.774 | processing | 0 / 0 | impressions |
| 12:59:48.958 | processing | 2 / 2 | impressions |
| 12:59:57.899 | completed | 4 / 4 | impressions |
| 13:00:06.905 | idle | cleared | — |

The observer card adopted job 371 without local submission, displayed progress,
cleared the filename on completion and returned to Choose file. The submitting
tab was refreshed after acceptance; the inspected refreshed card showed the
same completion and no staged filename. We did not capture an active-state
snapshot immediately after refresh, so this alone does not prove recovery while
printing. Scanner reload during the manual-back pause is the next recovery test.
Both native connectivity sensors remained connected during the print.

Physical sheet count/orientation awaits the user's confirmation. The test sheet
will then be reused for a two-pass scan: fronts 1F,2F; backs 2B,1B with Last sheet
first, validating final PDF order 1F,1B,2F,2B.

## Finding and fix: provisional progress totals

The HP increased `job-impressions` while processing (0 → 2 → 4), making the old
card say `Printing page 2/2…` before the job was finished. Print 0.9.1 changes live
progress to completed counts (`Printing… 2 pages printed`) and retains explicit
sheet wording where that is the only counter. Only terminal state confirms
completion; backend counters remain unchanged for automations.

The captured HP sequence is now a regression test. Print has 217 Python + 54 card
tests passing, plus Ruff, compileall and shared-core parity. The small card update
was backed up, installed and the print entry reloaded successfully (200, no HA
restart). Backup: `/config/.document-card-backups/before-hp-progress-v091-20261009.tar.gz`.
Commit: `84b4eb070a4a9513ebd5b17eb6889b09d0e2e39d`. All six hosted checks and the v0.9.1 release workflow pass; the release is published.
The installed card resource is `/ipp_print/card-90abe4fae503.js`.

## Remaining physical checks

- [ ] Confirm the printed sheets, load fronts, scan them and reach manual-back pause.
- [ ] Refresh the submitting dashboard during that pause; compare same scan ID/count.
- [ ] Briefly disconnect only that browser tab from HA and restore it; same scan recovers.
- [ ] Scan reversed backs, download PDF and inspect page count/order/orientation.
- [ ] With no job active, user switches HP off/on to validate real unreachable/recovery.
- [ ] Record completion and leave both integrations idle with no pending test jobs.

No additional print should be sent unless needed and explained. Do not restart
HA or reload the scan integration while the manual duplex scan is waiting.
