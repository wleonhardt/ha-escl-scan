"""One durable successful result; PDF retention stays owned by the coordinator."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
import logging
from pathlib import Path
import re
import stat
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

_LOGGER = logging.getLogger(__name__)
STORAGE_VERSION = 1


def store_key(entry_id: str) -> str:
    return f"escl_scan.latest_scan.{entry_id}"


def _date(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        date = datetime.fromisoformat(value)
        return date.astimezone(UTC) if date.tzinfo is not None else None
    except (ValueError, OverflowError):
        return None


def _record(value: Any) -> dict | None:
    """Allow only a generated final basename; never restore filesystem paths."""
    if not isinstance(value, dict):
        return None
    scan_id, filename = value.get("scan_id"), value.get("filename")
    if not isinstance(scan_id, str) or not re.fullmatch(r"[a-f0-9]{12}", scan_id):
        return None
    if not isinstance(filename, str) or not re.fullmatch(
        rf"scan-\d{{8}}-\d{{6}}-(?:feeder|platen)-{scan_id}\.pdf", filename
    ):
        return None
    finished, expires = _date(value.get("finished_at")), _date(value.get("expires_at"))
    pages = value.get("pages_done")
    if finished is None or expires is None or type(pages) is not int or pages < 1:
        return None
    return {"scan_id": scan_id, "filename": filename, "pages_done": pages,
            "finished_at": finished.isoformat(), "expires_at": expires.isoformat()}


def inspect_file(path: Path, deadline: datetime, ttl: int) -> tuple[str, datetime]:
    """Blocking read-only check. Never follow a symlink or extend a deadline."""
    if datetime.now(UTC) >= deadline:
        return "expired", deadline
    try:
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_size == 0:
            return "missing", deadline
        file_deadline = datetime.fromtimestamp(info.st_mtime, UTC) + timedelta(seconds=ttl)
        deadline = min(deadline, file_deadline)
    except (OSError, ValueError, OverflowError):
        return "missing", deadline
    return ("expired" if datetime.now(UTC) >= deadline else "available"), deadline


class LatestScan:
    """Versioned metadata only; loading never reconstructs or resumes a job."""

    def __init__(self, hass: HomeAssistant, storage: Path, ttl: int, entry_id: str | None):
        self._hass, self._directory, self._ttl = hass, storage, ttl
        self._store = Store(hass, STORAGE_VERSION, store_key(entry_id), private=True,
                            atomic_writes=True) if entry_id else None
        self._record: dict | None = None
        self._availability = "missing"
        self._closed = False

    async def async_load(self) -> None:
        if self._store:
            try:
                self._record = _record(await self._store.async_load())
            except Exception:  # Bad metadata must not prevent scanning.
                _LOGGER.warning("Could not restore latest scan metadata", exc_info=True)
        await self.async_reconcile()

    def completed(self, scan) -> None:
        if self._closed or scan.state != "completed" or not scan.finished_at or not scan.file_path:
            return
        record = _record({
            "scan_id": scan.scan_id, "filename": scan.filename, "pages_done": scan.pages_done,
            "finished_at": scan.finished_at.isoformat(),
            "expires_at": (scan.finished_at + timedelta(seconds=self._ttl)).isoformat(),
        })
        if record is None:
            return
        self._record, self._availability = record, "available"
        self._save_later()

    def _save_later(self) -> None:
        if self._store and not self._closed:
            self._store.async_delay_save(lambda: self._record)

    async def async_reconcile(self) -> bool:
        record = self._record
        if record is None:
            return False
        availability, deadline = await self._hass.async_add_executor_job(
            inspect_file, self._directory / record["filename"],
            _date(record["expires_at"]), self._ttl,
        )
        if self._closed or self._record is not record:
            return False  # A newer success arrived while the disk check ran.
        changed = availability != self._availability or deadline.isoformat() != record["expires_at"]
        self._availability = availability
        if deadline.isoformat() != record["expires_at"]:
            self._record = {**record, "expires_at": deadline.isoformat()}
            self._save_later()
        return changed

    def snapshot(self) -> dict | None:
        if self._record is None:
            return None
        record = self._record
        availability = self._availability
        if datetime.now(UTC) >= _date(record["expires_at"]):
            availability = "expired"
        return {
            **record, "availability": availability,
            "file_url": (f'/api/escl_scan/file/{record["scan_id"]}'
                         if availability == "available" else None),
        }

    async def async_close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._store and self._record:
            await self._store.async_save(self._record)
