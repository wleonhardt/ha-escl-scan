# Scanning and saved files

[Documentation](README.md) · [Dashboard setup](dashboard.md)

## Scan a document

1. Put the document on the glass or in the automatic document feeder (ADF).
2. Open the sliders button if you want to change the scan settings.
3. Press **Scan**. The card shows progress and offers **Cancel** while scanning.
4. When the scan succeeds, press **Download PDF**.

With **Automatic** source, the scanner's feeder status determines the source:
loaded feeder first, otherwise glass. Choose **Feeder** or **Glass** explicitly
if that detection does not match what you want. Only one scan can run at a time.

## Scan both sides

Turn on **Two-sided** for a feeder document. Scanning both sides and printing
both sides are separate hardware capabilities.

| Card message | What happens |
| --- | --- |
| Automatic duplex | The scanner supplies both sides in one job. |
| Two passes required | Scan the fronts, then reload the backs when prompted. |
| May need two passes | Capability information is unavailable or stale; the label cannot confirm automatic support. |

For a manual two-pass scan:

1. Load the fronts in document order and press **Scan**.
2. **Wait for the reload prompt before flipping the sheets.** Some scanners
   keep accepting pages into the first pass after the feeder appears finished.
3. Reload the backs in the orientation required by your feeder.
4. Choose **First sheet first** if the first sheet will feed first, or
   **Last sheet first (flipped stack)** if flipping reversed the stack order.
5. Press **Scan back sides**.

The final PDF is ordered front 1, back 1, front 2, back 2, and so on. The
integration uses your order selection; it does not read page numbers or infer
which sheet is which. Both passes must contain the same number of pages.

You can cancel while waiting. The reload window expires after **15 minutes**.
Incomplete fronts stay private and a mismatch does not publish a partial PDF.
A failed automatic duplex job is not silently restarted as a manual scan.

If every back page is upside down, enable **Rotate scanned back sides 180
degrees** in the integration options. This applies to both automatic and manual
duplex output. It changes orientation, not sheet order.

## Choose scan settings

| Option in the card | What it does |
| --- | --- |
| Source | Automatic, Feeder or Glass. Glass cannot scan both sides. |
| Color | Integration default, Color or Grayscale. |
| Resolution | Integration default or a supported DPI. Higher DPI creates larger files. |
| Page size | Full scan area, Letter, A4 or Custom. Custom dimensions use millimeters. |

**Full scan area** uses the source's advertised maximum area; it is not automatic
paper-size detection. A specific size can reduce blank margins. Requested DPI
is adjusted to supported resolutions for the chosen source, color and duplex
profile when the scanner provides those capabilities.

Permanent integration defaults live under **Settings → Devices & services →
eSCL Scan → Configure / Options**:

| Setting | Default |
| --- | --- |
| Resolution | 300 DPI |
| Color | Color |
| Scan both sides | Off |
| Rotate back sides | Off |
| Scanned file retention | 3600 seconds (one hour) |
| Copy finished scans to a folder | Disabled |

The card's Two-sided switch overrides the integration duplex default. Card
color and resolution use the integration defaults unless overridden; see
[card defaults](dashboard.md#card-defaults).

## Download and retention

After a successful scan, the main action becomes **Download PDF**. Once the
file has been handed to your browser, the action returns to **Scan**. The
browser controls saving/opening the file and cannot tell the card whether you
canceled its save dialog.

Expand **Latest scan** to download the most recent successful result again.
That record and its original expiry survive dashboard refreshes and Home
Assistant restarts. Downloading does not extend retention. Downloads require
Home Assistant authentication and can work while the scanner is offline.

Only the latest successful scan is listed; this is not an archive of all PDFs.
Failed or canceled scans do not replace it. Expired or missing files show an
explanation instead of a download link. Set a positive retention period in
seconds; `0` means immediate expiry, not unlimited storage. Removing the
integration deletes its latest-result metadata.

An active scan or a waiting back-side pass does **not** resume after a Home
Assistant restart or integration reload. Saved successful results are separate
from active-job recovery.

## Save scans to a folder

For permanent copies or Paperless-ngx, choose an absolute folder path accessible
to Home Assistant. For example, add this to `configuration.yaml`, merging it
into an existing `homeassistant:` section if present:

```yaml
homeassistant:
  allowlist_external_dirs:
    - /media/paperless/consume
```

Restart Home Assistant to apply that configuration, then set **Also copy finished
scans to this folder** to `/media/paperless/consume` in the integration options.
For Paperless-ngx, this must be the actual consume folder mounted into Home
Assistant, not a path that exists only inside another container.

Only complete, successful PDFs are copied. A temporary file is renamed into
place so folder watchers do not receive a half-written document. These copies
are never deleted by scan retention. If copying fails, the local completed
PDF remains downloadable and the failure is logged. Cancellation is no longer
accepted once folder publication starts.

## Output and limits

Scans are PDFs. Native PDF is preferred; JPEG/PNG-only scanner profiles are
converted to PDF. No OCR is performed; use Paperless-ngx or another OCR tool
for searchable text. TIFF, multi-frame images and asymmetric-only resolutions
are not supported.

The complete batch is limited to **1 GiB**, including both duplex passes.
Encoded image inputs are limited to **50 MiB and 40 megapixels**. The integration
also checks for **256 MiB free disk headroom** before jobs and as files grow;
PDF assembly can need additional temporary space. Use smaller batches, lower
DPI or a smaller page size if these limits are reached.

[Connection or scan problems →](troubleshooting.md)
