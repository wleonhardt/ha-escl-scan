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


@pytest.fixture
async def scanner(aiohttp_server, socket_enabled):
    # socket_enabled: HA's test harness blocks real sockets by default; this
    # suite talks to a genuine loopback aiohttp server on purpose.
    backend = _Backend()

    async def status(request):
        backend.peernames.add(request.transport.get_extra_info("peername"))
        return web.Response(body=STATUS_XML)

    async def create(request):
        backend.create_calls += 1
        await request.read()
        return web.Response(status=201, headers={"Location": "/eSCL/ScanJobs/j1"})

    async def jobinfo(request):
        return web.Response(body=JOBINFO_XML)

    async def nextdoc(request):
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


def _url(scanner):
    return f"{scanner.base_url}/ScanJobs/j1"
