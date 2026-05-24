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
from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
from pathlib import Path
import time
from typing import Any, Callable
import uuid

from homeassistant.core import HomeAssistant

from .const import EVENT_COMPLETED, EVENT_STATE_CHANGED
from .scanner import (
    JobInfo,
    ScannerClient,
    TERMINAL_JOB_STATES,
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


@dataclass
class TrackedScan:
    scan_id: str
    source: str
    dpi: int
    color: str
    submitted_at: datetime
    job_url: str | None = None
    state: str = STATE_PENDING
    state_reasons: str | None = None
    pages_done: int = 0
    pages_total: int | None = None
    filename: str | None = None
    file_path: Path | None = None
    bytes_written: int = 0
    finished_at: datetime | None = None
    error: str | None = None
    last_seen: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def is_terminal(self) -> bool:
        return self.state in _TERMINAL_STATES

    def to_dict(self) -> dict[str, Any]:
        return {
            "scan_id": self.scan_id,
            "source": self.source,
            "dpi": self.dpi,
            "color": self.color,
            "state": self.state,
            "state_reasons": self.state_reasons,
            "pages_done": self.pages_done,
            "pages_total": self.pages_total,
            "filename": self.filename,
            "bytes": self.bytes_written,
            "submitted_at": self.submitted_at.isoformat(),
            "finished_at": (
                self.finished_at.isoformat() if self.finished_at else None
            ),
            "error": self.error,
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
        file_ttl_seconds: int,
    ) -> None:
        self._hass = hass
        self._client = client
        self._storage = storage_dir
        self._default_dpi = default_dpi
        self._default_color = default_color
        self._file_ttl = file_ttl_seconds
        self._scans: dict[str, TrackedScan] = {}
        self._current: TrackedScan | None = None
        self._driver_tasks: dict[str, asyncio.Task] = {}
        self._update_listeners: list[Callable[[], None]] = []
        self._storage.mkdir(parents=True, exist_ok=True)

    @property
    def current(self) -> TrackedScan | None:
        return self._current

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
    ) -> TrackedScan:
        """Kick off a scan. Returns the tracked scan immediately; the
        driver task assembles pages in the background."""
        actual_source = source or await self._client.detect_source()
        actual_dpi = dpi or self._default_dpi
        actual_color = color or self._default_color

        scan_id = uuid.uuid4().hex[:12]
        scan = TrackedScan(
            scan_id=scan_id,
            source=actual_source,
            dpi=actual_dpi,
            color=actual_color,
            submitted_at=datetime.now(timezone.utc),
        )
        self._scans[scan_id] = scan
        self._current = scan
        self._fire(EVENT_STATE_CHANGED, scan)
        self._notify()

        self._purge_expired_files()
        self._driver_tasks[scan_id] = self._hass.loop.create_task(
            self._drive_scan(scan)
        )
        _LOGGER.info(
            "started scan %s (source=%s dpi=%s color=%s)",
            scan_id, actual_source, actual_dpi, actual_color,
        )
        return scan

    async def async_cancel(self, scan_id: str) -> bool:
        scan = self._scans.get(scan_id)
        if scan is None or scan.is_terminal():
            return False
        ok = False
        if scan.job_url:
            try:
                ok = await self._client.delete_job(scan.job_url)
            except Exception as exc:
                _LOGGER.warning("delete_job for %s failed: %s", scan_id, exc)
        # The driver task will observe the cancel via JobInfo or NextDocument
        # returning 404; mark optimistically here so the UI updates fast.
        self._mark_terminal(scan, STATE_CANCELED, "user-cancel", error=None)
        return ok

    # ── Driver ──────────────────────────────────────────────────────────

    async def _drive_scan(self, scan: TrackedScan) -> None:
        """Foreground orchestration of a single scan job."""
        try:
            try:
                scan.job_url = await self._client.create_job(
                    source=scan.source,
                    dpi=scan.dpi,
                    color=scan.color,
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
            buffer = bytearray()

            poll_task = self._hass.loop.create_task(self._poll_loop(scan))
            try:
                # Pull pages serially; eSCL servers serialize these anyway.
                while not scan.is_terminal():
                    chunk = await self._client.pull_next_document(scan.job_url)
                    if chunk is None:
                        break
                    if not buffer:
                        # First PDF chunk — happy path for HP/Canon/Epson
                        # multifunction devices that bundle the whole ADF
                        # batch into a single document.
                        buffer.extend(chunk)
                    else:
                        # Subsequent chunks: scanner returned one document
                        # per page instead of bundling. Keep the first; log
                        # the rest. Proper multi-PDF concatenation is on
                        # the roadmap (issue #1).
                        _LOGGER.warning(
                            "scan %s: scanner returned a second document chunk "
                            "(%d bytes) — ignoring (only first chunk is saved)",
                            scan.scan_id, len(chunk),
                        )
                    scan.pages_done += 1
                    scan.last_seen = datetime.now(timezone.utc)
                    self._fire(EVENT_STATE_CHANGED, scan)
                    self._notify()
            finally:
                poll_task.cancel()
                try:
                    await poll_task
                except (asyncio.CancelledError, Exception):
                    pass

            if scan.is_terminal():
                # Coordinator cancel beat us to it.
                return

            if not buffer:
                self._mark_terminal(
                    scan, STATE_FAILED, None, error="no document returned from scanner"
                )
                return

            try:
                scan.file_path.write_bytes(bytes(buffer))
                scan.bytes_written = len(buffer)
            except OSError as exc:
                self._mark_terminal(
                    scan, STATE_FAILED, None, error=f"write failed: {exc}"
                )
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

            self._mark_terminal(scan, final_state, final_reasons, error=None)
            # Best-effort delete of the server-side job.
            try:
                await self._client.delete_job(scan.job_url)
            except Exception:
                pass
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            _LOGGER.exception("scan driver crashed")
            self._mark_terminal(scan, STATE_FAILED, None, error=str(exc))
        finally:
            self._driver_tasks.pop(scan.scan_id, None)
            self._hass.loop.create_task(self._terminal_hold(scan))

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
        scan.finished_at = datetime.now(timezone.utc)
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

    def _purge_expired_files(self) -> None:
        cutoff = time.time() - self._file_ttl
        try:
            for f in self._storage.glob("scan-*.pdf"):
                if f.is_file() and f.stat().st_mtime < cutoff:
                    try:
                        f.unlink()
                    except OSError:
                        pass
        except OSError:
            pass
        # Drop tracked entries whose files are gone.
        for scan_id in list(self._scans):
            s = self._scans[scan_id]
            if s.file_path and not s.file_path.exists() and s.is_terminal():
                self._scans.pop(scan_id, None)
