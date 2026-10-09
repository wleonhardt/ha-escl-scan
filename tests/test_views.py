"""HTTP views: auth, input validation, status precedence."""
import asyncio
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.escl_scan.const import CONF_HOST, CONF_USE_TLS, DOMAIN

from .fakes import FakeClient
from .test_coordinator import VALID_PDF, _wait_for


async def _noop_reap(*args, **kwargs):
    return None


@pytest.fixture
async def api(hass, hass_client):
    client = FakeClient(docs=[[VALID_PDF]])
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "192.0.2.10", CONF_USE_TLS: False})
    entry.add_to_hass(hass)
    with (
        patch("custom_components.escl_scan._sync_lovelace_resources", _noop_reap),
        patch("custom_components.escl_scan.ScannerClient", return_value=client),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        http = await hass_client()
        coord = hass.data[DOMAIN][entry.entry_id]["coordinator"]
        yield http, client, coord
        await coord.async_shutdown()
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_views_require_auth(hass, hass_client_no_auth, api):
    anon = await hass_client_no_auth()
    assert (await anon.post("/api/escl_scan/start", json={})).status == 401
    assert (await anon.post("/api/escl_scan/cancel", json={"scan_id": "x"})).status == 401
    assert (await anon.get("/api/escl_scan/file/x")).status == 401
    assert (await anon.post("/api/escl_scan/scan_backs", json={"scan_id": "x"})).status == 401


async def test_manual_duplex_views_reject_early_download_and_stale_resume(api):
    http, client, coord = api
    assert (await http.post("/api/escl_scan/scan_backs", json=[])).status == 400
    for invalid in ["false", 1, None]:
        assert (await http.post("/api/escl_scan/scan_backs", json={
            "scan_id": "missing", "reverse_back_order": invalid,
        })).status == 400
    assert (await http.post("/api/escl_scan/scan_backs", data="bad")).status == 400
    assert (await http.post("/api/escl_scan/scan_backs", json={"scan_id": "missing"})).status == 404
    response = await http.post("/api/escl_scan/start", json={"source": "Feeder", "duplex": True})
    data = await response.json()
    assert data["duplex_mode"] == "manual" and not data["duplex"]
    scan = coord.get(data["scan_id"])
    await _wait_for(lambda: scan.state == "awaiting-back-sides")
    assert (await http.get(f"/api/escl_scan/file/{scan.scan_id}")).status == 409
    blocked = await http.post("/api/escl_scan/start", json={})
    assert blocked.status == 409
    assert "Scan back sides" in (await blocked.json())["message"]
    client._docs = [[VALID_PDF]]
    back_response = await http.post("/api/escl_scan/scan_backs", json={
        "scan_id": scan.scan_id, "reverse_back_order": True,
    })
    assert back_response.status == 200
    assert scan.reverse_back_order
    await coord._driver_tasks[scan.scan_id]
    assert scan.state == "completed" and scan.pages_done == 2
    stale_response = await http.post("/api/escl_scan/scan_backs", json={"scan_id": scan.scan_id})
    assert stale_response.status == 409
    assert (await http.get(f"/api/escl_scan/file/{scan.scan_id}")).status == 200


async def test_start_validates_body(api):
    http, _, _ = api
    assert (await http.post("/api/escl_scan/start", json={"source": "Tray"})).status == 400
    assert (await http.post("/api/escl_scan/start", json={"dpi": 0})).status == 400
    assert (await http.post("/api/escl_scan/start", json={"dpi": "300"})).status == 400
    assert (await http.post("/api/escl_scan/start", json={"color": "sepia"})).status == 400
    assert (await http.post("/api/escl_scan/start", json={"duplex": "yes"})).status == 400
    assert (await http.post("/api/escl_scan/start", json={"dpi": True})).status == 400
    assert (await http.post("/api/escl_scan/start", json={"dpi": 49})).status == 400
    assert (await http.post("/api/escl_scan/start", data=b"invalid JSON")).status == 400
    assert (await http.post("/api/escl_scan/start", json=[])).status == 400


async def test_start_accepts_empty_body(api):
    http, _, _ = api
    assert (await http.post("/api/escl_scan/start")).status == 200


@pytest.mark.parametrize("state, guidance", [
    (None, "starting or reconnecting"),
    ("processing", "Wait for it to finish, or cancel"),
    ("canceled", "previous scan is finishing"),
])
async def test_start_conflict_explains_next_step(api, state, guidance):
    from datetime import UTC, datetime
    from unittest.mock import AsyncMock

    from custom_components.escl_scan.coordinator import ScanBusyError, TrackedScan

    http, _, coord = api
    if state:
        coord._current = TrackedScan(
            scan_id="existing", source="Feeder", dpi=300, color="color",
            submitted_at=datetime.now(UTC), state=state,
        )
    with patch.object(coord, "start_scan", AsyncMock(side_effect=ScanBusyError("busy"))):
        response = await http.post("/api/escl_scan/start", json={"duplex": True})
    assert response.status == 409
    assert guidance in (await response.json())["message"]


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


@pytest.mark.parametrize("path", ["start", "cancel", "scan_backs"])
async def test_explicit_target_rejects_foreign_sensor_without_device_io(api, path):
    http, client, coord = api
    with patch.object(coord, "start_scan") as start:
        response = await http.post(f"/api/escl_scan/{path}", json={
            "entity_id": "sensor.foreign", "scan_id": "some-scan",
        })
        assert response.status == 404
        assert "Select a scan sensor" in (await response.json())["message"]
        start.assert_not_called()


async def test_explicit_registered_sensor_routes_start(hass, api):
    from homeassistant.helpers import entity_registry as er

    http, _, coord = api
    sensors = [e for e in er.async_get(hass).entities.values()
               if e.platform == DOMAIN and e.domain == "sensor"]
    assert len(sensors) == 1
    response = await http.post("/api/escl_scan/start", json={"entity_id": sensors[0].entity_id})
    assert response.status == 200
    assert coord.get((await response.json())["scan_id"]) is not None
