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


def real_pdf(n_pages: int = 1) -> bytes:
    """Build a PDF with a real page tree for validation/merge tests."""
    from pypdf import PdfWriter

    writer = PdfWriter()
    for _ in range(n_pages):
        writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


VALID_PDF = real_pdf()


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


class TwoPassClient(FakeClient):
    """Each created job supplies its own complete document batch."""

    def __init__(self, fronts, backs):
        super().__init__(source="Feeder", caps=ScannerCapabilities(adf_duplex=False))
        self.passes = [fronts, backs]
        self.create_calls = 0

    async def create_job(self, **kwargs):
        self.create_calls += 1
        self.create_kwargs = kwargs
        self._docs = [[self.passes.pop(0)]]
        return f"https://scanner/eSCL/ScanJobs/j{self.create_calls}"


def marked_pdf(widths):
    from pypdf import PdfWriter

    writer = PdfWriter()
    for width in widths:
        writer.add_blank_page(width=width, height=200)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


@pytest.mark.parametrize("unknown_caps", [False, True])
@pytest.mark.parametrize("rotate", [False, True])
@pytest.mark.parametrize("reverse", [False, True])
async def test_manual_duplex_pairs_pages_and_publishes_only_after_backs(
    make_coord, tmp_path, unknown_caps, rotate, reverse,
):
    from pypdf import PdfReader

    backs = [203, 202, 201] if reverse else [201, 202, 203]
    client = TwoPassClient(marked_pdf([101, 102, 103]), marked_pdf(backs))
    if unknown_caps:
        client.caps = None
    copy = tmp_path / "copies"
    coord = make_coord(client, copy_dir=copy, rotate_duplex_backs=rotate)
    scan = await coord.start_scan(duplex=True)
    await _wait_for(lambda: scan.state == "awaiting-back-sides")
    assert scan.duplex_mode == "manual" and not scan.duplex
    assert scan.front_pages == scan.pages_done == 3
    assert scan.to_dict()["file_url"] is None
    assert not scan.file_path.exists() and not copy.exists()
    assert scan.job_url is None and len(client.deleted) == 1
    with pytest.raises(ScanBusyError):
        await coord.start_scan()
    with pytest.raises(ValueError, match="boolean"):
        await coord.async_scan_backs(scan.scan_id, reverse_back_order="false")
    assert scan.state == "awaiting-back-sides" and not scan.reverse_back_order
    await coord.async_scan_backs(scan.scan_id, reverse_back_order=reverse)
    assert scan.to_dict()["reverse_back_order"] is reverse
    with pytest.raises(ValueError, match="not waiting"):
        await coord.async_scan_backs(scan.scan_id)
    await _drive(coord, scan)
    assert scan.state == "completed" and scan.pages_done == 6
    pages = PdfReader(str(scan.file_path)).pages
    assert [p.mediabox.width for p in pages] == [101, 201, 102, 202, 103, 203]
    assert [p.rotation for p in pages] == [0, 180 if rotate else 0] * 3
    assert scan.copied_to.read_bytes() == scan.file_path.read_bytes()
    assert len(client.deleted) == 2
    assert list(coord._storage.iterdir()) == [scan.file_path]


@pytest.mark.parametrize("exit_kind", ["cancel", "shutdown", "timeout"])
async def test_manual_duplex_wait_exit_removes_private_fronts(make_coord, monkeypatch, exit_kind):
    if exit_kind == "timeout":
        monkeypatch.setattr(
            "custom_components.escl_scan.coordinator.MANUAL_RELOAD_TIMEOUT_SECONDS", .03
        )
    client = TwoPassClient(VALID_PDF, VALID_PDF)
    coord = make_coord(client)
    scan = await coord.start_scan(duplex=True)
    task = coord._driver_tasks[scan.scan_id]
    await _wait_for(lambda: scan.state == "awaiting-back-sides")
    if exit_kind == "cancel":
        assert await coord.async_cancel(scan.scan_id)
        await task
        assert scan.state == "canceled"
    elif exit_kind == "shutdown":
        await coord.async_shutdown()
    else:
        await task
        assert scan.state == "failed" and "timed out" in scan.error
    assert client.create_calls == 1
    assert not coord._back_events
    assert not list(coord._storage.iterdir())


async def test_manual_duplex_mismatched_backs_fail_without_folder_copy(make_coord, tmp_path):
    client = TwoPassClient(real_pdf(3), real_pdf(2))
    copy = tmp_path / "copies"
    coord = make_coord(client, copy_dir=copy)
    scan = await coord.start_scan(duplex=True)
    await _wait_for(lambda: scan.state == "awaiting-back-sides")
    await coord.async_scan_backs(scan.scan_id)
    await _drive(coord, scan)
    assert scan.state == "failed" and "3 fronts, 2 backs" in scan.error
    assert scan.to_dict()["file_url"] is None
    assert not copy.exists() and not list(coord._storage.iterdir())


async def test_manual_duplex_resume_checks_loaded_idle_feeder(make_coord, monkeypatch):
    from custom_components.escl_scan.scanner import ScannerStatus

    client = TwoPassClient(VALID_PDF, VALID_PDF)
    coord = make_coord(client)
    scan = await coord.start_scan(duplex=True)
    await _wait_for(lambda: scan.state == "awaiting-back-sides")
    for state, loaded, message in [
        ("Idle", False, "feeder is empty.*Load the back sides"),
        ("Processing", True, "scanner is busy.*Wait"),
    ]:
        async def status(state=state, loaded=loaded):
            return ScannerStatus(state=state, adf_loaded=loaded)
        monkeypatch.setattr(client, "get_scanner_status", status)
        with pytest.raises(ValueError, match=message):
            await coord.async_scan_backs(scan.scan_id)
        assert scan.state == "awaiting-back-sides" and client.create_calls == 1
    assert await coord.async_cancel(scan.scan_id)
    await _drive(coord, scan)


async def test_manual_duplex_aborted_fronts_do_not_wait(make_coord):
    client = TwoPassClient(VALID_PDF, VALID_PDF)
    client.job_state = "Aborted"
    coord = make_coord(client)
    scan = await coord.start_scan(duplex=True)
    await _drive(coord, scan)
    assert scan.state == "aborted" and client.create_calls == 1
    assert not coord._back_events and not list(coord._storage.iterdir())


async def test_start_cleans_manual_intermediates_from_abrupt_exit(make_coord):
    coord = make_coord(FakeClient(docs=[[VALID_PDF]]))
    coord._storage.mkdir()
    for suffix in ["fronts", "duplex", "rot", "partfronts0"]:
        (coord._storage / f"scan-old.pdf.{suffix}").write_bytes(b"abandoned")
    unrelated = coord._storage / "other-document.pdf.fronts"
    unrelated.write_bytes(b"leave intact")
    scan = await coord.start_scan()
    await _drive(coord, scan)
    assert scan.state == "completed"
    assert set(coord._storage.iterdir()) == {scan.file_path, unrelated}


async def test_manual_resume_cancel_race_cannot_start_another_job(make_coord, monkeypatch):
    from custom_components.escl_scan.scanner import ScannerStatus

    client = TwoPassClient(VALID_PDF, VALID_PDF)
    coord = make_coord(client)
    scan = await coord.start_scan(duplex=True)
    await _wait_for(lambda: scan.state == "awaiting-back-sides")
    checking = asyncio.Event()
    gate = asyncio.Event()

    async def status():
        checking.set()
        await gate.wait()
        return ScannerStatus(state="Idle", adf_loaded=True)

    monkeypatch.setattr(client, "get_scanner_status", status)
    resume = asyncio.create_task(coord.async_scan_backs(scan.scan_id))
    await checking.wait()
    with pytest.raises(ValueError, match="already starting"):
        await coord.async_scan_backs(scan.scan_id)
    task = coord._driver_tasks[scan.scan_id]
    assert await coord.async_cancel(scan.scan_id)
    await task
    gate.set()
    with pytest.raises(ValueError, match="no longer waiting"):
        await resume
    assert client.create_calls == 1 and not list(coord._storage.iterdir())


@pytest.mark.parametrize("shutdown", [False, True])
async def test_manual_back_job_creation_cleanup_on_cancel_or_shutdown(
    make_coord, monkeypatch, shutdown,
):
    client = TwoPassClient(VALID_PDF, VALID_PDF)
    coord = make_coord(client)
    scan = await coord.start_scan(duplex=True)
    await _wait_for(lambda: scan.state == "awaiting-back-sides")
    original_create = client.create_job
    creating = asyncio.Event()
    gate = asyncio.Event()

    async def create(**kw):
        creating.set()
        await gate.wait()
        return await original_create(**kw)

    monkeypatch.setattr(client, "create_job", create)
    await coord.async_scan_backs(scan.scan_id)
    task = coord._driver_tasks[scan.scan_id]
    await creating.wait()
    if shutdown:
        stop = asyncio.create_task(coord.async_shutdown())
        await asyncio.sleep(0)
    else:
        assert await coord.async_cancel(scan.scan_id)
    gate.set()
    if shutdown:
        await stop
    else:
        await task
    assert client.create_calls == 2
    assert client.deleted == [
        "https://scanner/eSCL/ScanJobs/j1", "https://scanner/eSCL/ScanJobs/j2",
    ]
    assert not list(coord._storage.iterdir())


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
    parts = [VALID_PDF[i:i + 64] for i in range(0, len(VALID_PDF), 64)]
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


async def test_multi_document_truncated_part_fails_entire_batch(make_coord):
    coord = make_coord(
        FakeClient(docs=[[real_pdf(1)], [b"%PDF-1.4 truncated, no trailer"]])
    )
    scan = await coord.start_scan()
    await _drive(coord, scan)
    assert scan.state == "failed"
    assert "truncated" in scan.error
    assert not scan.file_path.exists()
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


async def test_final_jobinfo_does_not_overwrite_pdf_page_count(make_coord):
    coord = make_coord(FakeClient(docs=[[VALID_PDF]], pages=5))
    scan = await coord.start_scan()
    await _drive(coord, scan)
    assert scan.state == "completed"
    assert scan.pages_done == 1


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
    coord.capability_cache._expires_at = 0
    client._docs = [[VALID_PDF]]
    scan = await coord.start_scan(source="Feeder", duplex=True)
    await _wait_for(lambda: scan.state == "awaiting-back-sides")
    assert scan.duplex is False  # requested but unsupported
    assert scan.duplex_mode == "manual"
    assert await coord.async_cancel(scan.scan_id)
    await _drive(coord, scan)


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


async def test_rotate_duplex_backs(make_coord):
    from pypdf import PdfReader

    client = FakeClient(docs=[[real_pdf(4)]], source="Feeder", caps=CAPS)
    coord = make_coord(client, default_duplex=True, rotate_duplex_backs=True)
    scan = await coord.start_scan()
    await _drive(coord, scan)
    assert scan.state == "completed"
    pages = PdfReader(str(scan.file_path)).pages
    assert [p.rotation for p in pages] == [0, 180, 0, 180]
    assert not list(coord._storage.glob("*.rot"))


async def test_no_rotation_by_default(make_coord):
    from pypdf import PdfReader

    client = FakeClient(docs=[[real_pdf(2)]], source="Feeder", caps=CAPS)
    coord = make_coord(client, default_duplex=True)
    scan = await coord.start_scan()
    await _drive(coord, scan)
    assert [p.rotation for p in PdfReader(str(scan.file_path)).pages] == [0, 0]


async def test_cancel_during_job_creation_never_revives_scan(make_coord):
    entered, release = asyncio.Event(), asyncio.Event()

    class SlowCreate(FakeClient):
        async def create_job(self, **kwargs):
            entered.set()
            await release.wait()
            return await super().create_job(**kwargs)

    client = SlowCreate(docs=[[VALID_PDF]])
    coord = make_coord(client)
    scan = await coord.start_scan()
    await entered.wait()
    assert await coord.async_cancel(scan.scan_id)
    with pytest.raises(ScanBusyError):
        await coord.start_scan()
    release.set()
    await _drive(coord, scan)
    assert scan.state == "canceled"
    assert scan.file_path is None
    assert client.deleted == [scan.job_url]


async def test_cancel_interrupts_stalled_stream_and_cleans_files(make_coord):
    client = FakeClient(hang=True)
    coord = make_coord(client)
    scan = await coord.start_scan()
    await _wait_for(lambda: bool(list(coord._storage.glob("*.part*"))))
    task = coord._driver_tasks[scan.scan_id]
    assert await coord.async_cancel(scan.scan_id)
    async with asyncio.timeout(2):
        await task
    assert scan.state == "canceled"
    assert client.deleted == [scan.job_url]
    assert not list(coord._storage.iterdir())


async def test_shutdown_cleans_scratch_and_own_server_job(make_coord):
    client = FakeClient(hang=True)
    coord = make_coord(client)
    scan = await coord.start_scan()
    await _wait_for(lambda: bool(list(coord._storage.glob("*.part*"))))
    await coord.async_shutdown()
    assert not list(coord._storage.iterdir())
    assert client.deleted == [scan.job_url]
    with pytest.raises(ScanBusyError):
        await coord.start_scan()


async def test_shutdown_interrupts_source_detection(make_coord):
    entered = asyncio.Event()

    class SlowDetect(FakeClient):
        async def detect_source(self):
            entered.set()
            await asyncio.Event().wait()

    client = SlowDetect()
    coord = make_coord(client)
    start = asyncio.create_task(coord.start_scan())
    await entered.wait()
    await coord.async_shutdown()
    assert start.cancelled()
    assert coord.current is None
    assert client.closed


@pytest.mark.parametrize("failure", ["network", "disk"])
async def test_later_document_error_fails_batch(make_coord, monkeypatch, failure):
    from custom_components.escl_scan.coordinator import _PdfFileWriter

    class BrokenStream(FakeClient):
        async def iter_next_document(self, url):
            if not self._docs:
                raise OSError("connection lost")
            async for chunk in super().iter_next_document(url):
                yield chunk

    client = BrokenStream(docs=[[real_pdf()]])
    coord = make_coord(client)
    if failure == "disk":
        original = _PdfFileWriter.open

        def fail_second(writer):
            if str(writer.path).endswith("part1"):
                raise OSError("disk full")
            original(writer)

        monkeypatch.setattr(_PdfFileWriter, "open", fail_second)
    scan = await coord.start_scan()
    await _drive(coord, scan)
    assert scan.state == "failed"
    assert not list(coord._storage.iterdir())


async def test_aborted_scan_is_not_copied(make_coord, tmp_path):
    consume = tmp_path / "consume"
    coord = make_coord(
        FakeClient(docs=[[real_pdf()]], job_state="Aborted"), copy_dir=consume
    )
    scan = await coord.start_scan()
    await _drive(coord, scan)
    assert scan.state == "aborted"
    assert scan.copied_to is None
    assert not consume.exists()
    assert not scan.file_path.exists()


async def test_file_job_finishes_worker_before_cancellation_cleanup(make_coord):
    import threading

    entered, release = threading.Event(), threading.Event()
    coord = make_coord(FakeClient())

    def operation():
        entered.set()
        assert release.wait(2)

    task = asyncio.create_task(coord._file_job(operation))
    await _wait_for(entered.is_set)
    task.cancel()
    await asyncio.sleep(0)
    assert not task.done()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task


async def test_purge_cannot_delete_new_scan_scratch_files(make_coord):
    import threading

    entered, release = threading.Event(), threading.Event()
    client = FakeClient(hang=True)
    coord = make_coord(client)
    purge = coord._ensure_storage_and_purge

    def slow_purge():
        entered.set()
        assert release.wait(2)
        return purge()

    coord._ensure_storage_and_purge = slow_purge
    sweep = asyncio.create_task(coord.async_purge_now())
    await _wait_for(entered.is_set)
    await coord.start_scan()
    assert client.create_kwargs is None
    release.set()
    await sweep
    await _wait_for(lambda: bool(list(coord._storage.glob("*.part*"))))
    await coord.async_shutdown()
    assert not list(coord._storage.iterdir())


async def test_rotate_preserves_metadata(make_coord):
    from pypdf import PdfReader, PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.add_blank_page(width=200, height=200)
    writer.add_metadata({"/Title": "Original title"})
    buf = io.BytesIO()
    writer.write(buf)
    coord = make_coord(
        FakeClient(docs=[[buf.getvalue()]], source="Feeder", caps=CAPS),
        default_duplex=True, rotate_duplex_backs=True,
    )
    scan = await coord.start_scan()
    await _drive(coord, scan)
    assert PdfReader(scan.file_path).metadata.title == "Original title"
    assert scan.bytes_written == scan.file_path.stat().st_size


async def test_capabilities_failure_backs_off_and_recovers(make_coord, monkeypatch):
    from unittest.mock import AsyncMock

    client = FakeClient()
    get_caps = AsyncMock(side_effect=OSError("unsupported endpoint"))
    monkeypatch.setattr(client, "get_capabilities", get_caps)
    coord = make_coord(client)
    assert await coord.async_refresh_capabilities() is None
    assert await coord.async_refresh_capabilities() is None
    get_caps.assert_awaited_once()
    coord.capability_cache._retry_at = 0
    get_caps.side_effect = None
    get_caps.return_value = CAPS
    assert await coord.async_refresh_capabilities() is CAPS


async def test_dpi_snap_for_duplex_feeder(make_coord):
    caps = ScannerCapabilities(
        adf_duplex=True, resolutions=[300, 600, 1200],
        source_resolutions={"FeederDuplex": [300]},
    )
    client = FakeClient(docs=[[real_pdf()]], source="Feeder", caps=caps)
    coord = make_coord(client)
    scan = await coord.start_scan(dpi=1200, duplex=True)
    await _drive(coord, scan)
    assert scan.dpi == 300
    assert client.create_kwargs["dpi"] == 300


async def test_poll_reports_pause_and_resume(make_coord, monkeypatch):
    monkeypatch.setattr("custom_components.escl_scan.coordinator.POLL_INTERVAL", 0.01)
    client = FakeClient(hang=True, job_state="ProcessingStopped")
    coord = make_coord(client)
    scan = await coord.start_scan()
    await _wait_for(lambda: scan.state == "processing-stopped")
    client.job_state = "Processing"
    await _wait_for(lambda: scan.state == "processing")


async def test_poll_abort_interrupts_stalled_document(make_coord, monkeypatch):
    monkeypatch.setattr("custom_components.escl_scan.coordinator.POLL_INTERVAL", 0.01)
    client = FakeClient(hang=True, job_state="Aborted")
    coord = make_coord(client)
    scan = await coord.start_scan()
    task = coord._driver_tasks[scan.scan_id]
    async with asyncio.timeout(2):
        await task
    assert scan.state == "aborted"
    assert not list(coord._storage.iterdir())
    assert client.deleted == [scan.job_url]


async def test_corrupt_pdf_with_header_and_eof_is_rejected(make_coord):
    coord = make_coord(FakeClient(docs=[[b"%PDF-1.4\nnot a page tree\n%%EOF\n"]]))
    scan = await coord.start_scan()
    await _drive(coord, scan)
    assert scan.state == "failed"
    assert "assemble PDF" in scan.error
    assert not scan.file_path.exists()


async def test_cancel_during_pdf_assembly_waits_and_removes_output(make_coord, monkeypatch):
    import threading

    from custom_components.escl_scan import coordinator as module

    entered, release = threading.Event(), threading.Event()
    original = module._count_pdf_pages

    def delayed_count(path):
        entered.set()
        assert release.wait(2)
        return original(path)

    monkeypatch.setattr(module, "_count_pdf_pages", delayed_count)
    coord = make_coord(FakeClient(docs=[[VALID_PDF]]))
    scan = await coord.start_scan()
    task = coord._driver_tasks[scan.scan_id]
    await _wait_for(entered.is_set)
    assert await coord.async_cancel(scan.scan_id)
    release.set()
    await task
    assert scan.state == "canceled"
    assert not list(coord._storage.iterdir())


async def test_cancel_is_too_late_once_folder_publication_begins(make_coord, tmp_path, monkeypatch):
    import threading

    from custom_components.escl_scan import coordinator as module

    entered, release = threading.Event(), threading.Event()
    original = module._copy_into

    def delayed_copy(src, directory):
        entered.set()
        assert release.wait(2)
        return original(src, directory)

    monkeypatch.setattr(module, "_copy_into", delayed_copy)
    coord = make_coord(FakeClient(docs=[[VALID_PDF]]), copy_dir=tmp_path / "consume")
    scan = await coord.start_scan()
    await _wait_for(entered.is_set)
    assert not await coord.async_cancel(scan.scan_id)
    release.set()
    await _drive(coord, scan)
    assert scan.state == "completed"
    assert scan.copied_to.exists()


async def test_failed_copy_removes_its_temporary_file(make_coord, tmp_path, monkeypatch):
    from custom_components.escl_scan import coordinator as module

    def failed_copy(src, dest):
        dest.write_bytes(b"partial copy")
        raise OSError("disk full")

    monkeypatch.setattr(module.shutil, "copyfile", failed_copy)
    consume = tmp_path / "consume"
    coord = make_coord(FakeClient(docs=[[VALID_PDF]]), copy_dir=consume)
    scan = await coord.start_scan()
    await _drive(coord, scan)
    assert scan.state == "completed"
    assert scan.copied_to is None
    assert not list(consume.iterdir())


async def test_shutdown_waits_for_running_purge_worker(make_coord):
    import threading

    entered, release = threading.Event(), threading.Event()
    coord = make_coord(FakeClient())
    original = coord._ensure_storage_and_purge

    def delayed_purge():
        entered.set()
        assert release.wait(2)
        return original()

    coord._ensure_storage_and_purge = delayed_purge
    purge = asyncio.create_task(coord.async_purge_now())
    await _wait_for(entered.is_set)
    shutdown = asyncio.create_task(coord.async_shutdown())
    await asyncio.sleep(0)
    assert not shutdown.done()
    release.set()
    await shutdown
    assert purge.cancelled()
    assert not coord._purge_tasks


async def test_shutdown_recovers_job_location_from_inflight_post(make_coord):
    entered, release = asyncio.Event(), asyncio.Event()

    class SlowCreate(FakeClient):
        async def create_job(self, **kwargs):
            entered.set()
            await release.wait()
            return await super().create_job(**kwargs)

    client = SlowCreate()
    coord = make_coord(client)
    scan = await coord.start_scan()
    await entered.wait()
    shutdown = asyncio.create_task(coord.async_shutdown())
    await asyncio.sleep(0)
    assert not shutdown.done()
    release.set()
    await shutdown
    assert client.deleted == [scan.job_url]
    assert client.closed
    assert not coord._driver_tasks


async def test_merge_preserves_content_streams_after_inputs_close(make_coord):
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import DecodedStreamObject, NameObject

    docs = []
    expected = [b"q 1 0 0 1 10 20 cm Q\n", b"q 1 0 0 1 30 40 cm Q\n"]
    for content in expected:
        writer = PdfWriter()
        page = writer.add_blank_page(width=200, height=200)
        stream = DecodedStreamObject()
        stream.set_data(content)
        page[NameObject("/Contents")] = writer._add_object(stream)
        buf = io.BytesIO()
        writer.write(buf)
        docs.append([buf.getvalue()])
    coord = make_coord(FakeClient(docs=docs))
    scan = await coord.start_scan()
    await _drive(coord, scan)
    assert scan.state == "completed"
    pages = PdfReader(scan.file_path).pages
    assert [page.get_contents().get_data() for page in pages] == expected


async def test_capability_refresh_cannot_change_region_between_manual_passes(make_coord):
    client = TwoPassClient(marked_pdf([101]), marked_pdf([201]))
    client.caps = ScannerCapabilities(adf_max=(2550, 3300))
    coord = make_coord(client)
    scan = await coord.start_scan(duplex=True)
    await _wait_for(lambda: scan.state == "awaiting-back-sides")
    assert scan.region == (2550, 3300)
    assert client.create_kwargs["height"] == 3300
    client.caps = ScannerCapabilities(adf_max=(2550, 4200))
    coord.capability_cache._expires_at = 0
    await coord.async_refresh_capabilities()
    await coord.async_scan_backs(scan.scan_id)
    await _drive(coord, scan)
    assert scan.state == "completed"
    assert client.create_kwargs["height"] == 3300
