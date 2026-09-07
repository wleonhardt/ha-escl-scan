"""eSCL client.

Implements the surface we need from the AirScan/eSCL spec:

    GET    /eSCL/ScannerCapabilities      — model, serial, bed sizes, duplex, DPIs
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

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
import logging
import re
import ssl
from xml.etree import ElementTree as ET

import aiohttp

_LOGGER = logging.getLogger(__name__)

# Terminal job states (eSCL JobInfo/JobState).
TERMINAL_JOB_STATES = {"Completed", "Canceled", "Aborted"}

# Stream document bytes to disk in chunks this size. Large enough to keep
# executor round-trips down on multi-hundred-MB ADF batches, small enough that
# transient per-chunk memory stays negligible on Pi-class hosts.
_STREAM_CHUNK = 1024 * 1024

# Per-request timeout overrides on the shared session (which carries a longer
# default for job creation). Status/poll/delete are quick control calls;
# document streaming bounds only the socket-read stall, never total transfer.
_SHORT_TIMEOUT = aiohttp.ClientTimeout(total=10.0)
_STREAM_TIMEOUT = aiohttp.ClientTimeout(sock_connect=15, sock_read=90)

# NextDocument may answer 503 while the ADF is still feeding the next sheet.
# We keep retrying while JobInfo says the job is alive, bounded by this
# wall-clock budget so a wedged device can't hang the driver forever.
NEXT_DOCUMENT_RETRY_SECONDS = 120.0

# After a cancel (or a previous job finishing) HP MFPs answer 503 on ScanJobs
# and report Processing for a few seconds. Wait this long for Idle before
# declaring the device busy with someone else's job.
SCANNER_IDLE_WAIT_SECONDS = 15.0


# ── ScanSettings XML template ────────────────────────────────────────────────
#
# Region units are 1/300". The coordinator passes the source's MaxWidth /
# MaxHeight from ScannerCapabilities so the full bed is scanned whatever the
# paper size. When capabilities are unavailable we fall back to A4-ish
# 2550 x 3508 (Letter width, A4 height) — scanners clamp oversize regions
# down to the bed, but never grow a too-small one, so erring large is safe.
DEFAULT_REGION = (2550, 3508)

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
  <scan:ColorMode>{color}</scan:ColorMode>{duplex}
</scan:ScanSettings>
"""
_DUPLEX_XML = "\n  <scan:Duplex>true</scan:Duplex>"


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
class ScannerCapabilities:
    """Parsed subset of ScannerCapabilities we act on."""

    make_and_model: str | None = None
    serial_number: str | None = None
    uuid: str | None = None
    platen_max: tuple[int, int] | None = None  # (width, height) in 1/300"
    adf_max: tuple[int, int] | None = None
    adf_duplex: bool = False
    resolutions: list[int] = field(default_factory=list)  # sorted, discrete
    color_modes: list[str] = field(default_factory=list)

    @property
    def device_id(self) -> str | None:
        """Stable identifier for unique_id: serial first, then UUID."""
        return self.serial_number or self.uuid

    def region_for(self, source: str) -> tuple[int, int]:
        caps = self.adf_max if source == "Feeder" else self.platen_max
        return caps or DEFAULT_REGION

    def snap_dpi(self, dpi: int) -> int:
        """Nearest supported discrete resolution (or dpi itself if unknown)."""
        if not self.resolutions:
            return dpi
        return min(self.resolutions, key=lambda r: (abs(r - dpi), r))


@dataclass
class JobInfo:
    """Parsed snapshot of a ScanJob's JobInfo."""

    state: str  # "Pending", "Processing", "Completed", "Canceled", "Aborted"
    state_reasons: str | None
    pages_completed: int | None

    @property
    def is_terminal(self) -> bool:
        return self.state in TERMINAL_JOB_STATES


# ── XML parsing helpers ──────────────────────────────────────────────────────


def _local(tag: str) -> str:
    """Strip XML namespace prefix from an element's tag."""
    return tag.split("}", 1)[1] if "}" in tag else tag


def _find_local(root: ET.Element, name: str) -> ET.Element | None:
    for el in root.iter():
        if _local(el.tag) == name:
            return el
    return None


def _text(el: ET.Element | None) -> str | None:
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
    text = xml.decode("utf-8", "replace")
    uris = [m.group(1) for m in re.finditer(r"<[^>]*JobUri[^>]*>([^<]+)</", text)]
    return ScannerStatus(state=state, adf_loaded=adf_loaded, active_job_uris=uris)


def _int(text: str | None) -> int | None:
    try:
        return int(text) if text is not None else None
    except ValueError:
        return None


def parse_scanner_capabilities(xml: bytes) -> ScannerCapabilities:
    """Tolerant parse of ScannerCapabilities. Everything is optional —
    vendors omit whole sections — so any missing field stays None/empty and
    the caller falls back to defaults."""
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise ValueError(f"ScannerCapabilities: invalid XML ({exc})") from exc

    def _max_region(caps_name: str) -> tuple[int, int] | None:
        el = _find_local(root, caps_name)
        if el is None:
            return None
        w = _int(_text(_find_local(el, "MaxWidth")))
        h = _int(_text(_find_local(el, "MaxHeight")))
        return (w, h) if w and h else None

    adf = _find_local(root, "Adf")
    adf_duplex = adf is not None and (
        _find_local(adf, "AdfDuplexInputCaps") is not None
        or any(
            _local(el.tag) == "AdfOption" and _text(el) == "Duplex"
            for el in adf.iter()
        )
    )
    resolutions: set[int] = set()
    for el in root.iter():
        if _local(el.tag) == "DiscreteResolution":
            x = _int(_text(_find_local(el, "XResolution")))
            if x:
                resolutions.add(x)
    color_modes: list[str] = []
    for el in root.iter():
        if _local(el.tag) == "ColorMode" and (t := _text(el)) and t not in color_modes:
            color_modes.append(t)
    return ScannerCapabilities(
        make_and_model=_text(_find_local(root, "MakeAndModel")),
        serial_number=_text(_find_local(root, "SerialNumber")),
        uuid=_text(_find_local(root, "UUID")),
        platen_max=_max_region("PlatenInputCaps"),
        adf_max=_max_region("AdfSimplexInputCaps") or _max_region("AdfDuplexInputCaps"),
        adf_duplex=adf_duplex,
        resolutions=sorted(resolutions),
        color_modes=color_modes,
    )


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
        ctx.set_ciphers("DEFAULT:@SECLEVEL=1")
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
        base_path: str = "eSCL",
    ) -> None:
        self._host = host
        self._port = port
        self._use_tls = use_tls
        self._user = user
        self._password = password
        self._verify_tls = verify_tls
        self._relaxed_ciphers = relaxed_ciphers
        self._default_timeout = aiohttp.ClientTimeout(total=timeout)
        scheme = "https" if use_tls else "http"
        port_suffix = "" if port in (80, 443) else f":{port}"
        self._origin = f"{scheme}://{host}{port_suffix}"
        self._base = f"{self._origin}/{base_path.strip('/')}"
        # Built once, lazily, and reused across every request — a fresh
        # session/connector/SSL context per call meant a TLS handshake and a
        # CA-bundle read on every 1.5s poll. Guarded so concurrent first-use
        # (driver + poll loop) can't build two sessions.
        self._ssl_ctx: ssl.SSLContext | None = None
        self._session_obj: aiohttp.ClientSession | None = None
        self._session_lock = asyncio.Lock()

    @property
    def host(self) -> str:
        return self._host

    @property
    def origin(self) -> str:
        return self._origin

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

    def _auth(self) -> aiohttp.BasicAuth | None:
        return (
            aiohttp.BasicAuth(self._user, self._password)
            if self._password
            else None
        )

    def _build_ssl(self) -> ssl.SSLContext:
        return _ssl_context(
            verify=self._verify_tls, relaxed_ciphers=self._relaxed_ciphers
        )

    async def _session(self) -> aiohttp.ClientSession:
        """Return the shared session, building it (and the SSL context) once.

        The default timeout is generous (create/scan). Callers that need a
        tighter bound (status/poll) or a stall-only bound (document streaming)
        pass a per-request `timeout=` to the individual .get()/.delete() call.
        """
        if self._session_obj is not None and not self._session_obj.closed:
            return self._session_obj
        async with self._session_lock:
            if self._session_obj is not None and not self._session_obj.closed:
                return self._session_obj
            if self._use_tls and self._ssl_ctx is None:
                # load_default_certs() can touch disk — build off the loop.
                loop = asyncio.get_running_loop()
                self._ssl_ctx = await loop.run_in_executor(None, self._build_ssl)
            connector = (
                aiohttp.TCPConnector(ssl=self._ssl_ctx)
                if self._use_tls
                else aiohttp.TCPConnector()
            )
            self._session_obj = aiohttp.ClientSession(
                connector=connector,
                timeout=self._default_timeout,
                auth=self._auth(),
            )
        return self._session_obj

    async def async_close(self) -> None:
        """Close the shared session. Called from coordinator shutdown."""
        if self._session_obj is not None and not self._session_obj.closed:
            await self._session_obj.close()
        self._session_obj = None

    # ── Status ──────────────────────────────────────────────────────────

    async def get_scanner_status(self) -> ScannerStatus:
        s = await self._session()
        async with s.get(
            f"{self._base}/ScannerStatus", timeout=_SHORT_TIMEOUT
        ) as resp:
            resp.raise_for_status()
            return parse_scanner_status(await resp.read())

    async def get_capabilities(self) -> ScannerCapabilities:
        s = await self._session()
        async with s.get(
            f"{self._base}/ScannerCapabilities", timeout=_SHORT_TIMEOUT
        ) as resp:
            resp.raise_for_status()
            return parse_scanner_capabilities(await resp.read())

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
        duplex: bool = False,
        document_format: str = "application/pdf",
        width: int = DEFAULT_REGION[0],
        height: int = DEFAULT_REGION[1],
    ) -> str:
        """Create a ScanJob; returns the job's absolute URL.

        Raises if the device returns a non-2xx status or omits the Location
        header. Tolerates the 503-while-a-stale-job-occupies-a-slot case by
        purging and retrying once — but only when the scanner reports Idle,
        so a job another client is actively running is never deleted.
        """
        body = _SCAN_SETTINGS_XML.format(
            source=source,
            dpi=dpi,
            color=_color_mode(color),
            format=document_format,
            width=width,
            height=height,
            duplex=_DUPLEX_XML if duplex else "",
        ).encode("utf-8")
        headers = {"Content-Type": "text/xml; charset=utf-8"}
        s = await self._session()

        async def _post() -> tuple[int, str | None, str | None]:
            # `async with` releases the response back to the shared session's
            # connection pool — required now that the session is long-lived.
            async with s.post(
                f"{self._base}/ScanJobs", data=body, headers=headers
            ) as r:
                loc = r.headers.get("Location")
                err = None if r.status in (200, 201) else (await r.text())[:200]
                return r.status, loc, err

        status, loc, err = await _post()
        if status == 503:
            # A device still winding down its previous/cancelled job reports
            # non-Idle briefly: wait for Idle. Then purge any stale job slots
            # (only ever done on an Idle device — a job on a busy device is
            # someone else's) and retry once. Still not Idle → truly busy.
            if not await self._wait_idle(s):
                raise RuntimeError("scanner busy (another job is active)")
            purged = await self._purge_active_jobs(s)
            _LOGGER.info(
                "eSCL ScanJobs returned 503; device idle again, purged %d stale job(s), retrying",
                purged,
            )
            status, loc, err = await _post()
        if status not in (200, 201):
            raise RuntimeError(f"scan create failed: {status} {err or ''}")
        if not loc:
            raise RuntimeError("scan create: no Location header")
        return self._absolute(loc)

    async def _wait_idle(self, session: aiohttp.ClientSession) -> bool:
        """Poll ScannerStatus until Idle or SCANNER_IDLE_WAIT_SECONDS elapse."""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + SCANNER_IDLE_WAIT_SECONDS
        while True:
            try:
                async with session.get(
                    f"{self._base}/ScannerStatus", timeout=_SHORT_TIMEOUT
                ) as resp:
                    if resp.status == 200 and parse_scanner_status(await resp.read()).is_idle:
                        return True
            except Exception as exc:  # noqa: BLE001 — keep polling until deadline
                _LOGGER.debug("ScannerStatus poll failed while waiting for idle: %s", exc)
            if loop.time() >= deadline:
                return False
            await asyncio.sleep(1.0)

    async def get_job_info(self, job_url: str) -> JobInfo | None:
        """Fetch JobInfo for an in-flight scan. Returns None on 404
        (job already cleaned up by device or never existed)."""
        s = await self._session()
        async with s.get(job_url, timeout=_SHORT_TIMEOUT) as resp:
            if resp.status == 404:
                return None
            resp.raise_for_status()
            return parse_job_info(await resp.read())

    async def iter_next_document(self, job_url: str) -> AsyncIterator[bytes]:
        """Stream one document from ScanJobs/{uuid}/NextDocument.

        Async-generates the body in chunks, then returns. Generates nothing
        (returns without yielding) when the scanner reports no more documents,
        so the caller distinguishes "empty/done" from "got a document" by
        whether any chunk arrived.

        Status code handling before the first chunk:
          * 404 / 410 — canonical "no more documents". Stop.
          * 503 — HP returns this in two contradictory ways:
                  (a) the document IS exhausted (signals "done")
                  (b) the next page is still being scanned ("retry me")
                Strategy: ask JobInfo. Job gone or terminal → done. Job still
                Pending/Processing → back off and retry, up to
                NEXT_DOCUMENT_RETRY_SECONDS (per-page ADF scanners can take
                several seconds per sheet).
          * 500 — sometimes transient. Same treatment.

        Once streaming has begun, a mid-transfer error propagates to the
        caller, which keeps the partial file and lets PDF validation decide.
        A sock_read timeout (not a total timeout) bounds stalls without
        capping large-but-healthy transfers.
        """
        s = await self._session()
        loop = asyncio.get_running_loop()
        deadline = loop.time() + NEXT_DOCUMENT_RETRY_SECONDS
        backoff = 0.5
        while True:
            async with s.get(
                f"{job_url}/NextDocument", timeout=_STREAM_TIMEOUT
            ) as resp:
                if resp.status in (404, 410):
                    return
                if resp.status not in (500, 503):
                    resp.raise_for_status()
                    async for chunk in resp.content.iter_chunked(_STREAM_CHUNK):
                        yield chunk
                    return
            if not await self._job_still_running(job_url) or loop.time() >= deadline:
                return
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 3.0)

    async def _job_still_running(self, job_url: str) -> bool:
        """True while JobInfo reports a non-terminal state. Probe failures
        count as "still running" so a flaky status endpoint doesn't truncate
        a batch; the caller's deadline bounds that."""
        try:
            info = await self.get_job_info(job_url)
        except Exception as exc:
            _LOGGER.debug("JobInfo probe during NextDocument retry failed: %s", exc)
            return True
        return info is not None and not info.is_terminal

    async def delete_job(self, job_url: str) -> bool:
        """Cancel a scan job. Returns True on 2xx, False otherwise.
        Treats 404 as success (already gone)."""
        s = await self._session()
        async with s.delete(job_url, timeout=_SHORT_TIMEOUT) as resp:
            if resp.status == 404:
                return True
            return 200 <= resp.status < 300

    async def purge_active_jobs(self) -> int:
        """Cancel every job the scanner is currently aware of. Returns
        the count of jobs purged. Best-effort — failures are swallowed."""
        return await self._purge_active_jobs(await self._session())

    async def _purge_active_jobs(self, session: aiohttp.ClientSession) -> int:
        try:
            async with session.get(
                f"{self._base}/ScannerStatus", timeout=_SHORT_TIMEOUT
            ) as resp:
                if resp.status != 200:
                    return 0
                status = parse_scanner_status(await resp.read())
        except Exception:
            return 0
        if not status.is_idle:
            # Jobs listed on a non-idle device belong to a live scan (possibly
            # another client's). Never delete those.
            return 0
        purged = 0
        for uri in status.active_job_uris:
            try:
                async with session.delete(
                    self._absolute(uri), timeout=_SHORT_TIMEOUT
                ) as r:
                    if 200 <= r.status < 300 or r.status == 404:
                        purged += 1
            except Exception:
                pass
        return purged
