"""Retained results survive reload without reviving scanner jobs or private files."""
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.escl_scan import ScanFileView, async_remove_entry
from custom_components.escl_scan.const import DOMAIN
from custom_components.escl_scan.coordinator import ScanCoordinator
from custom_components.escl_scan.results import LatestScan, store_key
from custom_components.escl_scan.sensor import ScannerScanSensor

from .fakes import FakeClient
from .test_coordinator import VALID_PDF, TwoPassClient, _wait_for


@pytest.fixture
async def create(hass, tmp_path):
    coordinators = []

    def make(client=None, **kwargs):
        coord = ScanCoordinator(hass, client or FakeClient(docs=[[VALID_PDF]]),
                                storage_dir=tmp_path, default_dpi=300, default_color="color",
                                file_ttl_seconds=60, entry_id="result-entry", **kwargs)
        coordinators.append(coord)
        return coord

    yield make
    for coord in coordinators:
        await coord.async_shutdown()


async def complete(coord):
    scan = await coord.start_scan()
    await coord._driver_tasks[scan.scan_id]
    assert scan.state == "completed"
    return scan


async def test_latest_survives_idle_and_reload_with_authenticated_file(hass, create):
    coord = create()
    scan = await complete(coord)
    before = coord.latest.snapshot()
    coord._current = None
    sensor = ScannerScanSensor(coord, "result-entry")
    assert sensor.native_value == "idle"
    assert sensor.extra_state_attributes["latest_scan"]["scan_id"] == scan.scan_id
    await coord.async_shutdown()
    restored = create()
    await restored.latest.async_load()
    assert restored.current is None and not restored._scans and not restored._driver_tasks
    assert restored.latest.snapshot() == before
    path, filename = await restored.async_download_file(scan.scan_id)
    assert path.read_bytes() == VALID_PDF and filename == scan.filename
    hass.data[DOMAIN] = {"result-entry": {"coordinator": restored}}
    view = ScanFileView(hass)
    assert view.requires_auth
    response = await view.get(None, scan.scan_id)
    assert response.status == 200 and response.headers["Cache-Control"] == "private, no-store"


async def test_expiry_removes_action_without_waiting_for_purge(create):
    coord = create()
    scan = await complete(coord)
    expired = {**coord.latest._record,
               "expires_at": (datetime.now(UTC) - timedelta(seconds=1)).isoformat()}
    coord.latest._record = expired
    assert scan.file_path.exists()
    assert coord.latest.snapshot()["availability"] == "expired"
    assert coord.latest.snapshot()["file_url"] is None
    assert await coord.async_download_file(scan.scan_id) is None
    await coord.async_shutdown()
    restored = create()
    await restored.latest.async_load()
    assert restored.latest.snapshot()["expires_at"] == expired["expires_at"]
    assert restored.latest.snapshot()["file_url"] is None


async def test_missing_and_symlink_results_are_not_downloadable(create, tmp_path):
    coord = create()
    scan = await complete(coord)
    scan.file_path.unlink()
    assert await coord.async_download_file(scan.scan_id) is None
    assert coord.latest.snapshot()["availability"] == "missing"
    outside = tmp_path / "private.txt"
    outside.write_bytes(VALID_PDF)
    scan.file_path.symlink_to(outside)
    assert await coord.async_download_file(scan.scan_id) is None


async def test_private_manual_fronts_and_failed_next_job_do_not_replace_latest(create):
    client = TwoPassClient(VALID_PDF, VALID_PDF)
    coord = create(client)
    scan = await coord.start_scan(duplex=True)
    await _wait_for(lambda: scan.state == "awaiting-back-sides")
    assert coord.latest.snapshot() is None
    assert await coord.async_download_file(scan.scan_id) is None
    await coord.async_cancel(scan.scan_id)
    await coord._driver_tasks[scan.scan_id]
    assert coord.latest.snapshot() is None
    successful = create()
    prior = await complete(successful)
    with patch.object(successful._client, "create_job", AsyncMock(side_effect=OSError("offline"))):
        failed = await successful.start_scan()
        await successful._driver_tasks[failed.scan_id]
    assert failed.state == "failed"
    assert successful.latest.snapshot()["scan_id"] == prior.scan_id


@pytest.mark.parametrize("change", [
    {"filename": "../../secret.pdf"},
    {"filename": "scan-20261009-120000-feeder-abcdef123456.pdf.fronts"},
    {"scan_id": "../../secret"}, {"pages_done": True}, {"finished_at": "yesterday"},
    {"expires_at": "2026-10-09T12:00:00"},
])
async def test_invalid_metadata_is_ignored(hass, tmp_path, hass_storage, change):
    record = {"scan_id": "abcdef123456", "filename": "scan-20261009-120000-feeder-abcdef123456.pdf",
              "pages_done": 1, "finished_at": datetime.now(UTC).isoformat(),
              "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(), **change}
    hass_storage[store_key("invalid")] = {"version": 1, "data": record}
    latest = LatestScan(hass, tmp_path, 60, "invalid")
    await latest.async_load()
    assert latest.snapshot() is None


async def test_file_check_race_never_returns_the_newer_pdf_for_an_older_id(create):
    coord = create()
    scan = await complete(coord)
    newer = {**coord.latest._record, "scan_id": "abcdef123456",
             "filename": "scan-20261009-120000-feeder-abcdef123456.pdf"}

    async def replace():
        coord.latest._record = newer
        return True

    with patch.object(coord.latest, "async_reconcile", replace):
        assert await coord.async_download_file(scan.scan_id) is None


async def test_entry_removal_deletes_only_its_metadata(hass, create, hass_storage):
    coord = create()
    scan = await complete(coord)
    await coord.async_shutdown()
    entry = MockConfigEntry(domain=DOMAIN, entry_id="result-entry", data={})
    await async_remove_entry(hass, entry)
    assert store_key(entry.entry_id) not in hass_storage
    assert Path(scan.file_path).exists()


async def test_reduced_ttl_and_file_touch_never_extend_saved_expiry(hass, create, tmp_path):
    import os

    coord = create()
    scan = await complete(coord)
    await coord.async_shutdown()
    original = coord.latest.snapshot()["expires_at"]
    shorter = LatestScan(hass, tmp_path, 10, "result-entry")
    await shorter.async_load()
    assert shorter.snapshot()["expires_at"] < original
    tightened = shorter.snapshot()["expires_at"]
    await shorter.async_close()
    os.utime(scan.file_path, None)
    longer = LatestScan(hass, tmp_path, 3600, "result-entry")
    await longer.async_load()
    assert longer.snapshot()["expires_at"] == tightened
    await longer.async_close()


async def test_periodic_purge_removes_link_and_keeps_expiry_explanation(create):
    import os

    coord = create()
    scan = await complete(coord)
    old = (datetime.now(UTC) - timedelta(hours=2)).timestamp()
    os.utime(scan.file_path, (old, old))
    await coord.async_purge_now()
    assert not scan.file_path.exists()
    assert coord.latest.snapshot()["file_url"] is None
    assert coord.latest.snapshot()["availability"] in {"expired", "missing"}
    assert await coord.async_download_file(scan.scan_id) is None
