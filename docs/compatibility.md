# Scanner compatibility

[Documentation](README.md) · [Connection settings](installation.md) · [Troubleshooting](troubleshooting.md)

eSCL Scan connects to an eSCL / AirScan endpoint. A manufacturer name alone
does not establish support: verify the protocol and the functions on your model.
Only one scanner endpoint can be configured. Printing duplex does not imply
automatic duplex scanning.

## Tested devices and evidence

Evidence recorded through 2026-10-10. A community report or successful capability
query is useful evidence, but is not the same as a complete physical test.

| Device or route | Evidence | Limits / unverified work |
| --- | --- | --- |
| HP Color LaserJet MFP M283fdw | Locally verified glass, feeder, manual duplex, cancellation, offline recovery and retained-result restart behavior. | Its feeder is simplex; automatic duplex scanning is unavailable. |
| Epson WF-4830 | Reporter confirmed the duplex fix works in [issue #5](https://github.com/wleonhardt/ha-escl-scan/issues/5#issuecomment-6069504848). | Exact installed version/firmware, orientation and large-batch evidence were not supplied. |
| Epson ET-4950 | [Issue #5](https://github.com/wleonhardt/ha-escl-scan/issues/5) supplied duplex region limits and reports success after a height correction; regression coverage uses that report. | Released-fix acceptance, complete capabilities/firmware, rotation and large batches remain unconfirmed. |
| Brother / Xerox B205-B215 / matched Ricoh models | Scoped recovery policies informed by sane-airscan; simulated retry/delay/cancel tests. | Device captures and physical tests are still needed. |
| JPEG/PNG-only scanner profiles | Simulated conversion, limits, cancellation and duplex-order tests. | No physical image-only scanner tested locally. |
| AirSane / ipp-usb | Endpoint configuration supported; routes documented below. | No local bridge/device acceptance test. |

Report your model through the [device compatibility form](https://github.com/wleonhardt/ha-escl-scan/issues/new?template=device_compatibility.yml),
including successful setups. Share firmware, integration/HA versions, route and
which functions passed. [Collect diagnostics](troubleshooting.md#collect-diagnostics)
for failures. A report does not establish support for every model from that brand.

## Choose a connection route

| Situation | Route |
| --- | --- |
| Network scanner offers eSCL | Connect directly using its advertised host, port, TLS and resource path. |
| SANE scanner without usable eSCL | Use a separately managed AirSane bridge. |
| USB device implements IPP-over-USB | Use a separately managed ipp-usb bridge's eSCL endpoint. |

A bridge is an optional service you manage separately. It exposes a compatible
protocol but does not guarantee every function of the attached device.

## Networks, paths and TLS

- Discovery may not cross VLANs. Manual setup uses the same advertised endpoint.
- A bridge's `localhost` points to the bridge machine, not your Home Assistant
  host/container. Use an address Home Assistant can reach.
- Preserve the full resource/queue path and actual port, including with IPv6.
  Do not assume that an administration web page is the protocol endpoint.
- TLS and port are separate choices. In live HP discovery checks, IPPS on port
  631 needed legacy ciphers while plain IPP on 631 did not. Secure connections
  never silently switch TLS off or enable legacy ciphers.
- Authentication support is HTTP Basic. A bridge requiring browser sign-in,
  Kerberos or another scheme needs a compatible endpoint/policy.

## AirSane

1. On the bridge, install a SANE backend that can see and operate the scanner.
   Confirm discovery as the service user (`scanimage -L`) and a local scan.
2. Install AirSane using its platform instructions. Its documented default port
   is 8090. Permit the HA host in its access rules and firewall.
3. Prefer its discovered eSCL advertisement. For manual setup use the bridge
   host, actual port/TLS and advertised resource path. The compatible first
   scanner path is normally `eSCL`; do not assume that path for every scanner.
4. Verify glass/feeder, colors and DPI. This integration selects one scanner
   endpoint; AirSane's ability to publish several does not add multi-scanner
   routing to this integration.

Capabilities and scan quality depend on the SANE backend. AirSane access files
control allowed addresses; do not assume browser login or new authentication
schemes are supported here. [AirSane documentation](https://github.com/SimulPiscator/AirSane).

## ipp-usb

1. Confirm the USB device implements IPP-over-USB; this is not a generic USB driver.
2. Install ipp-usb on the computer attached to it. Use DNS-SD/service discovery to
   find the assigned port and each service path; never assume a particular port.
3. Its default exposure is local to the bridge. For a separate HA machine,
   deliberately configure reachable interfaces/access controls. Do not enter
   the bridge's loopback address into a remote HA installation.
4. Configure print and scan independently from their advertised endpoints, then
   verify capabilities and a small job. The proxy does not convert arbitrary
   documents into a printer language.

[ipp-usb documentation](https://github.com/OpenPrinting/ipp-usb) describes its HTTP
proxy, DNS-SD, persisted port allocation and loopback/default interface policy.

For printing through CUPS or a Printer Application, see
[IPP Print compatibility](https://github.com/wleonhardt/ha-ipp-print/blob/main/docs/compatibility.md).

## Before relying on a new device

Test one small document first, then the modes you need. Record physical results
separately from discovered options. For scanning, verify source, page order and
orientation; for printing, verify format, copies, binding and paper/tray.

Do not resend a print whose acceptance is unknown without checking its queue.
A failed/consumed scan batch is not automatically restarted. See the maintainer
[compatibility follow-up](../plans/compatibility-follow-up-2026-10-09.md)
for historical tests and remaining hardware coverage.
