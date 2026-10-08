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
CAPABILITIES_RETRY_SECONDS = 300.0
MANUAL_RELOAD_TIMEOUT_SECONDS = 900.0

# Sensor states (lowercase kebab; mirror IPP integration's vocabulary).
STATE_IDLE = "idle"
STATE_PENDING = "pending"
STATE_PROCESSING = "processing"
STATE_PROCESSING_STOPPED = "processing-stopped"
STATE_AWAITING_BACKS = "awaiting-back-sides"
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
        self.close()
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
    try:
        shutil.copyfile(src, tmp)
        tmp.replace(dest)
    finally:
        tmp.unlink(missing_ok=True)
    return dest


def _count_pdf_pages(path: Path) -> int:
    """Read the page tree from disk; reject unreadable or empty PDFs."""
    from pypdf import PdfReader

    with path.open("rb") as stream:
        pages = len(PdfReader(stream).pages)
    if not pages:
        raise ValueError("scanner returned a PDF with no pages")
    return pages


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
        with part.open("rb") as stream:
            reader = PdfReader(stream)
            if not reader.pages:
                raise ValueError("scanner returned a PDF with no pages")
            for page in reader.pages:
                writer.add_page(page)
                pages += 1
    with open(dest, "wb") as fh:
        writer.write(fh)
    return pages, dest.stat().st_size


def _rotate_back_sides(path: Path) -> int:
    """Rotate odd (0-based) pages of the PDF at `path` by 180° in place.

    Blocking — call via an executor. Writes a sibling temp file and renames
    it over `path`, so a failure leaves the original intact.
    """
    from pypdf import PdfReader, PdfWriter

    tmp = path.with_name(path.name + ".rot")
    try:
        with path.open("rb") as stream:
            writer = PdfWriter(clone_from=PdfReader(stream))
            for i, page in enumerate(writer.pages):
                if i % 2:
                    page.rotate(180)
            with open(tmp, "wb") as fh:
                writer.write(fh)
        tmp.replace(path)
        return path.stat().st_size
    finally:
        tmp.unlink(missing_ok=True)


def _interleave_duplex(fronts: Path, backs: Path, rotate_backs: bool) -> tuple[int, int]:
    """Atomically replace the backs PDF with paired front/back pages."""
    from pypdf import PdfReader, PdfWriter

    tmp = backs.with_name(backs.name + ".duplex")
    try:
        with fronts.open("rb") as front_stream, backs.open("rb") as back_stream:
            front_reader = PdfReader(front_stream)
            back_reader = PdfReader(back_stream)
            if len(front_reader.pages) != len(back_reader.pages):
                raise ValueError(
                    f"page count mismatch: {len(front_reader.pages)} fronts, "
                    f"{len(back_reader.pages)} backs; reload every sheet in the same order"
                )
            writer = PdfWriter()
            if front_reader.metadata:
                writer.add_metadata(front_reader.metadata)
            for front, back in zip(front_reader.pages, back_reader.pages, strict=True):
                writer.add_page(front)
                copied_back = writer.add_page(back)
                if rotate_backs:
                    copied_back.rotate(180)
            with tmp.open("wb") as output:
                writer.write(output)
            pages = len(writer.pages)
        tmp.replace(backs)
        return pages, backs.stat().st_size
    finally:
        tmp.unlink(missing_ok=True)


@dataclass
class TrackedScan:
    scan_id: str
    source: str
    dpi: int
    color: str
    submitted_at: datetime
    duplex: bool = False
    duplex_mode: str = "simplex"
    scan_phase: str | None = None
    front_pages: int = 0
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
    publishing: bool = False
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
            "duplex_mode": self.duplex_mode,
            "scan_phase": self.scan_phase,
            "front_pages": self.front_pages,
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
        rotate_duplex_backs: bool = False,
        file_ttl_seconds: int,
        copy_dir: Path | None = None,
    ) -> None:
        self._hass = hass
        self._client = client
        self._storage = storage_dir
        self._default_dpi = default_dpi
        self._default_color = default_color
        self._default_duplex = default_duplex
        self._rotate_duplex_backs = rotate_duplex_backs
        self._file_ttl = file_ttl_seconds
        self._copy_dir = copy_dir
        self._caps: ScannerCapabilities | None = None
        self._caps_retry_at = 0.0
        self._scans: dict[str, TrackedScan] = {}
        self._current: TrackedScan | None = None
        self._driver_tasks: dict[str, asyncio.Task] = {}
        self._back_events: dict[str, asyncio.Event] = {}
        self._back_resuming: set[str] = set()
        self._hold_tasks: set[asyncio.Task] = set()
        self._purge_tasks: set[asyncio.Task] = set()
        self._update_listeners: list[Callable[[], None]] = []
        self._starting = False
        self._starting_task: asyncio.Task | None = None
        self._storage_lock = asyncio.Lock()
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
        """Cache capabilities; back off unavailable endpoints for five minutes
        without losing the chance to recover from a transient probe failure."""
        if self._caps is None and self._hass.loop.time() >= self._caps_retry_at:
            try:
                self._caps = await self._client.get_capabilities()
            except Exception as exc:
                _LOGGER.debug("ScannerCapabilities unavailable: %s", exc)
                self._caps_retry_at = self._hass.loop.time() + CAPABILITIES_RETRY_SECONDS
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
        if self._shutting_down:
            raise ScanBusyError("scanner integration is shutting down")
        if self._starting or self._driver_tasks or (
            self._current is not None and not self._current.is_terminal()
        ):
            raise ScanBusyError("a scan is already in progress")

        # Reserve synchronously so a second request can't slip past the guard
        # during the detect_source() network round-trip below.
        self._starting = True
        self._starting_task = asyncio.current_task()
        try:
            caps = await self.async_refresh_capabilities()
            actual_source = source or await self._client.detect_source()
            actual_dpi = dpi or self._default_dpi
            actual_color = color or self._default_color
            want_duplex = self._default_duplex if duplex is None else duplex
            actual_duplex = (
                want_duplex
                and actual_source == "Feeder"
                and caps is not None and caps.adf_duplex
            )
            manual_duplex = want_duplex and actual_source == "Feeder" and not actual_duplex
            if caps is not None and (
                snapped := caps.snap_dpi(actual_dpi, actual_source, actual_duplex)
            ) != actual_dpi:
                _LOGGER.info(
                    "scanner has no %d dpi mode; using nearest supported %d dpi",
                    actual_dpi, snapped,
                )
                actual_dpi = snapped

            scan_id = uuid.uuid4().hex[:12]
            scan = TrackedScan(
                scan_id=scan_id,
                source=actual_source,
                dpi=actual_dpi,
                color=actual_color,
                duplex=actual_duplex,
                duplex_mode="manual" if manual_duplex else (
                    "automatic" if actual_duplex else "simplex"
                ),
                scan_phase="fronts" if manual_duplex else None,
                submitted_at=datetime.now(UTC),
            )
            self._scans[scan_id] = scan
            self._current = scan
        finally:
            self._starting = False
            self._starting_task = None
        self._fire(EVENT_STATE_CHANGED, scan)
        self._notify()

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
        if scan is None or scan.is_terminal() or scan.publishing:
            return False
        # Mark before awaiting anything: completion must not beat a cancel
        # while DELETE is in flight. The driver owns device/file cleanup.
        waiting_for_backs = scan.state == STATE_AWAITING_BACKS
        self._mark_terminal(scan, STATE_CANCELED, "user-cancel", error=None)
        task = self._driver_tasks.get(scan_id)
        if task is not None and (scan.job_url or waiting_for_backs):
            task.cancel()
        # During create_job, let the POST finish so its Location is known
        # and the driver can delete exactly the job we created.
        return True

    async def async_scan_backs(self, scan_id: str) -> TrackedScan:
        """Resume only after the user has reloaded the back sides."""
        scan = self._scans.get(scan_id)
        event = self._back_events.get(scan_id)
        if self._shutting_down or scan is None or scan.state != STATE_AWAITING_BACKS:
            raise ValueError("scan is not waiting for back sides")
        if event is None or scan_id in self._back_resuming:
            raise ValueError("back-side scan is already starting")
        self._back_resuming.add(scan_id)
        try:
            status = await self._client.get_scanner_status()
            if not status.is_idle or not status.adf_loaded:
                raise ValueError("load the back sides into the idle feeder first")
            if (
                scan.is_terminal() or self._shutting_down
                or self._back_events.get(scan_id) is not event
            ):
                raise ValueError("scan is no longer waiting for back sides")
            scan.scan_phase = "backs"
            scan.state = STATE_PENDING
            scan.state_reasons = None
            self._fire(EVENT_STATE_CHANGED, scan)
            self._notify()
            event.set()
            return scan
        finally:
            self._back_resuming.discard(scan_id)

    async def async_shutdown(self) -> None:
        """Cancel every in-flight task and await it. Call on entry unload/reload
        so a scan-in-progress driver doesn't keep polling a stale client,
        writing files, or notifying a removed sensor."""
        self._shutting_down = True
        tasks = (
            list(self._driver_tasks.values()) + list(self._hold_tasks) + list(self._purge_tasks)
        )
        if self._starting_task is not None:
            tasks.append(self._starting_task)
        for t in tasks:
            if not t.cancelling():
                t.cancel()
        for t in tasks:
            try:
                await t
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        self._driver_tasks.clear()
        self._hold_tasks.clear()
        self._purge_tasks.clear()
        try:
            await self._client.async_close()
        except Exception:  # noqa: BLE001
            _LOGGER.debug("client close during shutdown failed", exc_info=True)

    # ── Driver ──────────────────────────────────────────────────────────

    async def _file_job(self, func: Callable, *args: Any) -> Any:
        """Finish executor I/O before cancellation allows file cleanup.

        Canceling an await doesn't stop its worker thread. Without shielding,
        cleanup can race an open/write/rename still running in that thread.
        """
        job = self._hass.async_add_executor_job(func, *args)
        try:
            return await asyncio.shield(job)
        except asyncio.CancelledError:
            try:
                await job
            except Exception:
                _LOGGER.debug("file operation failed during cancellation", exc_info=True)
            raise

    async def _create_device_job(self, scan: TrackedScan) -> None:
        """Recover the created job's address even if shutdown interrupts POST."""
        region = self._caps.region_for(scan.source, scan.duplex) if self._caps else DEFAULT_REGION
        create = self._hass.loop.create_task(self._client.create_job(
            source=scan.source, dpi=scan.dpi, color=scan.color, duplex=scan.duplex,
            width=region[0], height=region[1],
        ))
        try:
            scan.job_url = await asyncio.shield(create)
        except asyncio.CancelledError:
            try:
                scan.job_url = await create
            except Exception:
                _LOGGER.debug("job creation failed during shutdown", exc_info=True)
            raise

    async def _drive_scan(self, scan: TrackedScan) -> None:
        """Foreground orchestration of a single scan job."""
        parts: list[_PdfFileWriter] = []
        try:
            async with self._storage_lock:
                deleted = await self._file_job(self._ensure_storage_and_purge)
                self._reap_tracked(deleted)
            if scan.is_terminal():
                return
            try:
                await self._create_device_job(scan)
            except Exception as exc:
                self._mark_terminal(scan, STATE_FAILED, None, error=str(exc))
                return

            if scan.is_terminal():
                return
            scan.state = STATE_PROCESSING
            self._fire(EVENT_STATE_CHANGED, scan)
            self._notify()

            ts = time.strftime("%Y%m%d-%H%M%S")
            scan.filename = f"scan-{ts}-{scan.source.lower()}-{scan.scan_id}.pdf"
            scan.file_path = self._storage / scan.filename

            parts = await self._stream_documents(scan)

            if scan.is_terminal():
                return

            # Validate + assemble; marks the scan failed itself on error.
            pdf_pages = await self._assemble_result(scan, parts)
            if pdf_pages is None:
                return

            if scan.duplex_mode == "manual":
                if not await self._scan_manual_backs(scan, pdf_pages):
                    return

            # Final JobInfo sanity check — if scanner reports Aborted, honour it.
            final_state = STATE_COMPLETED
            final_reasons: str | None = None
            try:
                info = await self._client.get_job_info(scan.job_url)
                if info and info.state in TERMINAL_JOB_STATES:
                    final_state = _ESCL_STATE_MAP.get(info.state, STATE_COMPLETED)
                    final_reasons = info.state_reasons
            except Exception:
                pass

            if scan.is_terminal():
                return
            # Publish to a watched folder only after the device's final state
            # confirms success. Aborted/canceled batches must not be consumed.
            if self._copy_dir is not None and final_state == STATE_COMPLETED:
                # This is the commit point: once publication begins a folder
                # consumer may ingest the file, so cancellation is too late.
                scan.publishing = True
                try:
                    scan.copied_to = await self._file_job(
                        _copy_into, scan.file_path, self._copy_dir
                    )
                except Exception as exc:
                    _LOGGER.warning(
                        "scan %s: copy to %s failed: %s", scan.scan_id, self._copy_dir, exc
                    )
            self._mark_terminal(scan, final_state, final_reasons, error=None)
        except asyncio.CancelledError:
            if not scan.is_terminal():
                raise
        except Exception as exc:
            _LOGGER.exception("scan driver crashed")
            self._mark_terminal(scan, STATE_FAILED, None, error=str(exc))
        finally:
            # Always best-effort delete the server-side job, including on
            # failure paths. eSCL devices have a limited number of job slots
            # and won't accept new ScanJobs until stale ones are deleted.
            if scan.job_url:
                try:
                    await self._client.delete_job(scan.job_url)
                except Exception as exc:
                    _LOGGER.debug(
                        "post-terminal delete_job for %s: %s",
                        scan.scan_id, exc,
                    )
            for writer in parts:
                await self._file_job(writer.cleanup)
            if scan.file_path is not None and scan.state != STATE_COMPLETED:
                await self._file_job(_safe_unlink, scan.file_path)
            self._driver_tasks.pop(scan.scan_id, None)
            if not self._shutting_down:
                hold = self._hass.loop.create_task(self._terminal_hold(scan))
                self._hold_tasks.add(hold)
                hold.add_done_callback(self._hold_tasks.discard)

    async def _scan_manual_backs(self, scan: TrackedScan, front_pages: int) -> bool:
        """Keep the validated fronts private while awaiting the second pass."""
        info = await self._client.get_job_info(scan.job_url)
        if info and info.state in {"Canceled", "Cancelled", "Aborted"}:
            self._mark_terminal(scan, _ESCL_STATE_MAP[info.state], info.state_reasons, error=None)
            return False
        fronts = scan.file_path.with_name(scan.file_path.name + ".fronts")
        back_parts: list[_PdfFileWriter] = []
        try:
            await self._file_job(scan.file_path.replace, fronts)
            if scan.is_terminal():
                return False
            if not await self._client.delete_job(scan.job_url):
                raise RuntimeError("could not release the front-side scanner job")
            scan.job_url = None
            if scan.is_terminal():
                return False
            scan.front_pages = front_pages
            scan.bytes_written = 0
            event = asyncio.Event()
            self._back_events[scan.scan_id] = event
            scan.scan_phase = "waiting-for-backs"
            scan.state = STATE_AWAITING_BACKS
            scan.state_reasons = None
            self._fire(EVENT_STATE_CHANGED, scan)
            self._notify()
            try:
                await asyncio.wait_for(event.wait(), timeout=MANUAL_RELOAD_TIMEOUT_SECONDS)
            except TimeoutError as exc:
                raise RuntimeError("timed out waiting for back sides (15 minutes)") from exc
            if scan.is_terminal():
                return False
            await self._create_device_job(scan)
            if scan.is_terminal():
                return False
            scan.state = STATE_PROCESSING
            self._fire(EVENT_STATE_CHANGED, scan)
            self._notify()
            back_parts = await self._stream_documents(scan)
            if scan.is_terminal():
                return False
            if await self._assemble_result(scan, back_parts) is None:
                return False
            if scan.is_terminal():
                return False
            pages, size = await self._file_job(
                _interleave_duplex, fronts, scan.file_path, self._rotate_duplex_backs
            )
            scan.pages_done = pages
            scan.bytes_written = size
            return True
        finally:
            self._back_events.pop(scan.scan_id, None)
            for writer in back_parts:
                await self._file_job(writer.cleanup)
            await self._file_job(_safe_unlink, fronts)

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
                    scan.file_path.with_name(
                        f"{scan.file_path.name}.part{scan.scan_phase or ''}{doc_index}"
                    )
                )
                parts.append(writer)
                got_data = False
                try:
                    await self._file_job(writer.open)
                    async for chunk in self._client.iter_next_document(scan.job_url):
                        got_data = True
                        await self._file_job(writer.write, chunk)
                finally:
                    await self._file_job(writer.close)
                if not got_data:
                    await self._file_job(writer.cleanup)
                    parts.pop()
                    break
                doc_index += 1
                scan.pages_done = max(scan.pages_done, scan.front_pages + doc_index)
                scan.last_seen = datetime.now(UTC)
                self._fire(EVENT_STATE_CHANGED, scan)
                self._notify()
        except BaseException:
            # Includes task cancellation: never leave a scratch file or an
            # open descriptor behind, and never silently complete a batch
            # after losing a later document.
            for writer in parts:
                await self._file_job(writer.cleanup)
            raise
        finally:
            poll_task.cancel()
            try:
                await poll_task
            except (asyncio.CancelledError, Exception):
                pass
        return parts

    async def _assemble_result(
        self, scan: TrackedScan, parts: list[_PdfFileWriter]
    ) -> int | None:
        """Validate the streamed parts and produce scan.file_path.

        Returns the PDF's page count, or None after marking the scan failed.
        The driver owns scratch cleanup. A single document is renamed into
        place and parsed for its page count; multiple are concatenated.
        """
        if not parts:
            self._mark_terminal(
                scan, STATE_FAILED, None, error="no document returned from scanner"
            )
            return None

        # "Valid" = looks like a complete PDF. HP MFPs occasionally hand back a
        # truncated catalog header (~58 bytes) for an unsupported DPI/colour
        # combo without a 4xx/5xx; the EOF check turns that into a clear
        # failure rather than a "completed" claim on a broken file.
        valid = [w for w in parts if w.is_valid_pdf()]
        if len(valid) != len(parts):
            first = next(w for w in parts if not w.is_valid_pdf())
            if not first.head.startswith(b"%PDF-"):
                err = f"scanner returned a non-PDF response ({first.bytes_written} bytes)"
            else:
                err = (
                    f"scanner returned a truncated PDF ({first.bytes_written} bytes; "
                    f"no EOF trailer). This usually means the requested DPI/color "
                    f"combo isn't supported by the device."
                )
            self._mark_terminal(scan, STATE_FAILED, None, error=err)
            return None

        pages: int
        try:
            if len(valid) == 1:
                await self._file_job(valid[0].commit, scan.file_path)
                scan.bytes_written = valid[0].bytes_written
                # Bundle-mode scanners pack the whole ADF batch into one
                # document, so the document count (1) understates the pages
                # and the device counter can overstate them. The file itself
                # is the truth when pypdf can read it.
                pages = await self._file_job(
                    _count_pdf_pages, scan.file_path
                )
                scan.pages_done = scan.front_pages + pages
            else:
                pages, size = await self._file_job(
                    _merge_pdfs, [w.path for w in valid], scan.file_path
                )
                scan.bytes_written = size
                scan.pages_done = scan.front_pages + pages
                _LOGGER.info(
                    "scan %s: merged %d documents into a %d-page PDF",
                    scan.scan_id, len(valid), pages,
                )
        except Exception as exc:
            self._mark_terminal(
                scan, STATE_FAILED, None, error=f"could not assemble PDF: {exc}"
            )
            return None

        if self._rotate_duplex_backs and scan.duplex and pages > 1:
            try:
                scan.bytes_written = await self._file_job(
                    _rotate_back_sides, scan.file_path
                )
            except Exception as exc:
                _LOGGER.warning(
                    "scan %s: could not rotate duplex back sides: %s",
                    scan.scan_id, exc,
                )
        return pages

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
                if scan.is_terminal():
                    return
                if info.state in {"Canceled", "Cancelled", "Aborted"}:
                    self._mark_terminal(
                        scan, _ESCL_STATE_MAP[info.state], info.state_reasons, error=None
                    )
                    if task := self._driver_tasks.get(scan.scan_id):
                        task.cancel()
                    return
                changed = False
                if info.state in {"Processing", "ProcessingStopped"}:
                    state = _ESCL_STATE_MAP[info.state]
                    if state != scan.state:
                        scan.state = state
                        changed = True
                if info.state_reasons and info.state_reasons != scan.state_reasons:
                    scan.state_reasons = info.state_reasons
                    changed = True
                if info.pages_completed is not None:
                    # Scanner's counter races with our local pages_done
                    # (incremented after each NextDocument pull). Take the
                    # higher of the two so the UI never goes backwards.
                    if scan.front_pages + info.pages_completed > scan.pages_done:
                        scan.pages_done = scan.front_pages + info.pages_completed
                        changed = True
                if changed:
                    self._fire(EVENT_STATE_CHANGED, scan)
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
            # No driver is active when this runs. Remove intermediate files
            # left by an abrupt process exit, including private manual fronts.
            for pattern in (
                "scan-*.pdf.part*", "scan-*.pdf.fronts", "scan-*.pdf.duplex", "scan-*.pdf.rot",
            ):
                for part in self._storage.glob(pattern):
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
        task = asyncio.current_task()
        self._purge_tasks.add(task)
        try:
            async with self._storage_lock:
                if self._shutting_down or self._starting or self._driver_tasks:
                    return
                deleted = await self._file_job(self._ensure_storage_and_purge)
                self._reap_tracked(deleted)
        finally:
            self._purge_tasks.discard(task)

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
