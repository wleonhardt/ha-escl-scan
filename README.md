# eSCL Scan for Home Assistant

[![HACS Default](https://img.shields.io/badge/HACS-Default-41BDF5.svg)](https://github.com/hacs/default)
[![Release](https://img.shields.io/github/v/release/wleonhardt/ha-escl-scan)](https://github.com/wleonhardt/ha-escl-scan/releases)
[![Validation](https://github.com/wleonhardt/ha-escl-scan/actions/workflows/validate.yml/badge.svg)](https://github.com/wleonhardt/ha-escl-scan/actions/workflows/validate.yml)

Scan documents to PDF from your Home Assistant dashboard. Use the scanner glass
or document feeder, scan both sides, and download the finished file.

Pairs with [IPP Print](https://github.com/wleonhardt/ha-ipp-print) for matching
Scan and Print controls on the same dashboard.

## Before you start

- **Home Assistant 2024.12 or newer.**
- An eSCL / AirScan network scanner reachable from Home Assistant. One scanner
  can be configured per Home Assistant instance.

Check [device compatibility](docs/compatibility.md) if you are unsure about your
hardware or use a USB device, bridge or separate network.

## Installation

[![Open in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=wleonhardt&repository=ha-escl-scan&category=integration)

1. Open **HACS**, search for **eSCL Scan**, and select **Download**.
   It is in the default store; no custom repository is needed.
2. Restart Home Assistant.
3. Open **Settings → Devices & services** and configure the discovered scanner.
   If it does not appear, choose **Add integration → eSCL Scan** and enter its
   connection details.

[Manual installation, connection settings and updates →](docs/installation.md)

## Adding the card to a dashboard

1. Edit your dashboard and add a **Tile** card.
2. Select the scanner's **Current scan** sensor from this integration.
3. In **Features**, add **eSCL Scan**. Set **Features position** to **Bottom**.
4. In a Sections dashboard, leave **Rows** set to **Auto** so messages can expand.

The card is included and registered automatically. No separate card download,
resource entry or styling code is needed.

[Dashboard examples, side-by-side cards and other card types →](docs/dashboard.md)

## Scan your first document

1. Place a document on the glass or load the feeder.
2. Turn on **Two-sided** for a double-sided feeder document. If your scanner
   needs a manual second pass, the card will tell you when and how to reload it.
3. Press **Scan**, then **Download PDF** when it finishes.

Use the sliders button for source, color, resolution and page size. **Latest
scan** keeps the most recent result available after a refresh or restart,
until it expires. Downloads are retained for **one hour by default**.

Need to save every scan? See [scan to folder and Paperless-ngx](docs/scanning.md#save-scans-to-a-folder).

## Guides and help

| I want to… | Read |
| --- | --- |
| Adjust scan defaults, two-sided scanning or saved files | [Scanning](docs/scanning.md) |
| Build an automation | [Actions, entities and events](docs/automations.md) |
| Fix a problem | [Troubleshooting](docs/troubleshooting.md) |
| Use a bridge or check tested hardware | [Compatibility](docs/compatibility.md) |
| Build a client or contribute | [HTTP API](docs/api.md) · [Contributing](CONTRIBUTING.md) |

[All documentation](docs/README.md) · [Report a problem](https://github.com/wleonhardt/ha-escl-scan/issues/new/choose) · [Changelog](CHANGELOG.md) · [MIT license](LICENSE)
