"""eSCL client.

Implements the surface we need from the AirScan/eSCL spec:

    GET    /eSCL/ScannerStatus            — device state, ADF presence, active jobs
    POST   /eSCL/ScanJobs                  — create a scan job (XML ScanSettings body)
    GET    /eSCL/ScanJobs/{uuid}           — JobInfo (state, pages, reasons)
    GET    /eSCL/ScanJobs/{uuid}/NextDocument — pull next image/PDF; 404 when done
    DELETE /eSCL/ScanJobs/{uuid}           — cancel

eSCL XML is namespaced (scan:* and pwg:*) but vendor implementations differ
in capitalization and attribute set. We parse via ElementTree using local
tag names only, which has proven more robust than namespace-strict parsing.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import logging
import re
import ssl
from typing import Optional
from xml.etree import ElementTree as ET

import aiohttp

_LOGGER = logging.getLogger(__name__)

# Terminal job states (eSCL JobInfo/JobState).
TERMINAL_JOB_STATES = {"Completed", "Canceled", "Aborted"}


# ── ScanSettings XML template ────────────────────────────────────────────────
#
# US Letter region at 1/300" units = 2550 x 3300 (W x H). We use that as
# a safe default — most scanners clamp to their native bed size anyway.
# A4 would be 2480 x 3508; users typically don't care unless they hit
# the edge of the bed.
_SCAN_SETTINGS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<scan:ScanSettings xmlns:scan="http://schemas.hp.com/imaging/escl/2011/05/03"
                   xmlns:pwg="http://www.pwg.org/schemas/2010/12/sm">
  <pwg:Version>2.63</pwg:Version>
  <scan:Intent>Document</scan:Intent>
  <pwg:ScanRegions>
    <pwg:ScanRegion>
      <pwg:Height>{height}</pwg:Height>
      <pwg:Width>{width}</pwg:Width>
      <pwg:XOffset>0</pwg:XOffset>
      <pwg:YOffset>0</pwg:YOffset>
      <pwg:ContentRegionUnits>escl:ThreeHundredthsOfInches</pwg:ContentRegionUnits>
    </pwg:ScanRegion>
  </pwg:ScanRegions>
  <pwg:InputSource>{source}</pwg:InputSource>
  <scan:DocumentFormatExt>{format}</scan:DocumentFormatExt>
  <scan:XResolution>{dpi}</scan:XResolution>
  <scan:YResolution>{dpi}</scan:YResolution>
  <scan:ColorMode>{color}</scan:ColorMode>
</scan:ScanSettings>
"""


def _color_mode(color: str) -> str:
    """Map our short codes to eSCL ColorMode values."""
    if color == "gray":
        return "Grayscale8"
    return "RGB24"


@dataclass
class ScannerStatus:
    """Parsed snapshot of ScannerStatus."""

    state: str  # "Idle", "Processing", "Down", "Testing", "Stopped", ...
    adf_loaded: bool
    active_job_uris: list[str] = field(default_factory=list)

    @property
    def is_idle(self) -> bool:
        return self.state == "Idle"


@dataclass
class JobInfo:
    """Parsed snapshot of a ScanJob's JobInfo."""

    state: str  # "Pending", "Processing", "Completed", "Canceled", "Aborted"
    state_reasons: Optional[str]
    pages_completed: Optional[int]

    @property
    def is_terminal(self) -> bool:
        return self.state in TERMINAL_JOB_STATES


# ── XML parsing helpers ──────────────────────────────────────────────────────


def _local(tag: str) -> str:
    """Strip XML namespace prefix from an element's tag."""
    return tag.split("}", 1)[1] if "}" in tag else tag


def _find_local(root: ET.Element, name: str) -> Optional[ET.Element]:
    for el in root.iter():
        if _local(el.tag) == name:
            return el
    return None


def _text(el: Optional[ET.Element]) -> Optional[str]:
    return el.text.strip() if el is not None and el.text else None


def parse_scanner_status(xml: bytes) -> ScannerStatus:
    """Tolerant parse of ScannerStatus XML.

    Vendors differ on whether AdfState appears at all (no ADF), the casing
    of state values, and the namespace of the job-uri element. We collect
    JobUris via regex as a fallback because some scanners nest them
    inconsistently under JobInfo/ScannerStatus.
    """
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise ValueError(f"ScannerStatus: invalid XML ({exc})") from exc

    state = _text(_find_local(root, "State")) or "Unknown"
    adf_state = _text(_find_local(root, "AdfState"))
    adf_loaded = adf_state == "ScannerAdfLoaded"

    # Active job URIs — these are absolute or root-relative URLs.
    uris = [m.group(1) for m in re.finditer(r"<[^>]*JobUri[^>]*>([^<]+)</", xml.decode("utf-8", "replace"))]
    return ScannerStatus(state=state, adf_loaded=adf_loaded, active_job_uris=uris)


def parse_job_info(xml: bytes) -> JobInfo:
    """Tolerant parse of JobInfo XML for a single ScanJob."""
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise ValueError(f"JobInfo: invalid XML ({exc})") from exc
    state = _text(_find_local(root, "JobState")) or "Unknown"
    # JobStateReasons is sometimes a leaf with text ("JobCompletedSuccessfully")
    # and sometimes a wrapper around <JobStateReason>…</JobStateReason> children.
    # Cover both: take the wrapper's text if non-empty, else the first child's text.
    reasons_wrapper = _find_local(root, "JobStateReasons")
    reasons = _text(reasons_wrapper)
    if reasons is None and reasons_wrapper is not None:
        for child in reasons_wrapper:
            if _local(child.tag) == "JobStateReason":
                reasons = _text(child)
                break
    if reasons is None:
        reasons = _text(_find_local(root, "JobStateReason"))
    pages_raw = _text(_find_local(root, "ImagesCompleted")) or _text(
        _find_local(root, "PagesCompleted")
    )
    pages = None
    if pages_raw is not None:
        try:
            pages = int(pages_raw)
        except ValueError:
            pages = None
    return JobInfo(state=state, state_reasons=reasons, pages_completed=pages)


# ── SSL helper ──────────────────────────────────────────────────────────────


def _ssl_context(*, verify: bool, relaxed_ciphers: bool) -> ssl.SSLContext:
    """Build an SSL context for talking to a scanner. See ipp_print's
    PrinterClient for the rationale behind the relaxed-ciphers escape hatch
    — some HP LaserJet MFPs only offer non-PFS suites that SECLEVEL=2 rejects."""
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    if verify:
        ctx.check_hostname = True
        ctx.verify_mode = ssl.CERT_REQUIRED
        ctx.load_default_certs()
    else:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    if relaxed_ciphers:
        ctx.set_ciphers("DEFAULT:@SECLEVEL=0")
    return ctx


# ── Client ──────────────────────────────────────────────────────────────────


class ScannerClient:
    """eSCL client bound to a single scanner host."""

    def __init__(
        self,
        *,
        host: str,
        port: int = 443,
        use_tls: bool = True,
        user: str = "anonymous",
        password: str = "",
        verify_tls: bool = False,
        relaxed_ciphers: bool = False,
        timeout: float = 120.0,
    ) -> None:
        self._host = host
        self._port = port
        self._use_tls = use_tls
        self._user = user
        self._password = password
        self._verify_tls = verify_tls
        self._relaxed_ciphers = relaxed_ciphers
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        scheme = "https" if use_tls else "http"
        port_suffix = "" if port in (80, 443) else f":{port}"
        self._origin = f"{scheme}://{host}{port_suffix}"
        self._base = f"{self._origin}/eSCL"

    @property
    def host(self) -> str:
        return self._host

    @property
    def base_url(self) -> str:
        return self._base

    def _absolute(self, uri: str) -> str:
        """Resolve a job URI (may be absolute or root-relative)."""
        if uri.startswith("http://") or uri.startswith("https://"):
            return uri
        if uri.startswith("/"):
            return f"{self._origin}{uri}"
        return f"{self._base}/{uri}"

    def _connector(self) -> aiohttp.TCPConnector:
        if self._use_tls:
            return aiohttp.TCPConnector(
                ssl=_ssl_context(
                    verify=self._verify_tls,
                    relaxed_ciphers=self._relaxed_ciphers,
                )
            )
        return aiohttp.TCPConnector()

    def _auth(self) -> Optional[aiohttp.BasicAuth]:
        return (
            aiohttp.BasicAuth(self._user, self._password)
            if self._password
            else None
        )

    async def _session(self, *, timeout: float | None = None) -> aiohttp.ClientSession:
        return aiohttp.ClientSession(
            connector=self._connector(),
            timeout=(aiohttp.ClientTimeout(total=timeout) if timeout else self._timeout),
            auth=self._auth(),
        )

    # ── Status ──────────────────────────────────────────────────────────

    async def get_scanner_status(self) -> ScannerStatus:
        async with await self._session(timeout=10.0) as s:
            async with s.get(f"{self._base}/ScannerStatus") as resp:
                resp.raise_for_status()
                return parse_scanner_status(await resp.read())

    # ── ScanJob lifecycle ───────────────────────────────────────────────

    async def detect_source(self) -> str:
        """Pick Feeder if ADF is loaded, else Platen. Best-effort —
        fall back to Platen on probe failure."""
        try:
            st = await self.get_scanner_status()
        except Exception as exc:
            _LOGGER.debug("source detect: status probe failed: %s", exc)
            return "Platen"
        return "Feeder" if (st.is_idle and st.adf_loaded) else "Platen"

    async def create_job(
        self,
        *,
        source: str,
        dpi: int,
        color: str,
        document_format: str = "application/pdf",
        width: int = 2550,
        height: int = 3300,
    ) -> str:
        """Create a ScanJob; returns the job's absolute URL.

        Raises if the device returns a non-2xx status or omits the Location
        header. Tolerates the 503-while-an-old-job-is-pending case by purging
        and retrying once.
        """
        body = _SCAN_SETTINGS_XML.format(
            source=source,
            dpi=dpi,
            color=_color_mode(color),
            format=document_format,
            width=width,
            height=height,
        ).encode("utf-8")
        headers = {"Content-Type": "text/xml; charset=utf-8"}

        async with await self._session() as s:
            r = await s.post(f"{self._base}/ScanJobs", data=body, headers=headers)
            if r.status == 503:
                # Likely a stale prior job. Purge and retry.
                _LOGGER.info("eSCL ScanJobs returned 503; purging and retrying")
                await self._purge_active_jobs(s)
                r = await s.post(f"{self._base}/ScanJobs", data=body, headers=headers)
            if r.status not in (200, 201):
                raise RuntimeError(
                    f"scan create failed: {r.status} {(await r.text())[:200]}"
                )
            loc = r.headers.get("Location")
            if not loc:
                raise RuntimeError("scan create: no Location header")
            return self._absolute(loc)

    async def get_job_info(self, job_url: str) -> Optional[JobInfo]:
        """Fetch JobInfo for an in-flight scan. Returns None on 404
        (job already cleaned up by device or never existed)."""
        async with await self._session(timeout=10.0) as s:
            async with s.get(job_url) as resp:
                if resp.status == 404:
                    return None
                resp.raise_for_status()
                return parse_job_info(await resp.read())

    async def pull_next_document(self, job_url: str) -> Optional[bytes]:
        """GET ScanJobs/{uuid}/NextDocument. Returns the body bytes, or None
        if the scanner reports no more pages.

        Status code handling:
          * 404 / 410 — canonical "no more documents". Return None.
          * 503 — HP returns this in two contradictory ways:
                  (a) the document IS exhausted (signals "done")
                  (b) the next chunk is still being processed ("retry me")
                Strategy: retry a couple times with backoff. If 503 persists
                we treat it as "done" so the loop terminates.
          * 500 — sometimes transient. Retry once.

        The caller decides whether to keep partial buffer state on a None
        return — see coordinator's PDF validation.
        """
        import asyncio

        for attempt in range(3):
            async with await self._session() as s:
                async with s.get(f"{job_url}/NextDocument") as resp:
                    if resp.status in (404, 410):
                        return None
                    if resp.status in (500, 503):
                        # Transient on attempt 0-1; treat as "done" on the
                        # third try if it still hasn't resolved.
                        if attempt < 2:
                            await asyncio.sleep(0.5 * (attempt + 1))
                            continue
                        return None
                    resp.raise_for_status()
                    return await resp.read()
        return None

    async def delete_job(self, job_url: str) -> bool:
        """Cancel a scan job. Returns True on 2xx, False otherwise.
        Treats 404 as success (already gone)."""
        async with await self._session(timeout=10.0) as s:
            async with s.delete(job_url) as resp:
                if resp.status == 404:
                    return True
                return 200 <= resp.status < 300

    async def purge_active_jobs(self) -> int:
        """Cancel every job the scanner is currently aware of. Returns
        the count of jobs purged. Best-effort — failures are swallowed."""
        async with await self._session(timeout=10.0) as s:
            return await self._purge_active_jobs(s)

    async def _purge_active_jobs(self, session: aiohttp.ClientSession) -> int:
        try:
            async with session.get(f"{self._base}/ScannerStatus") as resp:
                if resp.status != 200:
                    return 0
                status = parse_scanner_status(await resp.read())
        except Exception:
            return 0
        purged = 0
        for uri in status.active_job_uris:
            try:
                async with session.delete(self._absolute(uri)) as r:
                    if 200 <= r.status < 300 or r.status == 404:
                        purged += 1
            except Exception:
                pass
        return purged
