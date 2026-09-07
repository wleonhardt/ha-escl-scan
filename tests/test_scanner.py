"""ScannerClient tests against a real local aiohttp server. Covers the P2
session-reuse fix, chunked streaming integrity, and response release.
"""
from aiohttp import web
import pytest

from custom_components.escl_scan.scanner import ScannerClient

VALID_PDF = b"%PDF-1.4\n" + b"z" * (300_000) + b"\n%%EOF\n"

STATUS_XML = (
    b'<ScannerStatus><State>Idle</State>'
    b'<AdfState>ScannerAdfLoaded</AdfState></ScannerStatus>'
)
JOBINFO_XML = (
    b'<ScanJob><JobState>Completed</JobState>'
    b'<ImagesCompleted>1</ImagesCompleted></ScanJob>'
)


class _Backend:
    def __init__(self):
        self.next_calls = 0
        self.peernames = set()
        self.create_calls = 0
        self.deleted = []
        # Scripted NextDocument statuses before the real document arrives.
        self.next_prelude = []
        self.job_state = b"Completed"
        self.scanner_state = b"Idle"
        self.create_status = 201


@pytest.fixture
async def scanner(aiohttp_server, socket_enabled):
    # socket_enabled: HA's test harness blocks real sockets by default; this
    # suite talks to a genuine loopback aiohttp server on purpose.
    backend = _Backend()

    async def status(request):
        backend.peernames.add(request.transport.get_extra_info("peername"))
        hook = getattr(backend, "on_status", None)
        if hook:
            await hook()
        return web.Response(
            body=b"<ScannerStatus><State>" + backend.scanner_state + b"</State>"
            b"<AdfState>ScannerAdfLoaded</AdfState>"
            b"<Jobs><JobInfo><JobUri>/eSCL/ScanJobs/stale</JobUri></JobInfo></Jobs>"
            b"</ScannerStatus>"
        )

    async def create(request):
        backend.create_calls += 1
        await request.read()
        if backend.create_status != 201:
            return web.Response(status=backend.create_status)
        return web.Response(status=201, headers={"Location": "/eSCL/ScanJobs/j1"})

    async def jobinfo(request):
        return web.Response(
            body=b"<ScanJob><JobState>" + backend.job_state + b"</JobState>"
            b"<ImagesCompleted>1</ImagesCompleted></ScanJob>"
        )

    async def nextdoc(request):
        if backend.next_prelude:
            return web.Response(status=backend.next_prelude.pop(0))
        backend.next_calls += 1
        if backend.next_calls == 1:
            resp = web.StreamResponse(status=200)
            resp.content_type = "application/pdf"
            await resp.prepare(request)
            for i in range(0, len(VALID_PDF), 64_000):
                await resp.write(VALID_PDF[i:i + 64_000])
            await resp.write_eof()
            return resp
        raise web.HTTPNotFound()

    async def delete(request):
        backend.deleted.append(request.match_info["jid"])
        hook = getattr(backend, "on_delete", None)
        if hook:
            await hook()
        return web.Response(status=200)

    app = web.Application()
    app.add_routes([
        web.get("/eSCL/ScannerStatus", status),
        web.post("/eSCL/ScanJobs", create),
        web.get("/eSCL/ScanJobs/{jid}", jobinfo),
        web.get("/eSCL/ScanJobs/{jid}/NextDocument", nextdoc),
        web.delete("/eSCL/ScanJobs/{jid}", delete),
    ])
    server = await aiohttp_server(app)
    client = ScannerClient(host="127.0.0.1", port=server.port, use_tls=False)
    client._backend = backend  # stash for assertions
    yield client
    await client.async_close()


async def test_session_is_reused(scanner):
    s1 = await scanner._session()
    s2 = await scanner._session()
    assert s1 is s2


async def test_status_and_detect_source(scanner):
    st = await scanner.get_scanner_status()
    assert st.state == "Idle" and st.adf_loaded
    assert await scanner.detect_source() == "Feeder"


async def test_create_job_returns_absolute_url(scanner):
    url = await scanner.create_job(source="Platen", dpi=300, color="color")
    assert url.endswith("/eSCL/ScanJobs/j1")
    assert url.startswith("http://127.0.0.1:")


async def test_stream_document_intact(scanner):
    url = await scanner.create_job(source="Platen", dpi=300, color="color")
    buf = bytearray()
    async for chunk in scanner.iter_next_document(url):
        buf.extend(chunk)
    assert bytes(buf) == VALID_PDF


async def test_second_document_yields_nothing(scanner):
    url = await scanner.create_job(source="Platen", dpi=300, color="color")
    async for _ in scanner.iter_next_document(url):
        pass
    chunks = [c async for c in scanner.iter_next_document(url)]
    assert chunks == []


async def test_job_info_and_delete(scanner):
    info = await scanner.get_job_info(_url(scanner))
    assert info.state == "Completed"
    assert await scanner.delete_job(_url(scanner)) is True


async def test_many_calls_reuse_one_connection(scanner):
    for _ in range(8):
        await scanner.get_scanner_status()
    # keep-alive pooling: all requests over a single client connection
    assert len(scanner._backend.peernames) == 1


async def test_close_then_rebuild(scanner):
    await scanner.get_scanner_status()
    await scanner.async_close()
    assert scanner._session_obj is None
    st = await scanner.get_scanner_status()
    assert st.state == "Idle"


async def test_next_document_retries_503_while_job_alive(scanner, monkeypatch):
    # Per-page ADF scanners answer 503 while the next sheet feeds; keep
    # retrying while JobInfo says Processing, then stream the document.
    monkeypatch.setattr("custom_components.escl_scan.scanner.asyncio.sleep", _no_sleep)
    scanner._backend.job_state = b"Processing"
    scanner._backend.next_prelude = [503, 503, 500]
    buf = bytearray()
    async for chunk in scanner.iter_next_document(_url(scanner)):
        buf.extend(chunk)
    assert bytes(buf) == VALID_PDF


async def test_next_document_503_on_terminal_job_means_done(scanner):
    # HP: 503 after the last page with JobInfo already Completed → stop.
    scanner._backend.next_prelude = [503]
    chunks = [c async for c in scanner.iter_next_document(_url(scanner))]
    assert chunks == []
    assert scanner._backend.next_calls == 0


async def test_create_job_503_purges_stale_jobs_when_idle(scanner):
    scanner._backend.create_status = 503

    # First POST 503s; purge (device Idle) deletes the stale job; retry succeeds.
    async def flip(*_):
        scanner._backend.create_status = 201
    scanner._backend.on_delete = flip
    url = await scanner.create_job(source="Platen", dpi=300, color="color")
    assert url.endswith("/ScanJobs/j1")
    assert scanner._backend.deleted == ["stale"]
    assert scanner._backend.create_calls == 2


async def test_create_job_503_on_busy_device_never_deletes(scanner, monkeypatch):
    monkeypatch.setattr("custom_components.escl_scan.scanner.SCANNER_IDLE_WAIT_SECONDS", 0.0)
    scanner._backend.create_status = 503
    scanner._backend.scanner_state = b"Processing"
    with pytest.raises(RuntimeError, match="busy"):
        await scanner.create_job(source="Platen", dpi=300, color="color")
    assert scanner._backend.deleted == []
    assert scanner._backend.create_calls == 1


async def test_create_job_503_waits_for_idle_after_cancel(scanner, monkeypatch):
    # Live HP behaviour: right after a cancel the device 503s ScanJobs and
    # reports Processing for a few seconds, then goes Idle. We must wait,
    # not fail with "busy".
    monkeypatch.setattr("custom_components.escl_scan.scanner.asyncio.sleep", _no_sleep)
    b = scanner._backend
    b.create_status = 503
    b.scanner_state = b"Processing"
    polls = {"n": 0}
    orig_status = b.scanner_state

    async def flip_after_polls():
        polls["n"] += 1
        if polls["n"] >= 3:
            b.scanner_state = b"Idle"
            b.create_status = 201
    b.on_status = flip_after_polls
    url = await scanner.create_job(source="Platen", dpi=300, color="color")
    assert url.endswith("/ScanJobs/j1")
    assert b.deleted == ["stale"]  # idle → stale slot purged before retry
    assert b.create_calls == 2
    assert orig_status == b"Processing" and polls["n"] >= 3


async def _no_sleep(_seconds):
    return None


def _url(scanner):
    return f"{scanner.base_url}/ScanJobs/j1"
