"""ScannerClient tests against a real local aiohttp server. Covers the P2
session-reuse fix, chunked streaming integrity, and response release.
"""
from unittest.mock import AsyncMock, patch

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
        self.adf_state = b"ScannerAdfLoaded"
        self.create_status = 201
        self.jobinfo_404 = False  # HP: GET ScanJobs/{uuid} is always 404
        self.status_images = b"1"


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
        if location := getattr(backend, "redirect_url", None):
            raise web.HTTPFound(location)
        if hasattr(backend, "status_body"):
            return web.Response(body=backend.status_body)
        return web.Response(
            body=b"<ScannerStatus><State>" + backend.scanner_state + b"</State>"
            b"<AdfState>" + backend.adf_state + b"</AdfState>"
            b"<Jobs><JobInfo><JobUri>/eSCL/ScanJobs/stale</JobUri></JobInfo>"
            b"<JobInfo><JobUri>/eSCL/ScanJobs/j1</JobUri>"
            b"<ImagesCompleted>" + backend.status_images + b"</ImagesCompleted>"
            b"<JobState>" + backend.job_state + b"</JobState></JobInfo></Jobs>"
            b"</ScannerStatus>"
        )

    async def create(request):
        backend.create_calls += 1
        backend.settings = await request.read()
        if backend.create_status != 201:
            return web.Response(status=backend.create_status)
        return web.Response(status=201, headers={"Location": "/eSCL/ScanJobs/j1"})

    async def jobinfo(request):
        if backend.jobinfo_404:
            raise web.HTTPNotFound()
        return web.Response(
            body=b"<ScanJob><JobState>" + backend.job_state + b"</JobState>"
            b"<ImagesCompleted>1</ImagesCompleted></ScanJob>"
        )

    async def nextdoc(request):
        backend.next_query = dict(request.query)
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
        web.get("/redirected-status", lambda request: web.Response(body=STATUS_XML)),
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


@pytest.mark.parametrize("status", [404, 410])
async def test_xerox_transient_missing_document_does_not_end_batch(scanner, status):
    scanner.quirks = ("retry_missing_document",)
    scanner._backend.next_prelude = [status]
    scanner._backend.job_state = b"Processing"
    with patch("custom_components.escl_scan.scanner.asyncio.sleep", AsyncMock()):
        url = scanner.base_url + "/ScanJobs/j1"
        data = b"".join([chunk async for chunk in scanner.iter_next_document(url)])
    assert data == VALID_PDF
    scanner._backend.job_state = b"Completed"
    assert not [chunk async for chunk in scanner.iter_next_document(url)]


async def test_xerox_retry_deadline_is_failure_not_partial_success(scanner, monkeypatch):
    scanner.quirks = ("retry_missing_document",)
    scanner._backend.next_prelude = [404]
    scanner._backend.job_state = b"Processing"
    monkeypatch.setattr("custom_components.escl_scan.scanner.NEXT_DOCUMENT_RETRY_SECONDS", 0)
    with pytest.raises(TimeoutError):
        _ = [chunk async for chunk in scanner.iter_next_document(scanner.base_url + "/ScanJobs/j1")]


async def test_ricoh_status_probe_precedes_document(scanner):
    scanner.quirks = ("status_before_load",)
    with patch.object(scanner, "get_scanner_status", AsyncMock()) as status:
        _ = [chunk async for chunk in scanner.iter_next_document(scanner.base_url + "/ScanJobs/j1")]
        status.assert_awaited_once()


async def test_status_and_detect_source(scanner):
    st = await scanner.get_scanner_status()
    assert st.state == "Idle" and st.adf_loaded
    assert await scanner.detect_source() == "Feeder"


async def test_create_job_returns_absolute_url(scanner):
    url = await scanner.create_job(source="Platen", dpi=300, color="color")
    assert url.endswith("/eSCL/ScanJobs/j1")
    assert url.startswith("http://127.0.0.1:")


@pytest.mark.parametrize(("state", "adf", "source", "message"), [
    (b"Idle", b"ScannerAdfEmpty", "Feeder", "The feeder is empty. Load the pages"),
    (b"Processing", b"ScannerAdfEmpty", "Feeder", "The scanner is busy or needs attention"),
    (b"Idle", b"", "Feeder", "The scanner could not start. Check its screen"),
    (b"Idle", b"ScannerAdfLoaded", "Feeder", "The scanner could not start. Check its screen"),
    (b"Idle", b"ScannerAdfEmpty", "Platen", "The scanner could not start. Check its screen"),
])
async def test_create_conflict_explains_status_without_retry_or_delete(
    scanner, state, adf, source, message,
):
    backend = scanner._backend
    backend.create_status = 409
    backend.scanner_state = state
    backend.adf_state = adf
    with pytest.raises(RuntimeError, match=message):
        await scanner.create_job(source=source, dpi=300, color="gray")
    assert backend.create_calls == 1
    assert backend.deleted == []


async def test_create_conflict_status_failure_keeps_safe_guidance(scanner):
    scanner._backend.create_status = 409
    with patch.object(scanner, "get_scanner_status", side_effect=TimeoutError), pytest.raises(
        RuntimeError, match="The scanner could not start. Check its screen"
    ):
        await scanner.create_job(source="Feeder", dpi=300, color="gray")
    assert scanner._backend.create_calls == 1
    assert scanner._backend.deleted == []


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


async def test_job_info_falls_back_to_scanner_status(scanner):
    # HP behaviour: job endpoint 404s; ScannerStatus/Jobs carries the info.
    b = scanner._backend
    b.jobinfo_404 = True
    b.job_state = b"Processing"
    b.status_images = b"2"
    info = await scanner.get_job_info(_url(scanner))
    assert info is not None and info.state == "Processing" and info.pages_completed == 2
    assert await scanner.get_job_info(f"{scanner.base_url}/ScanJobs/unknown") is None


async def test_next_document_503_retries_using_status_fallback(scanner, monkeypatch):
    # With the job endpoint 404ing, a 503 between ADF sheets must still be
    # read as "job alive" via ScannerStatus, not as "job gone".
    monkeypatch.setattr("custom_components.escl_scan.scanner.asyncio.sleep", _no_sleep)
    b = scanner._backend
    b.jobinfo_404 = True
    b.job_state = b"Processing"
    b.next_prelude = [503, 503]
    buf = bytearray()
    async for chunk in scanner.iter_next_document(_url(scanner)):
        buf.extend(chunk)
    assert bytes(buf) == VALID_PDF


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


@pytest.mark.parametrize(("host", "port", "tls", "origin"), [
    ("scanner", 443, False, "http://scanner:443"),
    ("scanner", 80, True, "https://scanner:80"),
    ("2001:db8::1", 8080, False, "http://[2001:db8::1]:8080"),
    ("[2001:db8::1]", 443, True, "https://[2001:db8::1]"),
])
def test_origin_keeps_nondefault_port_and_formats_ipv6(host, port, tls, origin):
    assert ScannerClient(host=host, port=port, use_tls=tls).origin == origin


@pytest.mark.parametrize("uri", [
    "http://other-host/eSCL/ScanJobs/j1", "//other-host/eSCL/ScanJobs/j1",
    "http://scanner:8080/eSCL/ScanJobs/j1", "https://scanner/eSCL/ScanJobs/j1",
    "http://user@scanner/eSCL/ScanJobs/j1",
    "/admin/reset", "../reset",
])
def test_job_uri_cannot_escape_scanner_job_endpoint(uri):
    client = ScannerClient(host="scanner", use_tls=False, port=80)
    with pytest.raises(ValueError):
        client._absolute(uri)


def test_job_uri_resolves_relative_and_absolute_paths():
    client = ScannerClient(host="scanner", use_tls=False, port=80)
    for uri in ("ScanJobs/j1", "/eSCL/ScanJobs/j1", "http://scanner/eSCL/ScanJobs/j1"):
        assert client._absolute(uri) == "http://scanner/eSCL/ScanJobs/j1"


@pytest.mark.parametrize(("tls", "port", "uri"), [
    (False, 80, "http://scanner:80/eSCL/ScanJobs/j1"),
    (True, 443, "https://scanner:443/eSCL/ScanJobs/j1"),
])
def test_job_and_redirect_origin_accept_explicit_default_ports(tls, port, uri):
    from yarl import URL

    client = ScannerClient(host="scanner", use_tls=tls, port=port)
    assert client._is_scanner_origin(URL(uri))
    assert client._absolute(uri) == uri.replace(f":{port}/", "/")


async def test_document_retry_deadline_is_failure_not_end_of_batch(scanner, monkeypatch):
    monkeypatch.setattr("custom_components.escl_scan.scanner.NEXT_DOCUMENT_RETRY_SECONDS", 0)
    scanner._backend.job_state = b"Processing"
    scanner._backend.next_prelude = [503]
    with pytest.raises(TimeoutError, match="deadline"):
        _ = [chunk async for chunk in scanner.iter_next_document(_url(scanner))]


async def test_document_url_preserves_job_query_parameters(scanner):
    chunks = [chunk async for chunk in scanner.iter_next_document(_url(scanner) + "?key=value")]
    assert b"".join(chunks) == VALID_PDF
    assert scanner._backend.next_query == {"key": "value"}


async def test_redirect_cannot_forward_credentials_to_other_origin(scanner, aiohttp_server):
    seen = []

    async def collect(request):
        seen.append(request.headers.get("Authorization"))
        return web.Response(body=STATUS_XML)

    app = web.Application()
    app.router.add_get("/collect", collect)
    other = await aiohttp_server(app)
    scanner._password = "scanner-secret"
    scanner._backend.redirect_url = str(other.make_url("/collect"))
    with pytest.raises(ValueError, match="outside its origin"):
        await scanner.get_scanner_status()
    assert seen == []


async def test_redirect_within_scanner_origin_is_supported(scanner):
    scanner._backend.redirect_url = scanner.origin + "/redirected-status"
    assert (await scanner.get_scanner_status()).is_idle


@pytest.mark.parametrize("oversized", [False, True])
async def test_capability_response_is_bounded(aiohttp_server, socket_enabled, oversized):
    async def caps(request):
        body = b"x" * (1024 * 1024 + 1) if oversized else (
            b"<ScannerCapabilities><MakeAndModel>Test</MakeAndModel></ScannerCapabilities>"
        )
        return web.Response(body=body)

    app = web.Application()
    app.router.add_get("/eSCL/ScannerCapabilities", caps)
    server = await aiohttp_server(app)
    client = ScannerClient(host=server.host, port=server.port, use_tls=False)
    try:
        if oversized:
            with pytest.raises(ValueError, match="1 MiB"):
                await client.get_capabilities()
        else:
            assert (await client.get_capabilities()).make_and_model == "Test"
    finally:
        await client.async_close()


async def test_brother_delay_is_feeder_only_and_cancellable(scanner, monkeypatch):
    import asyncio
    scanner.quirks = ("next_page_delay",)
    scanner._next_page_at = asyncio.get_running_loop().time() + 60
    scanner._feeder_job = False
    # Glass never incurs the Brother inter-page workaround.
    assert b"".join([part async for part in scanner.iter_next_document(_url(scanner))]) == VALID_PDF
    scanner._feeder_job = True
    scanner._next_page_at = asyncio.get_running_loop().time() + 60
    waiting = asyncio.Event()
    async def delay(seconds):
        assert seconds > 0
        waiting.set()
        await asyncio.Event().wait()
    monkeypatch.setattr("custom_components.escl_scan.scanner.asyncio.sleep", delay)
    async def consume():
        return [part async for part in scanner.iter_next_document(_url(scanner))]
    task = asyncio.create_task(consume())
    await waiting.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    monkeypatch.undo()


@pytest.mark.parametrize("extension", [False, True])
async def test_scan_ticket_uses_standard_format_and_only_requested_extension(scanner, extension):
    from xml.etree import ElementTree as ET
    await scanner.create_job(source="Platen", color="gray", dpi=300,
                             document_format="image/png", format_extension=extension,
                             width=1000, height=2000, x_offset=20, y_offset=30)
    root = ET.fromstring(scanner._backend.settings)
    standard = root.find(".//{http://www.pwg.org/schemas/2010/12/sm}DocumentFormat")
    assert standard is not None and standard.text == "image/png"
    values = {el.tag.rsplit("}", 1)[-1]: el.text for el in root.iter()}
    assert ("DocumentFormatExt" in values) == extension
    assert values["XOffset"] == "20" and values["YOffset"] == "30"


@pytest.mark.parametrize("body", [b"<html>Login</html>", b"x" * (1024 * 1024 + 1)],
                         ids=["html", "oversized"])
async def test_status_rejects_non_protocol_or_oversized_responses(scanner, body):
    client, backend = scanner, scanner._backend
    backend.status_body = body
    with pytest.raises(ValueError):
        await client.get_scanner_status()
    assert backend.create_calls == 0
    assert backend.deleted == []
