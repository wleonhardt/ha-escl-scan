# Rollout closeout and compatibility follow-up

Status: main dashboard promoted; compatibility checks in progress.
The original six-phase rollout is complete. This follow-up is explicitly
requested by the user and does not silently include multi-scanner support,
new transports/authentication, converters, presets or new translations.

## Main dashboard

Moved the accepted native Tile Scan/Print pair and its device heading into
`/lovelace/printer`. Retained one Vertical stack per tile for independent growth,
all original connection tiles, page/jam chips, navigation, theme and other views.
The preview remains available. No integration update or restart was required.
Dashboard backup: `/config/.document-card-backups/before-native-main-20261009.json`.
Saved/read-back configuration matches the reviewed candidate. Real host checks
at 320/390/768 px pass for each disclosure independently, both open, and closing;
a fresh main-dashboard load also passes.

## Compatibility scope and gates

1. Discover actual HP `_uscan`, `_uscans`, `_ipp` and `_ipps` advertisements.
   Test first-time confirmation and duplicate detection using an isolated HA
   registry/configuration, with read-only device probes. Do not remove or modify
   production entries, submit jobs or alter device network settings. Distinguish
   received LAN advertisements, flow acceptance and endpoint reachability.
2. Reproduce card-mod's Options warning, identify its origin and assess a narrow
   fix against HA's public dialog contract. Verify both Options dialogs, Back,
   closure and focus, with/without card-mod and on minimum/current HA as needed.
3. Provide a structured device report and compatibility matrix. Distinguish
   synthetic fixtures, read-only probes and physical output acceptance. Only
   implement vendor workarounds after a representative failure is reproduced.
4. Keep external physical checks explicit: automatic-duplex ADF, additional
   vendors, AirSane/ipp-usb and multi-device hardware need devices/reporters.
   Prepare the reporting path here; contacting reporters requires authorization.

Implementation changes require focused regressions, all repository checks,
version/changelog updates and hosted CI before release/install. Documentation
and dashboard-only work need no integration version or tag. Record evidence and
remaining limits below as the checks finish.

## Discovery findings and fixes

Actual HP DNS-SD advertisements were received on the LAN for HTTP eSCL/8080,
HTTPS eSCL/443, IPP/631 and IPPS/631. The resource paths are `eSCL` and `ipp/print`.
No saved production connection setting was used to manufacture these records.

The isolated HA 2026.9.4 flow registry reproduced two failures: the secure HP
endpoints reject the default cipher negotiation; Print retained its failed
confirmation, while Scan created a configured entry despite an unusable endpoint.
Both secure endpoints passed read-only probes when the existing legacy cipher
option was explicitly enabled. Plain discovery endpoints passed with defaults.

Scan 0.12.1 shares the manual setup probe with discovery, closes clients on all
paths and rechecks the single-scanner limit after awaiting I/O. Failed discovery
stays on the form. Both integrations expose the existing legacy cipher option
on secure discovery confirmation, initially off. TLS/port/path remain as
advertised; no automatic fallback or global SSL policy change is introduced.
The user must choose the compatibility setting before another probe uses it.

All four live advertisement cases pass in the isolated config-entry flow:
confirmation, stored endpoint, read-only device response, rediscovery rejection
and exactly one entry. Secure cases first prove a default failure creates no
entry, then explicitly retry with legacy ciphers. Integration setup was stubbed
in this fixture to avoid registering another running coordinator; these are
flow-level runtime checks, not a second fully onboarded HA installation. Actual
LAN delivery and endpoint I/O are live; production entries, UUIDs, devices,
network settings and jobs were left alone. Raw identifying captures stay outside
Git. Ordinary tests remain socket-blocked and use patched network boundaries.

## card-mod finding and fix

Reproduced `TypeError: this.requestUpdate is not a function` with installed
card-mod 4.2.1 after opening Options. Its
[dialog hook](https://github.com/thomasloven/lovelace-card-mod/blob/master/src/patch/ha-dialog.ts)
wraps every `show-dialog` host and assumes Lit update methods plus a shadow root.
Our plain HTMLElement routing host has no asynchronous rendering or visible
surface; its panel remains in the owning card for theme and navigation handling.

Shared core v5 provides an empty shadow root and already-completed synchronous
update hooks on that small host. card-mod can inspect it without throwing and
finds no HA dialog shell to restyle. No Lit dependency, private card-mod registry
mutation, window error suppression or change to other custom cards is involved.
The new regression reproduces the failure on the previous module and verifies
opening, HA closure, stale parameters and focus after the fix in both repositories.

Exact candidate modules loaded under isolated names coexist with the installed
core v4 modules. On the real HA/card-mod 4.2.1 host, Scan and Print Options render,
card-mod confirms it patched each candidate, no errors are captured, and Back
closes each panel. The visible panel still lives in its original card shadow root.

## Reporting and validation

Both compatibility guides now distinguish completed HP physical acceptance from
synthetic vendor coverage, read-only bridge probes and unavailable hardware.
New device-report issue forms collect firmware, transport/bridge, setup options,
actual operations and reviewed diagnostics, including successful reports. No
reporter was contacted and no unsupported hardware support is claimed.

Required local checks pass: Scan 243 Python + 78 card; Print 231 Python + 65 card
(617 total), npm ci, Ruff and Print compileall. JSON/translations, issue/example
YAML and shared-core parity are checked. Live discovery adds four separate HP
flow checks. Hosted validation, release and installed-version checks follow.
