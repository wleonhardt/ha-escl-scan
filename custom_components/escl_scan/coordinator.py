"""Per-scan eSCL progress tracker.

Drives the full scan lifecycle:
    create ScanJob → loop {poll JobInfo, pull NextDocument} → mark terminal

While the scan is active, polls JobInfo every POLL_INTERVAL seconds so
`pages_done` (server-side ImagesCompleted) updates in real time. Pulls
PDF chunks concurrently — eSCL servers serialize NextDocument calls,
so a single coroutine alternating poll + pull is sufficient.

Three observable surfaces:
* `ScanCoordinator.current` is the most-recently-active scan, mirrored
  to `sensor.printer_current_scan`.
* `escl_scan_state_changed` events fire on every observed state change.
* `escl_scan_completed` events fire once per terminal transition.
"""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
import logging
from pathlib import Path
import shutil
import time
from typing import Any
import uuid

from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN, EVENT_COMPLETED, EVENT_STATE_CHANGED
from .scanner import (
    DEFAULT_REGION,
    TERMINAL_JOB_STATES,
    JobInfo,
    ScannerCapabilities,
    ScannerClient,
)

_LOGGER = logging.getLogger(__name__)

POLL_INTERVAL = 1.5
TERMINAL_HOLD_SECONDS = 8.0

# Sensor states (lowercase kebab; mirror IPP integration's vocabulary).
STATE_IDLE = "idle"
STATE_PENDING = "pending"
STATE_PROCESSING = "processing"
STATE_PROCESSING_STOPPED = "processing-stopped"
STATE_COMPLETED = "completed"
STATE_CANCELED = "canceled"
STATE_ABORTED = "aborted"
STATE_FAILED = "failed"

# Map eSCL JobState → our state vocabulary.
_ESCL_STATE_MAP = {
    "Pending": STATE_PENDING,
    "Processing": STATE_PROCESSING,
    "ProcessingStopped": STATE_PROCESSING_STOPPED,
    "Completed": STATE_COMPLETED,
    "Canceled": STATE_CANCELED,
    "Cancelled": STATE_CANCELED,  # some vendors
    "Aborted": STATE_ABORTED,
}

_TERMINAL_STATES = {STATE_COMPLETED, STATE_CANCELED, STATE_ABORTED, STATE_FAILED}


class ScanBusyError(RuntimeError):
    """Raised by start_scan when a scan is already in progress."""


class _PdfFileWriter:
    """Streams scan bytes to a scratch file, capturing the head/tail needed
    for PDF validation without re-reading the file.

    All methods do blocking file I/O — call them via
    ``hass.async_add_executor_job``, never directly on the event loop.
    """

    def __init__(self, tmp_path: Path) -> None:
        self._tmp = tmp_path
        self._f: Any = None
        self.bytes_written = 0
        self.head = b""
        self.tail = b""

    @property
    def path(self) -> Path:
        return self._tmp

    def is_valid_pdf(self) -> bool:
        """The streamed bytes look like a complete PDF (header + EOF trailer)."""
        return self.head.startswith(b"%PDF-") and b"%%EOF" in self.tail

    def open(self) -> None:
        self._f = open(self._tmp, "wb")

    def write(self, chunk: bytes) -> None:
        self._f.write(chunk)
        self.bytes_written += len(chunk)
        if len(self.head) < 8:
            self.head = (self.head + chunk)[:8]
        self.tail = (self.tail + chunk)[-1024:]

    def close(self) -> None:
        if self._f is not None:
            try:
                self._f.close()
            finally:
                self._f = None

    def commit(self, final_path: Path) -> None:
        """Atomically move the scratch file into place (same filesystem)."""
        self._tmp.replace(final_path)

    def cleanup(self) -> None:
        try:
            self._tmp.unlink()
        except OSError:
            pass


def _safe_unlink(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        pass


def _copy_into(src: Path, directory: Path) -> Path:
    """Blocking: copy `src` into `directory` (created if missing), writing to
    a temp name first so a consumer watching the folder never sees a partial
    file. Returns the final path."""
    directory.mkdir(parents=True, exist_ok=True)
    dest = directory / src.name
    tmp = directory / f".{src.name}.tmp"
    shutil.copyfile(src, tmp)
    tmp.replace(dest)
    return dest


def _count_pdf_pages(path: Path) -> int | None:
    """Best-effort page count of a PDF. Returns None if pypdf is unavailable
    or the file won't parse — the caller keeps its document-based count."""
    try:
        from pypdf import PdfReader

        return len(PdfReader(str(path)).pages)
    except Exception:
        return None


def _merge_pdfs(parts: list[Path], dest: Path) -> tuple[int, int]:
    """Concatenate PDF `parts` into `dest`. Returns (page_count, byte_size).

    Blocking (pypdf is sync + CPU-bound) — call via an executor. pypdf is
    imported lazily so single-document scans never load it and a missing
    dependency only surfaces on the multi-document path.
    """
    from pypdf import PdfReader, PdfWriter

    writer = PdfWriter()
    pages = 0
    for part in parts:
        reader = PdfReader(str(part))
        for page in reader.pages:
            writer.add_page(page)
            pages += 1
    with open(dest, "wb") as fh:
        writer.write(fh)
    return pages, dest.stat().st_size


@dataclass
class TrackedScan:
    scan_id: str
    source: str
    dpi: int
    color: str
    submitted_at: datetime
    duplex: bool = False
    job_url: str | None = None
    state: str = STATE_PENDING
    state_reasons: str | None = None
    pages_done: int = 0
    filename: str | None = None
    file_path: Path | None = None
    copied_to: Path | None = None
    bytes_written: int = 0
    finished_at: datetime | None = None
    error: str | None = None
    last_seen: datetime = field(
        default_factory=lambda: datetime.now(UTC)
    )

    def is_terminal(self) -> bool:
        return self.state in _TERMINAL_STATES

    def to_dict(self) -> dict[str, Any]:
        return {
            "scan_id": self.scan_id,
            "source": self.source,
            "dpi": self.dpi,
            "color": self.color,
            "duplex": self.duplex,
            "state": self.state,
            "state_reasons": self.state_reasons,
            "pages_done": self.pages_done,
            "filename": self.filename,
            "bytes": self.bytes_written,
            "submitted_at": self.submitted_at.isoformat(),
            "finished_at": (
                self.finished_at.isoformat() if self.finished_at else None
            ),
            "error": self.error,
            "file_path": (
                str(self.file_path) if self.state == STATE_COMPLETED else None
            ),
            "copied_to": str(self.copied_to) if self.copied_to else None,
            "file_url": (
                f"/api/escl_scan/file/{self.scan_id}" if self.state == STATE_COMPLETED else None
            ),
        }


class ScanCoordinator:
    """Drives scan jobs and mirrors state into HA."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: ScannerClient,
        *,
        storage_dir: Path,
        default_dpi: int,
        default_color: str,
        default_duplex: bool = False,
        file_ttl_seconds: int,
        copy_dir: Path | None = None,
    ) -> None:
        self._hass = hass
        self._client = client
        self._storage = storage_dir
        self._default_dpi = default_dpi
        self._default_color = default_color
        self._default_duplex = default_duplex
        self._file_ttl = file_ttl_seconds
        self._copy_dir = copy_dir
        self._caps: ScannerCapabilities | None = None
        self._scans: dict[str, TrackedScan] = {}
        self._current: TrackedScan | None = None
        self._driver_tasks: dict[str, asyncio.Task] = {}
        self._hold_tasks: set[asyncio.Task] = set()
        self._update_listeners: list[Callable[[], None]] = []
        self._starting = False
        self._shutting_down = False
        # `storage` directory is created lazily on first scan (inside an
        # executor) so the integration's async_setup_entry never blocks.

    @property
    def current(self) -> TrackedScan | None:
        return self._current

    @property
    def host(self) -> str:
        return self._client.host

    @property
    def origin(self) -> str:
        return self._client.origin

    @property
    def capabilities(self) -> ScannerCapabilities | None:
        return self._caps

    def device_info(self, entry_id: str) -> DeviceInfo:
        """One device for all entities. Make/model/serial come from
        ScannerCapabilities when the device serves it."""
        caps = self._caps
        model = caps.make_and_model if caps else None
        # "HP LaserJet MFP M234sdw" -> manufacturer "HP", model the rest.
        manufacturer, _, rest = (model or "").partition(" ")
        return DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name=model or f"eSCL scanner ({self.host})",
            manufacturer=manufacturer or "eSCL / AirScan",
            model=rest or None,
            serial_number=caps.serial_number if caps else None,
            configuration_url=f"{self.origin}/",
        )

    async def async_refresh_capabilities(self) -> ScannerCapabilities | None:
        """Fetch ScannerCapabilities once (cached). Best-effort: a device
        that doesn't serve it just leaves us on the built-in defaults."""
        if self._caps is None:
            try:
                self._caps = await self._client.get_capabilities()
            except Exception as exc:
                _LOGGER.debug("ScannerCapabilities unavailable: %s", exc)
        return self._caps

    def get(self, scan_id: str) -> TrackedScan | None:
        return self._scans.get(scan_id)

    def register_update_listener(self, cb: Callable[[], None]) -> Callable[[], None]:
        self._update_listeners.append(cb)

        def _unsub() -> None:
            try:
                self._update_listeners.remove(cb)
            except ValueError:
                pass

        return _unsub

    def _notify(self) -> None:
        for cb in list(self._update_listeners):
            try:
                cb()
            except Exception:
                _LOGGER.exception("update listener raised")

    # ── Public surface ──────────────────────────────────────────────────

    async def start_scan(
        self,
        *,
        source: str | None = None,
        dpi: int | None = None,
        color: str | None = None,
        duplex: bool | None = None,
    ) -> TrackedScan:
        """Kick off a scan. Returns the tracked scan immediately; the
        driver task assembles pages in the background.

        Raises ScanBusyError if a scan is already in progress — the scanner
        is single-job hardware and a second create would 503 and purge the
        running job."""
        if self._starting or (
            self._current is not None and not self._current.is_terminal()
        ):
            raise ScanBusyError("a scan is already in progress")

        # Reserve synchronously so a second request can't slip past the guard
        # during the detect_source() network round-trip below.
        self._starting = True
        try:
            caps = await self.async_refresh_capabilities()
            actual_source = source or await self._client.detect_source()
            actual_dpi = dpi or self._default_dpi
            if caps is not None and (snapped := caps.snap_dpi(actual_dpi)) != actual_dpi:
                _LOGGER.info(
                    "scanner has no %d dpi mode; using nearest supported %d dpi",
                    actual_dpi, snapped,
                )
                actual_dpi = snapped
            actual_color = color or self._default_color
            want_duplex = self._default_duplex if duplex is None else duplex
            actual_duplex = (
                want_duplex
                and actual_source == "Feeder"
                and (caps is None or caps.adf_duplex)
            )

            scan_id = uuid.uuid4().hex[:12]
            scan = TrackedScan(
                scan_id=scan_id,
                source=actual_source,
                dpi=actual_dpi,
                color=actual_color,
                duplex=actual_duplex,
                submitted_at=datetime.now(UTC),
            )
            self._scans[scan_id] = scan
            self._current = scan
        finally:
            self._starting = False
        self._fire(EVENT_STATE_CHANGED, scan)
        self._notify()

        deleted = await self._hass.async_add_executor_job(
            self._ensure_storage_and_purge
        )
        self._reap_tracked(deleted)
        self._driver_tasks[scan_id] = self._hass.loop.create_task(
            self._drive_scan(scan)
        )
        _LOGGER.info(
            "started scan %s (source=%s dpi=%s color=%s duplex=%s)",
            scan_id, actual_source, actual_dpi, actual_color, actual_duplex,
        )
        return scan

    async def async_cancel(self, scan_id: str) -> bool:
        scan = self._scans.get(scan_id)
        if scan is None or scan.is_terminal():
            return False
        # Best-effort device-side delete; if the scan hasn't gotten its
        # job_url yet (still in `pending`), skip it. The local cancel
        # below is what guarantees the UI/sensor flips to canceled.
        if scan.job_url:
            try:
                await self._client.delete_job(scan.job_url)
            except Exception as exc:
                _LOGGER.warning("delete_job for %s failed: %s", scan_id, exc)
        # The driver task will observe the cancel via JobInfo or NextDocument
        # returning 404; mark optimistically here so the UI updates fast.
        self._mark_terminal(scan, STATE_CANCELED, "user-cancel", error=None)
        return True

    async def async_shutdown(self) -> None:
        """Cancel every in-flight task and await it. Call on entry unload/reload
        so a scan-in-progress driver doesn't keep polling a stale client,
        writing files, or notifying a removed sensor."""
        self._shutting_down = True
        tasks = list(self._driver_tasks.values()) + list(self._hold_tasks)
        for t in tasks:
            t.cancel()
        for t in tasks:
            try:
                await t
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        self._driver_tasks.clear()
        self._hold_tasks.clear()
        try:
            await self._client.async_close()
        except Exception:  # noqa: BLE001
            _LOGGER.debug("client close during shutdown failed", exc_info=True)

    # ── Driver ──────────────────────────────────────────────────────────

    async def _drive_scan(self, scan: TrackedScan) -> None:
        """Foreground orchestration of a single scan job."""
        try:
            region = (
                self._caps.region_for(scan.source) if self._caps else DEFAULT_REGION
            )
            try:
                scan.job_url = await self._client.create_job(
                    source=scan.source,
                    dpi=scan.dpi,
                    color=scan.color,
                    duplex=scan.duplex,
                    width=region[0],
                    height=region[1],
                )
            except Exception as exc:
                self._mark_terminal(scan, STATE_FAILED, None, error=str(exc))
                return

            scan.state = STATE_PROCESSING
            self._fire(EVENT_STATE_CHANGED, scan)
            self._notify()

            ts = time.strftime("%Y%m%d-%H%M%S")
            scan.filename = f"scan-{ts}-{scan.source.lower()}-{scan.scan_id}.pdf"
            scan.file_path = self._storage / scan.filename

            parts = await self._stream_documents(scan)

            if scan.is_terminal():
                # Coordinator cancel beat us to it.
                for writer in parts:
                    await self._hass.async_add_executor_job(writer.cleanup)
                return

            # Validate + assemble; marks the scan failed itself on error.
            if not await self._assemble_result(scan, parts):
                return

            # Optional "scan to folder" (e.g. a Paperless consume dir). A
            # failed copy never fails the scan — the file is still served.
            if self._copy_dir is not None:
                try:
                    scan.copied_to = await self._hass.async_add_executor_job(
                        _copy_into, scan.file_path, self._copy_dir
                    )
                except Exception as exc:  # noqa: BLE001
                    _LOGGER.warning(
                        "scan %s: copy to %s failed: %s", scan.scan_id, self._copy_dir, exc
                    )

            # Final JobInfo sanity check — if scanner reports Aborted, honour it.
            final_state = STATE_COMPLETED
            final_reasons: str | None = None
            try:
                info = await self._client.get_job_info(scan.job_url)
                if info and info.state in TERMINAL_JOB_STATES:
                    final_state = _ESCL_STATE_MAP.get(info.state, STATE_COMPLETED)
                    final_reasons = info.state_reasons
                # Single-document scanners report the page count only
                # server-side; take the higher so completed scans don't
                # under-report pages if the poll loop was cancelled early.
                if info and info.pages_completed and info.pages_completed > scan.pages_done:
                    scan.pages_done = info.pages_completed
            except Exception:
                pass

            self._mark_terminal(scan, final_state, final_reasons, error=None)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            _LOGGER.exception("scan driver crashed")
            self._mark_terminal(scan, STATE_FAILED, None, error=str(exc))
        finally:
            # Always best-effort delete the server-side job, including on
            # failure paths. eSCL devices have a limited number of job slots
            # and won't accept new ScanJobs until stale ones are deleted.
            # Skip during shutdown — the task is being cancelled and the
            # client session is about to close.
            if scan.job_url and not self._shutting_down:
                try:
                    await self._client.delete_job(scan.job_url)
                except Exception as exc:
                    _LOGGER.debug(
                        "post-terminal delete_job for %s: %s",
                        scan.scan_id, exc,
                    )
            self._driver_tasks.pop(scan.scan_id, None)
            if not self._shutting_down:
                hold = self._hass.loop.create_task(self._terminal_hold(scan))
                self._hold_tasks.add(hold)
                hold.add_done_callback(self._hold_tasks.discard)

    async def _stream_documents(self, scan: TrackedScan) -> list[_PdfFileWriter]:
        """Pull every document the scanner produces, each streamed straight to
        its own scratch file (never buffer a whole PDF in RAM — a 600-DPI
        colour ADF batch can be hundreds of MB). Returns the closed writers,
        one per document received. Runs the JobInfo poll loop alongside.

        Some scanners bundle the whole batch into a single document; others
        return one document per page. Both are handled here; concatenation
        happens in _assemble_result.
        """
        parts: list[_PdfFileWriter] = []
        poll_task = self._hass.loop.create_task(self._poll_loop(scan))
        try:
            doc_index = 0
            while not scan.is_terminal():
                writer = _PdfFileWriter(
                    scan.file_path.with_name(f"{scan.file_path.name}.part{doc_index}")
                )
                try:
                    await self._hass.async_add_executor_job(writer.open)
                except OSError as exc:
                    _LOGGER.warning(
                        "scan %s: cannot open scratch file: %s", scan.scan_id, exc
                    )
                    break
                got_data = False
                try:
                    async for chunk in self._client.iter_next_document(scan.job_url):
                        got_data = True
                        await self._hass.async_add_executor_job(writer.write, chunk)
                except Exception as exc:
                    # Mid-stream error: keep the partial (validation decides).
                    _LOGGER.warning(
                        "scan %s: document stream errored after %d page(s): "
                        "%s — using what we have",
                        scan.scan_id, scan.pages_done, exc,
                    )
                    await self._hass.async_add_executor_job(writer.close)
                    if got_data:
                        parts.append(writer)
                    else:
                        await self._hass.async_add_executor_job(writer.cleanup)
                    break
                await self._hass.async_add_executor_job(writer.close)
                if not got_data:
                    await self._hass.async_add_executor_job(writer.cleanup)
                    break
                parts.append(writer)
                doc_index += 1
                scan.pages_done += 1
                scan.last_seen = datetime.now(UTC)
                self._fire(EVENT_STATE_CHANGED, scan)
                self._notify()
        finally:
            poll_task.cancel()
            try:
                await poll_task
            except (asyncio.CancelledError, Exception):
                pass
        return parts

    async def _assemble_result(
        self, scan: TrackedScan, parts: list[_PdfFileWriter]
    ) -> bool:
        """Validate the streamed parts and produce scan.file_path.

        Returns True if a usable PDF was written (the scan may proceed to
        completed), or False after marking the scan failed. Always cleans up
        the scratch parts. A single valid document is renamed into place (fast
        path, no pypdf); multiple are concatenated with pypdf.
        """
        if not parts:
            self._mark_terminal(
                scan, STATE_FAILED, None, error="no document returned from scanner"
            )
            return False

        # "Valid" = looks like a complete PDF. HP MFPs occasionally hand back a
        # truncated catalog header (~58 bytes) for an unsupported DPI/colour
        # combo without a 4xx/5xx; the EOF check turns that into a clear
        # failure rather than a "completed" claim on a broken file.
        valid = [w for w in parts if w.is_valid_pdf()]
        if not valid:
            first = parts[0]
            for w in parts:
                await self._hass.async_add_executor_job(w.cleanup)
            if not first.head.startswith(b"%PDF-"):
                err = f"scanner returned a non-PDF response ({first.bytes_written} bytes)"
            else:
                err = (
                    f"scanner returned a truncated PDF ({first.bytes_written} bytes; "
                    f"no EOF trailer). This usually means the requested DPI/color "
                    f"combo isn't supported by the device."
                )
            self._mark_terminal(scan, STATE_FAILED, None, error=err)
            return False

        dropped = len(parts) - len(valid)
        if dropped:
            _LOGGER.warning(
                "scan %s: dropped %d incomplete document part(s)",
                scan.scan_id, dropped,
            )

        consumed: set[Path] = set()
        try:
            if len(valid) == 1:
                await self._hass.async_add_executor_job(valid[0].commit, scan.file_path)
                scan.bytes_written = valid[0].bytes_written
                consumed = {valid[0].path}
                # Bundle-mode scanners pack the whole ADF batch into one
                # document, so the document count (1) understates the pages.
                # Count the real pages so the sensor/card don't report "1 page"
                # for an N-page scan.
                pages = await self._hass.async_add_executor_job(
                    _count_pdf_pages, scan.file_path
                )
                if pages:
                    scan.pages_done = max(scan.pages_done, pages)
            else:
                pages, size = await self._hass.async_add_executor_job(
                    _merge_pdfs, [w.path for w in valid], scan.file_path
                )
                scan.bytes_written = size
                scan.pages_done = max(scan.pages_done, pages)
                _LOGGER.info(
                    "scan %s: merged %d documents into a %d-page PDF",
                    scan.scan_id, len(valid), pages,
                )
        except Exception as exc:
            for w in parts:
                await self._hass.async_add_executor_job(w.cleanup)
            await self._hass.async_add_executor_job(_safe_unlink, scan.file_path)
            self._mark_terminal(
                scan, STATE_FAILED, None, error=f"could not assemble PDF: {exc}"
            )
            return False

        for w in parts:
            if w.path not in consumed:
                await self._hass.async_add_executor_job(w.cleanup)
        return True

    async def _poll_loop(self, scan: TrackedScan) -> None:
        """Poll JobInfo while the scan is in flight. Updates pages_done
        from server-side counter when the scanner reports it (which is
        usually faster than waiting for NextDocument to return)."""
        if not scan.job_url:
            return
        try:
            while not scan.is_terminal():
                await asyncio.sleep(POLL_INTERVAL)
                try:
                    info: JobInfo | None = await self._client.get_job_info(
                        scan.job_url
                    )
                except Exception as exc:
                    _LOGGER.debug(
                        "JobInfo poll for %s failed: %s", scan.scan_id, exc
                    )
                    continue
                if info is None:
                    continue
                changed = False
                if info.state_reasons and info.state_reasons != scan.state_reasons:
                    scan.state_reasons = info.state_reasons
                    changed = True
                if info.pages_completed is not None:
                    # Scanner's counter races with our local pages_done
                    # (incremented after each NextDocument pull). Take the
                    # higher of the two so the UI never goes backwards.
                    if info.pages_completed > scan.pages_done:
                        scan.pages_done = info.pages_completed
                        changed = True
                if changed:
                    self._notify()
        except asyncio.CancelledError:
            raise

    async def _terminal_hold(self, scan: TrackedScan) -> None:
        """Keep a finished scan as `current` for a short hold, so the
        dashboard shows the success/error message instead of snapping
        back to idle the instant the driver finishes."""
        await asyncio.sleep(TERMINAL_HOLD_SECONDS)
        if self._current and self._current.scan_id == scan.scan_id:
            self._current = None
            self._notify()

    def _mark_terminal(
        self,
        scan: TrackedScan,
        state: str,
        reasons: str | None,
        *,
        error: str | None,
    ) -> None:
        if scan.is_terminal():
            return
        scan.state = state
        scan.state_reasons = reasons
        scan.error = error
        scan.finished_at = datetime.now(UTC)
        _LOGGER.info(
            "scan %s reached terminal state %s (%s)",
            scan.scan_id, state, reasons or error or "no reason",
        )
        self._fire(EVENT_STATE_CHANGED, scan)
        self._fire(EVENT_COMPLETED, scan)
        self._notify()

    def _fire(self, event: str, scan: TrackedScan) -> None:
        self._hass.bus.async_fire(event, scan.to_dict())

    # ── File retention ──────────────────────────────────────────────────

    def _ensure_storage_and_purge(self) -> set[Path]:
        """Executor-safe: create storage dir if missing, then purge TTLed
        files. Returns the set of deleted paths so the caller can reconcile
        the tracked-scan dict on the event loop (this runs off-loop and must
        not mutate coordinator state itself)."""
        try:
            self._storage.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            _LOGGER.warning("could not create scan storage dir: %s", exc)
        return self._purge_expired_files()

    def _purge_expired_files(self) -> set[Path]:
        """Delete scan files older than the TTL, plus any leftover ``.part``
        scratch files from a scan that died mid-write. Executor-safe: touches
        disk only, returns the completed paths removed. Safe to nuke every
        ``.part`` because the busy guard means no scan is writing when this
        runs at the start of a new scan."""
        deleted: set[Path] = set()
        cutoff = time.time() - self._file_ttl
        try:
            for f in self._storage.glob("scan-*.pdf"):
                if f.is_file() and f.stat().st_mtime < cutoff:
                    try:
                        f.unlink()
                        deleted.add(f)
                    except OSError:
                        pass
            for part in self._storage.glob("scan-*.pdf.part*"):
                try:
                    part.unlink()
                except OSError:
                    pass
        except OSError:
            pass
        return deleted

    async def async_purge_now(self, now: Any = None) -> None:
        """TTL sweep, also driven by a periodic timer (see async_setup_entry).
        Without it, files from infrequent scans outlive their TTL indefinitely
        because the only other purge is at the start of the next scan. Skips
        while a scan is active so it never races the writer."""
        if self._starting or (
            self._current is not None and not self._current.is_terminal()
        ):
            return
        deleted = await self._hass.async_add_executor_job(
            self._ensure_storage_and_purge
        )
        self._reap_tracked(deleted)

    def _reap_tracked(self, deleted: set[Path]) -> None:
        """Drop tracked entries whose files were just TTL-purged, plus any
        terminal scan (failed/canceled ones never had a file) older than the
        TTL. Runs on the event loop — safe to mutate `self._scans` here."""
        cutoff = datetime.now(UTC) - timedelta(seconds=self._file_ttl)
        for scan_id in list(self._scans):
            s = self._scans[scan_id]
            if not s.is_terminal() or s is self._current:
                continue
            expired = s.finished_at is not None and s.finished_at < cutoff
            if s.file_path in deleted or expired:
                self._scans.pop(scan_id, None)
