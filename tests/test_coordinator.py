"""Coordinator lifecycle tests against the real HomeAssistant fixture with a
fake scanner client. Covers the P1 fixes: busy guard, streaming + PDF
validation, cancel, clean shutdown, multi-document drain, page reconciliation.
"""
import asyncio
import io

import pytest

from custom_components.escl_scan.coordinator import ScanBusyError, ScanCoordinator
from custom_components.escl_scan.scanner import DEFAULT_REGION, ScannerCapabilities

from .fakes import FakeClient

VALID_PDF = b"%PDF-1.4\n" + b"x" * 4096 + b"\n%%EOF\n"


def real_pdf(n_pages: int = 1) -> bytes:
    """A genuinely parseable PDF (pypdf can merge it), unlike VALID_PDF which
    only satisfies the header/EOF sniff used on the single-document path."""
    from pypdf import PdfWriter

    writer = PdfWriter()
    for _ in range(n_pages):
        writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


@pytest.fixture
async def make_coord(hass, tmp_path):
    created = []

    def _make(client, ttl=3600, **kw):
        coord = ScanCoordinator(
            hass, client, storage_dir=tmp_path / "store",
            default_dpi=300, default_color="color", file_ttl_seconds=ttl, **kw,
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
    assert not list(coord._storage.glob("*.part*"))  # no scratch leak


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


async def test_single_bundle_pdf_page_count(make_coord):
    # Bundle-mode scanner: one document holding 3 pages. pages_done must
    # reflect the PDF's real page count, not the document count (1).
    coord = make_coord(FakeClient(docs=[[real_pdf(3)]]))
    scan = await coord.start_scan()
    await _drive(coord, scan)
    assert scan.state == "completed"
    assert scan.pages_done == 3


async def test_multi_document_merges(make_coord):
    # Per-page scanner: two single-page documents -> one merged 2-page PDF.
    coord = make_coord(FakeClient(docs=[[real_pdf(1)], [real_pdf(1)]]))
    scan = await coord.start_scan()
    await _drive(coord, scan)
    assert scan.state == "completed"
    from pypdf import PdfReader

    assert len(PdfReader(str(scan.file_path)).pages) == 2
    assert scan.pages_done == 2
    assert not list(coord._storage.glob("*.part*"))  # scratch parts cleaned


async def test_multi_document_pages_streamed_in_chunks(make_coord):
    # Each document itself split across TCP chunks, merged into 3 pages.
    doc = real_pdf(1)
    chunked = [doc[i:i + 128] for i in range(0, len(doc), 128)]
    coord = make_coord(FakeClient(docs=[chunked, chunked, chunked]))
    scan = await coord.start_scan()
    await _drive(coord, scan)
    assert scan.state == "completed"
    from pypdf import PdfReader

    assert len(PdfReader(str(scan.file_path)).pages) == 3


async def test_multi_document_drops_truncated_part(make_coord):
    # One good page + one truncated (no EOF) -> keep the good one only.
    coord = make_coord(
        FakeClient(docs=[[real_pdf(1)], [b"%PDF-1.4 truncated, no trailer"]])
    )
    scan = await coord.start_scan()
    await _drive(coord, scan)
    assert scan.state == "completed"
    from pypdf import PdfReader

    assert len(PdfReader(str(scan.file_path)).pages) == 1
    assert not list(coord._storage.glob("*.part*"))


async def test_device_counter_plus_pull_does_not_double_count(make_coord):
    # Live HP behaviour: ScannerStatus reports ImagesCompleted=1 while the
    # single platen page is still transferring; pulling the document must
    # not bump pages_done to 2.
    gate = asyncio.Event()
    coord = make_coord(FakeClient(docs=[[real_pdf(1)]], pages=1, gate=gate))
    scan = await coord.start_scan()
    await _wait_for(lambda: scan.pages_done == 1)  # counted by the poll loop
    gate.set()
    await _drive(coord, scan)
    assert scan.state == "completed"
    assert scan.pages_done == 1


async def test_pdf_page_count_beats_device_counter(make_coord):
    # Device says 5, file has 3 pages: the file wins.
    coord = make_coord(FakeClient(docs=[[real_pdf(3)]], pages=5))
    scan = await coord.start_scan()
    await _drive(coord, scan)
    assert scan.pages_done == 3


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


async def test_reap_drops_expired_terminal_scans_without_files(make_coord):
    # Failed scans never produce a file, so the old file-based reap kept them
    # forever. They must age out by finished_at instead.
    coord = make_coord(FakeClient(docs=[]), ttl=0)
    scan = await coord.start_scan()
    await _drive(coord, scan)
    assert scan.state == "failed" and scan.scan_id in coord._scans

    coord._current = None  # simulate the terminal hold having elapsed
    coord._reap_tracked(set())
    assert scan.scan_id not in coord._scans


async def test_reap_keeps_current_and_active_scans(make_coord):
    gate = asyncio.Event()
    coord = make_coord(FakeClient(docs=[[VALID_PDF]], gate=gate), ttl=0)
    scan = await coord.start_scan()
    await _wait_for(lambda: scan.state == "processing")
    coord._reap_tracked(set())
    assert scan.scan_id in coord._scans
    gate.set()
    await _drive(coord, scan)
    coord._reap_tracked(set())  # still `current` during the terminal hold
    assert scan.scan_id in coord._scans


CAPS = ScannerCapabilities(
    platen_max=(2550, 3508), adf_max=(2550, 4200), adf_duplex=True,
    resolutions=[75, 300, 600],
)


async def test_region_from_capabilities_per_source(make_coord):
    client = FakeClient(docs=[[VALID_PDF]], source="Feeder", caps=CAPS)
    coord = make_coord(client)
    scan = await coord.start_scan()
    await _drive(coord, scan)
    assert (client.create_kwargs["width"], client.create_kwargs["height"]) == (2550, 4200)

    client._docs = [[VALID_PDF]]
    scan = await coord.start_scan(source="Platen")
    await _drive(coord, scan)
    assert (client.create_kwargs["width"], client.create_kwargs["height"]) == (2550, 3508)


async def test_region_default_without_capabilities(make_coord):
    client = FakeClient(docs=[[VALID_PDF]])
    coord = make_coord(client)
    scan = await coord.start_scan()
    await _drive(coord, scan)
    assert coord.capabilities is None
    assert (client.create_kwargs["width"], client.create_kwargs["height"]) == DEFAULT_REGION


async def test_dpi_snaps_to_supported_resolution(make_coord):
    client = FakeClient(docs=[[VALID_PDF]], caps=CAPS)
    coord = make_coord(client)
    scan = await coord.start_scan(dpi=1200)
    await _drive(coord, scan)
    assert scan.dpi == 600
    assert client.create_kwargs["dpi"] == 600


async def test_duplex_only_for_feeder_on_capable_adf(make_coord):
    client = FakeClient(docs=[[VALID_PDF]], source="Feeder", caps=CAPS)
    coord = make_coord(client, default_duplex=True)
    scan = await coord.start_scan()
    await _drive(coord, scan)
    assert scan.duplex is True and client.create_kwargs["duplex"] is True

    client._docs = [[VALID_PDF]]
    scan = await coord.start_scan(source="Platen")  # platen has no duplex
    await _drive(coord, scan)
    assert scan.duplex is False and client.create_kwargs["duplex"] is False

    client.caps = ScannerCapabilities(adf_duplex=False)
    coord._caps = client.caps
    client._docs = [[VALID_PDF]]
    scan = await coord.start_scan(source="Feeder", duplex=True)
    await _drive(coord, scan)
    assert scan.duplex is False  # requested but unsupported


async def test_copy_dir_receives_finished_scan(make_coord, tmp_path):
    consume = tmp_path / "paperless" / "consume"
    coord = make_coord(FakeClient(docs=[[VALID_PDF]]), copy_dir=consume)
    scan = await coord.start_scan()
    await _drive(coord, scan)
    assert scan.state == "completed"
    assert scan.copied_to == consume / scan.filename
    assert scan.copied_to.read_bytes() == VALID_PDF
    assert not list(consume.glob(".*.tmp"))  # atomic rename, no leftovers
    d = scan.to_dict()
    assert d["file_path"] == str(scan.file_path)
    assert d["copied_to"] == str(scan.copied_to)


async def test_copy_dir_failure_does_not_fail_scan(make_coord, tmp_path):
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("file in the way")
    coord = make_coord(FakeClient(docs=[[VALID_PDF]]), copy_dir=blocker)
    scan = await coord.start_scan()
    await _drive(coord, scan)
    assert scan.state == "completed"
    assert scan.copied_to is None
    assert scan.file_path.exists()


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
