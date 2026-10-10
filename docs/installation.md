# Installation and connection settings

[Documentation](README.md) · [Next: dashboard](dashboard.md)

## Install with HACS

1. In **HACS**, search for **eSCL Scan** and select **Download**.
2. Restart Home Assistant.
3. Add your scanner under **Settings → Devices & services**.

[Open eSCL Scan in HACS](https://my.home-assistant.io/redirect/hacs_repository/?owner=wleonhardt&repository=ha-escl-scan&category=integration).
Both this integration and its dashboard controls are included in the download.

## Add the device

**Discovered device:** select **Configure** on the discovered scanner.
The connection is checked before the entry is saved. No document is scanned
during this check.

**Manual setup:** choose **Add integration → eSCL Scan**. Use this when discovery
is unavailable, the device is on another network, or credentials are required.
Enter the hostname or IP address separately from the port and path.

| Field | Default | When to change it |
| --- | --- | --- |
| Hostname or IP | Required | Use the address reachable from Home Assistant, such as `scanner.local`. |
| Port | `443` | Use the device's advertised port. Plain HTTP commonly uses `80`. |
| Scanner resource path | `eSCL` | Use the advertised resource path for bridges; `/` means the server root. |
| Use TLS | On | Match the endpoint: on for HTTPS, off for HTTP. The port alone does not determine this. |
| User | `anonymous` | Only needed with a password for HTTP Basic authentication. |
| Password | Empty | Fill in only if the endpoint requires HTTP Basic authentication. |
| Verify TLS certificate | Off | Enable for an endpoint with a certificate trusted by Home Assistant. |
| Allow legacy cipher suites | Off | Enable only for a device that needs older TLS ciphers, such as some HP LaserJets. |

TLS encrypts the connection. **Verify TLS certificate** additionally checks the
server certificate; it is off by default to accommodate self-signed devices.
Legacy ciphers are an explicit per-device option and are never enabled automatically.

Change saved connection details through the integration's **Configure / Options**
action in **Settings → Devices & services**. Scan defaults and file retention are explained in [Scanning](scanning.md).

Only one scanner can be configured in this integration.
For bridges or network discovery problems, see [Compatibility](compatibility.md).

## Update

1. Wait for active scans, including any waiting back-side pass, to finish.
2. Open **HACS → eSCL Scan** and download the offered stable update.
3. Restart Home Assistant and refresh the dashboard.

The integration refreshes its card resource automatically. Existing dashboard
cards do not need to be recreated. Saved results keep their existing expiry.

If files were previously copied into `custom_components` manually, HACS may not
track them as installed. Download the integration through HACS once, restart,
and check that HACS shows an installed version.

## Manual installation

1. Download the source archive for a [stable release](https://github.com/wleonhardt/ha-escl-scan/releases).
2. Copy its `custom_components/escl_scan` directory into
   `<config>/custom_components/escl_scan` on the Home Assistant host.
3. Restart Home Assistant, then follow **Add the device** above.

For manual updates, back up the existing directory and replace it with the
matching directory from the new release. Do not mix files from different releases.
HACS is the easier route for ongoing update notifications.
