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
