# Resolve scanner job URLs by path on the configured origin

Status: accepted and implemented in 0.12.8 (2026-11-14).

## Problem

HP MFPs build the `Location` of a new scan job from their own IP address and a
fixed port 80, whatever address and port the request used. Measured on the
HP M283fdw (`NPIC25FE4.local`, 10.11.30.190) on 2026-11-14 with a platen job
that was deleted straight away:

| Request to | `Location` returned |
|---|---|
| `http://NPIC25FE4.local:8080/eSCL/ScanJobs` | `http://10.11.30.190:80/eSCL/ScanJobs/…-1006-…` |
| `http://NPIC25FE4.local:80/eSCL/ScanJobs` | `http://10.11.30.190:80/eSCL/ScanJobs/…-1007-…` |

`ScannerClient._absolute()` requires the job URL to have exactly the configured
scheme, host and port. Any entry whose effective origin is not
`http://<scanner IP>:80` therefore fails with "scanner returned a job URL
outside its origin". That covers:

- every entry created through discovery, which stores the advertised port 8080
  (reproduced live, see [the 0.12.7 live test](../v0127-live-test-2026-11-14.md));
- manual entries that use a hostname such as `NPIC25FE4.local` instead of the
  IP address, even on port 80 (follows from the table; not yet run as a scan).

The failure happens after the scanner has accepted the job. The integration
never receives a usable job URL, so it cannot cancel the job, and the feeder
keeps pulling paper.

The same request on the same path but sent to our own origin works: deleting
`/eSCL/ScanJobs/…-1006-…` on port 8080 returned 200.

## Decision

Treat the scanner's `Location` (and the `JobUri` values in `ScannerStatus`) as
a job **path**, not as an address to contact. `_absolute()` will:

1. Parse the URI and keep only its path and query. Scheme, user info, host and
   port are ignored.
2. Join that path and query onto the configured origin.
3. Keep the existing check that the path is under `<base path>/ScanJobs/`.
   A path outside it is still rejected.
4. Log at debug level, once per client, when the scanner's origin differed from
   ours, so diagnostics show the rewrite.

Redirects keep the strict origin check in `_check_redirect`. A redirect is a
real request to another address, so it must stay on our origin.

### Why this is safe

Every request still goes only to the origin the user configured or discovery
stored. Credentials are never sent to an address the scanner names. That is
the property the origin check exists to protect, and it now holds by
construction instead of by rejection.

### Alternatives rejected

- **Accept the scanner's origin when its host resolves to the same device.**
  It needs DNS lookups, it still contacts an address taken from the scanner's
  response, and it adds code for no gain.
- **Store port 80 for HP during discovery.** A vendor-specific rule that
  leaves manual hostname entries broken and depends on HP keeping port 80.
- **Allow any port on the same host.** It sends credentials to a port the user
  never configured, and it does not fix hostname entries.

## Stranded jobs

After this change, `create_job` can only reject a `Location` whose path is
outside `ScanJobs`. That URL cannot be trusted as a delete target either, so
the integration cannot cancel the job it identifies. In that one case the
error message will say that the scanner may still be running a job and should
be cancelled on its panel. No device on record sends such a path. The
coordinator already owns the job URL as soon as `create_job` returns, so no
other path strands a job.

## Tests (written first, failing on 0.12.7)

- A client on port 8080 resolves `http://<other IP>:80/eSCL/ScanJobs/x` to
  `<our origin>/eSCL/ScanJobs/x`.
- A hostname client resolves an IP-based `Location` the same way.
- A root-relative `Location` and one with a query string still work.
- A `Location` with a path outside `ScanJobs` is rejected, whatever its origin.
- End to end against a test server: `create_job` gets a `Location` that names
  a second server. All later requests (`NextDocument`, `DELETE`) reach the
  first server, and the second server receives nothing.
- The existing redirect tests stay unchanged and still pass.

## Release

0.12.8 with a CHANGELOG entry under Fixed. Live check on the M283fdw: set the
entry back to port 8080, run a 3-page feeder scan, and confirm the PDF.
Optionally repeat with the hostname `NPIC25FE4.local` as the host.
