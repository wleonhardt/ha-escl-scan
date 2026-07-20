"""Coordinator lifecycle tests against the real HomeAssistant fixture with a
fake scanner client. Covers the P1 fixes: busy guard, streaming + PDF
validation, cancel, clean shutdown, multi-document drain, page reconciliation.
"""
import asyncio

import pytest

from custom_components.escl_scan.coordinator import ScanBusyError, ScanCoordinator
from custom_components.escl_scan.scanner import JobInfo

VALID_PDF = b"%PDF-1.4\n" + b"x" * 4096 + b"\n%%EOF\n"


class FakeClient:
    def __init__(
        self, docs=None, *, job_state="Completed", pages=None,
        source="Platen", gate=None, hang=False,
    ):
        self._docs = [list(d) for d in (docs or [])]
        self.job_state = job_state
        self.pages = pages
        self._source = source
        self._gate = gate
        self._hang = hang
        self.deleted = []
        self.closed = False

    async def detect_source(self):
        return self._source

    async def create_job(self, **kwargs):
        return "https://scanner/eSCL/ScanJobs/j1"

    async def iter_next_document(self, url):
        if self._hang:
            await asyncio.Event().wait()  # blocks until cancelled
        if self._gate is not None:
            await self._gate.wait()
        if self._docs:
            for chunk in self._docs.pop(0):
                yield chunk

    async def get_job_info(self, url):
        return JobInfo(
            state=self.job_state, state_reasons=None, pages_completed=self.pages
        )

    async def delete_job(self, url):
        self.deleted.append(url)
        return True

    async def async_close(self):
        self.closed = True


@pytest.fixture
async def make_coord(hass, tmp_path):
    created = []

    def _make(client, ttl=3600):
        coord = ScanCoordinator(
            hass, client, storage_dir=tmp_path / "store",
            default_dpi=300, default_color="color", file_ttl_seconds=ttl,
        )
        created.append(coord)
        return coord

    yield _make
    for coord in created:
        await coord.async_shutdown()


async def _drive(coord, scan):
    """Await the background driver task for a scan to completion."""
    await coord._driver_tasks[scan.scan_id]


async def _wait_for(predicate, timeout=2.0):
    async with asyncio.timeout(timeout):
        while not predicate():
            await asyncio.sleep(0.01)


async def test_happy_path_streams_and_commits(make_coord):
    client = FakeClient(docs=[[VALID_PDF]])
    coord = make_coord(client)
    scan = await coord.start_scan()
    await _drive(coord, scan)

    assert scan.state == "completed"
    assert scan.file_path.exists()
    assert scan.file_path.read_bytes() == VALID_PDF
    assert scan.bytes_written == len(VALID_PDF)
    assert client.deleted  # server-side job cleaned up
    assert not list((coord._storage).glob("*.part"))  # no scratch leak


async def test_streamed_in_multiple_chunks(make_coord):
    parts = [VALID_PDF[i:i + 500] for i in range(0, len(VALID_PDF), 500)]
    coord = make_coord(FakeClient(docs=[parts]))
    scan = await coord.start_scan()
    await _drive(coord, scan)
    assert scan.state == "completed"
    assert scan.file_path.read_bytes() == VALID_PDF


async def test_truncated_pdf_fails(make_coord):
    coord = make_coord(FakeClient(docs=[[b"%PDF-1.4 header only, no trailer"]]))
    scan = await coord.start_scan()
    await _drive(coord, scan)
    assert scan.state == "failed"
    assert "truncated" in scan.error
    assert scan.file_path is not None and not scan.file_path.exists()


async def test_non_pdf_body_fails(make_coord):
    coord = make_coord(FakeClient(docs=[[b"<html>login</html>\n%%EOF"]]))
    scan = await coord.start_scan()
    await _drive(coord, scan)
    assert scan.state == "failed"
    assert "non-PDF" in scan.error


async def test_no_document_fails(make_coord):
    coord = make_coord(FakeClient(docs=[]))
    scan = await coord.start_scan()
    await _drive(coord, scan)
    assert scan.state == "failed"
    assert "no document" in scan.error


async def test_multi_document_saves_first_drains_rest(make_coord):
    coord = make_coord(FakeClient(docs=[[VALID_PDF], [b"%PDF-1.4 second\n%%EOF"]]))
    scan = await coord.start_scan()
    await _drive(coord, scan)
    assert scan.state == "completed"
    assert scan.pages_done == 2
    assert scan.file_path.read_bytes() == VALID_PDF  # only first saved


async def test_final_jobinfo_reconciles_page_count(make_coord):
    # Single document pulled (pages_done=1) but scanner reports 5 server-side.
    coord = make_coord(FakeClient(docs=[[VALID_PDF]], pages=5))
    scan = await coord.start_scan()
    await _drive(coord, scan)
    assert scan.state == "completed"
    assert scan.pages_done == 5


async def test_final_jobinfo_aborted_is_honored(make_coord):
    coord = make_coord(FakeClient(docs=[[VALID_PDF]], job_state="Aborted"))
    scan = await coord.start_scan()
    await _drive(coord, scan)
    assert scan.state == "aborted"


async def test_busy_guard_rejects_second_start(make_coord):
    gate = asyncio.Event()
    client = FakeClient(docs=[[VALID_PDF]], gate=gate)
    coord = make_coord(client)
    scan = await coord.start_scan()
    await _wait_for(lambda: scan.state == "processing")

    with pytest.raises(ScanBusyError):
        await coord.start_scan()

    gate.set()
    await _drive(coord, scan)
    assert scan.state == "completed"


async def test_cancel_marks_canceled_and_wins(make_coord):
    gate = asyncio.Event()
    client = FakeClient(docs=[[VALID_PDF]], gate=gate)
    coord = make_coord(client)
    scan = await coord.start_scan()
    await _wait_for(lambda: scan.state == "processing" and scan.job_url)

    assert await coord.async_cancel(scan.scan_id) is True
    assert scan.state == "canceled"

    gate.set()  # let the driver unblock; canceled must not be overwritten
    await _drive(coord, scan)
    assert scan.state == "canceled"
    assert scan.file_path is None or not scan.file_path.exists()


async def test_shutdown_cancels_inflight_driver(make_coord):
    client = FakeClient(hang=True)
    coord = make_coord(client)
    scan = await coord.start_scan()
    await _wait_for(lambda: scan.state == "processing")

    await coord.async_shutdown()

    assert coord._driver_tasks == {}
    assert coord._hold_tasks == set()
    assert client.closed is True


async def test_start_after_terminal_is_allowed(make_coord):
    coord = make_coord(FakeClient(docs=[[VALID_PDF]]))
    scan1 = await coord.start_scan()
    await _drive(coord, scan1)
    assert scan1.state == "completed"
    # current is held terminal briefly; a new start must still be accepted.
    coord._client._docs = [[VALID_PDF]]
    scan2 = await coord.start_scan()
    await _drive(coord, scan2)
    assert scan2.state == "completed"
    assert scan2.scan_id != scan1.scan_id
