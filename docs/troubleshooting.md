# Troubleshooting

[Documentation](README.md) · [Compatibility](compatibility.md)

## Start here

Check the scanner's own screen and **Connection** entity in Home Assistant.
Connected means the protocol answers; it does not promise paper, readiness or
a successful job. Idle describes the integration's current job, not connectivity.

| Symptom | What to do |
| --- | --- |
| Device is not discovered | Discovery may not cross VLANs. Use [manual setup](installation.md#add-the-device) with the advertised host, port, path and TLS setting. |
| Setup cannot connect | Confirm Home Assistant can reach the endpoint, then check path, TLS and credentials. A working web management page may use a different port/path from eSCL. |
| TLS handshake failure | If the device needs older ciphers, explicitly enable **Allow legacy cipher suites**. Do not enable it for unrelated connection errors. |
| Certificate verification error | Match **Verify TLS certificate** to the device's certificate/trust setup. This is separate from cipher compatibility. |
| Authentication failed | Check HTTP Basic credentials; browser login, Kerberos and other authentication methods are not supported. |
| Scanner busy / conflict (409) | Finish or cancel the active scan, including any waiting back-side pass. If another app owns the scanner job, finish it there or on the device. |
| Feeder empty | Push the sheets in until the feeder detects them; confirm orientation in the device manual. A rejected back-side resume can be retried once loaded. |
| Back pages are in the wrong order | Match the back-order choice to the actual feed order. See [manual duplex](scanning.md#scan-both-sides). |
| Every back page is upside down | Try **Rotate scanned back sides 180 degrees** in integration options. |
| PDF is truncated or a batch fails | Try a small batch at a supported DPI/color, then collect diagnostics. An incomplete transfer is not a successful scan; the message alone does not identify the cause. |
| Download expired or missing | Local PDFs expire after one hour by default. Use [folder copies](scanning.md#save-scans-to-a-folder) for permanent retention. |
| Copy-to-folder failed | Check the allowlisted path, mount, write permissions and free space. The local completed PDF may still be downloaded. |

## Card does not load

For a persistent **Configuration error**, missing feature or missing controls:

1. Confirm the integration is loaded under **Settings → Devices & services**.
2. After a HACS update, restart Home Assistant and fully reload the dashboard.
3. Check the card's entity: it must be this integration's **Current scan**
   sensor, not its Connection sensor or another printer integration's sensor.
4. Check **Settings → Dashboards → Resources** (Advanced Mode may be needed).
   The integration registers a single `/escl_scan/card-…js` module. Remove only
   obsolete manual duplicates if present; do not create another copy of the module.
5. If it persists, report the full message, integration/HA versions and browser
   or Companion App version. Include a screenshot if the message is truncated.

A short loading delay can resolve itself, but a repeated configuration error
should be investigated. If history expansion moves the neighboring card, use
[one Vertical stack per card](dashboard.md#put-scan-and-print-beside-each-other)
and **Rows: Auto**.

## Collect diagnostics

1. Open **Settings → Devices & services → eSCL Scan**.
2. Open the integration/device overflow menu and select **Download diagnostics**.
3. Include that file with a [bug or device report](https://github.com/wleonhardt/ha-escl-scan/issues/new/choose).

The download includes redacted entry details, parsed scanner capabilities,
tracked scan details and applied compatibility policies. Include source
(glass/feeder), one- or two-sided mode, DPI, color, page size, page count, and
which stage failed. Do not attach private scanned pages unless needed.

For additional logs, merge this into `configuration.yaml`:

```yaml
logger:
  logs:
    custom_components.escl_scan: debug
```

Restart to apply the YAML, reproduce once, then remove or disable the debug
setting. Review raw logs and manually collected protocol captures for private
values before sharing. Include device model/firmware, connection route (direct
or bridge), Home Assistant version and integration version.

## Limits that can stop a job

| Limit | Behavior |
| --- | --- |
| Complete document | 1 GiB across the batch, including manual duplex passes and generated PDFs. |
| Image input | 50 MiB encoded and 40 megapixels decoded per image. |
| Free disk headroom | 256 MiB checked before jobs and as scan files grow; assembly needs extra space. |
| Protocol control response | 1 MiB after decompression for status, capabilities, job status and start-error replies. |

Lower DPI, reduce page size or split a large batch. Disk headroom is a check,
not reserved space; other software can still fill the disk. An oversized control
reply needs investigation of the device/bridge response, not a larger scan-size
setting. Failed scans clean up temporary data without deleting earlier retained
results. See [output limits](scanning.md#output-and-limits).
