# Phase 4 HP live tests — 2026-10-09

Status: in progress; physical print and two-pass scan passed, including
reload/reconnect and downloaded PDF inspection. HP shutdown detection passed;
automatic recovery after power-on remains. Starting installed pair: scan 0.10.0 / print 0.9.0.
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
printing. Scanner reload during the manual-back pause provides recovery evidence below.
Both native connectivity sensors remained connected during the print.

The user confirmed both printed sheets were correct and loaded fronts 1F,2F.
The same sheets were reused for a two-pass scan, with reversed backs 2B,1B
and Last sheet first; the final PDF order is 1F,1B,2F,2B.

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

- [x] Confirm the printed sheets, load fronts, scan them and reach manual-back pause.
- [x] Refresh the submitting dashboard during that pause; compare same scan ID/count.
- [x] Briefly disconnect only that browser tab from HA and restore it; same scan recovers.
- [x] Scan reversed backs, download PDF and inspect page count/order/orientation.
- [ ] With no job active, user switches HP off/on to validate real unreachable/recovery.
- [ ] Record completion and leave both integrations idle with no pending test jobs.

No additional print should be sent unless needed and explained. Do not restart
HA or reload the scan integration while the manual duplex scan is waiting.

## Scan recovery evidence

Real scan `a49d87b88844` started at 13:06:09 UTC, Feeder/Letter/color/300 DPI,
manual duplex. It reached awaiting-back-sides with 2 front pages. Both tabs
agreed on the scan ID, phase and count. Refreshing tab 65 restored the same
scan and enabled Scan back sides without a new start request.

Next, tab 65 alone was placed offline and its actual HA WebSocket closed.
The dashboard reported disconnected, kept scan `a49d87b88844`, showed reconnection
guidance and disabled both Scan back sides and Cancel. Networking was restored
in a finally block. The real HA connection reconnected, preserved the same scan
and counts, hid the connection warning and re-enabled both controls. Tab 67
remained online throughout. HA and the scanner integration were not restarted.

The unfinished `/api/escl_scan/file/a49d87b88844` correctly returns 409 while
waiting for backs. No intermediate/front-only PDF was exposed.

## Completed two-pass scan and download

The user confirmed backs were ready; Last sheet first was selected. Resumed the
same scan exactly once at 13:12:35 UTC with `reverse_back_order=true`. Real progress
was 2 → 3 → 4, then completed at 13:13:17.566 UTC, and idle at 13:13:26.211 UTC.
No job ID changed and no duplicate scan was created by reload or reconnect.

The real Download PDF button saved 2,084,147 bytes and returned to Scan. Inspected
all four rendered pages: **1F,1B,2F,2B**, all upright, correct front/back pairing,
Letter (612 × 792 pt), RGB images at 2550 × 3300 pixels (300 DPI). Paper show-through
is visible but there is no page-order, orientation or clipping issue.

Downloaded file:
`/Users/william/Downloads/scan-20261009-090610-feeder-a49d87b88844.pdf`.
Its SHA-256 matches both the private retained PDF and `/media/escl_scan` copy:
`fc93e19f6bc82a0b20c8319d966efd4503c9fccc5789497c40961d1c2a03bb3d`.
Both integration jobs are idle; no scan integration reload/restart was needed.

## Physical shutdown and automatic recovery

The user shut down the HP while both jobs were idle. The real IPP connection
entity changed to off at 13:33:06.359 UTC; eSCL followed at 13:33:07.913 UTC.
Both reported unreachable, while Home Assistant stayed connected and the two
job sensors remained idle. Each card showed "Cannot reach this device. Check
its power and connection." The native tiles showed Scanner Disconnected and
Printer Disconnected. The warnings were readable without overflow at 390 × 844;
a freshly opened dashboard also loaded both cards with the disconnected state.

While the printer remained off, natural retries at about 13:34:09 and 13:36:12
UTC still reported unreachable. The advertised retry intervals increased from
60 to 120 to 240 seconds; the next check is scheduled for 13:40:12 UTC. No
forced refresh, integration reload, restart or device job was used to advance
these checks. Power-on recovery is pending the user's readiness confirmation.
