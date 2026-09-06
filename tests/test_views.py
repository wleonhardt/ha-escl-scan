"""HTTP views: auth, input validation, status precedence."""
import asyncio
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.escl_scan.const import CONF_HOST, CONF_USE_TLS, DOMAIN

from .fakes import FakeClient
from .test_coordinator import VALID_PDF


async def _noop_reap(*args, **kwargs):
    return None


@pytest.fixture
async def api(hass, hass_client):
    client = FakeClient(docs=[[VALID_PDF]])
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "192.0.2.10", CONF_USE_TLS: False})
    entry.add_to_hass(hass)
    with (
        patch("custom_components.escl_scan._reap_lovelace_resources", _noop_reap),
        patch("custom_components.escl_scan.ScannerClient", return_value=client),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        http = await hass_client()
        coord = hass.data[DOMAIN][entry.entry_id]["coordinator"]
        yield http, client, coord
        for task in list(coord._driver_tasks.values()):
            await task
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_views_require_auth(hass, hass_client_no_auth, api):
    anon = await hass_client_no_auth()
    assert (await anon.post("/api/escl_scan/start", json={})).status == 401
    assert (await anon.post("/api/escl_scan/cancel", json={"scan_id": "x"})).status == 401
    assert (await anon.get("/api/escl_scan/file/x")).status == 401


async def test_start_validates_body(api):
    http, _, _ = api
    assert (await http.post("/api/escl_scan/start", json={"source": "Tray"})).status == 400
    assert (await http.post("/api/escl_scan/start", json={"dpi": 0})).status == 400
    assert (await http.post("/api/escl_scan/start", json={"dpi": "300"})).status == 400
    assert (await http.post("/api/escl_scan/start", json={"color": "sepia"})).status == 400
    assert (await http.post("/api/escl_scan/start", json={"duplex": "yes"})).status == 400


async def test_start_then_file_download(api):
    http, _, coord = api
    resp = await http.post("/api/escl_scan/start", json={"color": "gray"})
    assert resp.status == 200
    body = await resp.json()
    assert body["ok"] and body["color"] == "gray" and body["state"] == "pending"
    sid = body["scan_id"]
    for task in list(coord._driver_tasks.values()):
        await task
    resp = await http.get(f"/api/escl_scan/file/{sid}")
    assert resp.status == 200
    assert resp.headers["Content-Type"].startswith("application/pdf")
    assert await resp.read() == VALID_PDF


async def test_start_conflict_while_running(api):
    http, client, coord = api
    client._gate = asyncio.Event()
    assert (await http.post("/api/escl_scan/start", json={})).status == 200
    assert (await http.post("/api/escl_scan/start", json={})).status == 409
    client._gate.set()


async def test_cancel_validation_and_precedence(api):
    http, client, coord = api
    assert (await http.post("/api/escl_scan/cancel", data=b"not json")).status == 400
    assert (await http.post("/api/escl_scan/cancel", json={})).status == 400
    assert (await http.post("/api/escl_scan/cancel", json={"scan_id": "nope"})).status == 404

    client._gate = asyncio.Event()
    sid = (await (await http.post("/api/escl_scan/start", json={})).json())["scan_id"]
    assert (await http.post("/api/escl_scan/cancel", json={"scan_id": sid})).status == 200
    # already terminal
    assert (await http.post("/api/escl_scan/cancel", json={"scan_id": sid})).status == 409
    client._gate.set()


async def test_file_precedence_404_409(api):
    http, client, coord = api
    assert (await http.get("/api/escl_scan/file/unknown")).status == 404
    client._gate = asyncio.Event()
    sid = (await (await http.post("/api/escl_scan/start", json={})).json())["scan_id"]
    assert (await http.get(f"/api/escl_scan/file/{sid}")).status == 409  # not ready
    client._gate.set()
    for task in list(coord._driver_tasks.values()):
        await task
    coord.get(sid).file_path.unlink()  # simulate TTL purge
    assert (await http.get(f"/api/escl_scan/file/{sid}")).status == 404
