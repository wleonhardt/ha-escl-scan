"""Capabilities are bounded, source-specific and readable without an active scan."""
from unittest.mock import AsyncMock, patch

from custom_components.escl_scan.scanner import parse_scanner_capabilities

from . import test_views
from .test_parsers import CAPS_XML

scan_api = test_views.api

async def test_read_only_user_can_read_capabilities(
    scan_api, hass_client, hass_read_only_access_token,
):
    http = await hass_client(hass_read_only_access_token)
    assert (await http.get("/api/escl_scan/capabilities")).status == 200


async def test_unknown_capabilities_remain_unknown(scan_api):
    http, client, coord = scan_api
    coord.capability_cache.value = None
    coord.capability_cache._expires_at = coord.capability_cache._retry_at = 0
    with patch.object(client, "get_capabilities", AsyncMock(side_effect=OSError("offline"))):
        body = await (await http.get("/api/escl_scan/capabilities")).json()
    assert body["status"] == "unknown"
    assert body["supported"] == {
        "sources": None, "automatic_duplex": None, "manual_duplex": None, "profiles": {},
    }


async def test_idle_capabilities_resolve_sensor_and_preserve_source_unknowns(scan_api):
    http, client, coord = scan_api
    client.caps = parse_scanner_capabilities(CAPS_XML)
    coord.capability_cache._expires_at = 0
    coord.capability_cache._retry_at = 0
    with patch.object(client, "get_capabilities", AsyncMock(return_value=client.caps)) as fetch:
        for _ in range(3):
            response = await http.get("/api/escl_scan/capabilities")
            assert response.status == 200
            body = await response.json()
            assert body["schema_version"] == 1 and body["status"] == "fresh"
            assert body["entity_id"] == "sensor.printer_current_scan"
            assert body["supported"]["sources"] == ["Platen", "Feeder"]
            profiles = body["supported"]["profiles"]
            assert profiles["Platen"]["resolutions"] == [75, 300, 600]
            assert profiles["Platen"]["colors"] == ["color", "gray"]
            assert profiles["Feeder"]["resolutions"] is None
            assert profiles["FeederDuplex"]["resolutions"] is None
            assert body["supported"]["automatic_duplex"] is True
            assert body["supported"]["manual_duplex"] is True
            assert "192.0.2.10" not in str(body)
        fetch.assert_awaited_once()
    assert coord.current is None
    response = await http.get("/api/escl_scan/capabilities?entity_id=sensor.printer_current_scan")
    assert response.status == 200
    for query in ("entity_id=sensor.other", "entity_id=button.other"):
        assert (await http.get("/api/escl_scan/capabilities?" + query)).status == 404
    for query in ("refresh=true", "entity_id=a&entity_id=b"):
        assert (await http.get("/api/escl_scan/capabilities?" + query)).status == 400


async def test_capabilities_need_auth_and_unload_rejects(scan_api, hass_client_no_auth):
    http, _, coord = scan_api
    anonymous = await hass_client_no_auth()
    assert (await anonymous.get("/api/escl_scan/capabilities")).status == 401
    await coord.async_shutdown()
    assert (await http.get("/api/escl_scan/capabilities")).status == 503


async def test_stale_capabilities_retain_prior_success_without_private_error(scan_api):
    http, client, coord = scan_api
    client.caps = parse_scanner_capabilities(CAPS_XML)
    coord.capability_cache._expires_at = coord.capability_cache._retry_at = 0
    await coord.async_refresh_capabilities()
    coord.capability_cache._expires_at = 0
    with patch.object(
        client, "get_capabilities", AsyncMock(side_effect=OSError("secret"))
    ) as fetch:
        first = await (await http.get("/api/escl_scan/capabilities")).json()
        second = await (await http.get("/api/escl_scan/capabilities")).json()
        assert first["status"] == second["status"] == "stale"
        assert first["identity"]["model"] == "HP LaserJet MFP M234sdw"
        assert first["fetched_at"] and first["error"] == "refresh_failed"
        assert "secret" not in str(first)
        fetch.assert_awaited_once()


async def test_known_unsupported_source_and_color_are_rejected_before_job(scan_api):
    http, client, coord = scan_api
    client.caps = parse_scanner_capabilities(
        b"<ScannerCapabilities><PlatenInputCaps><ColorMode>Grayscale8</ColorMode>"
        b"</PlatenInputCaps></ScannerCapabilities>"
    )
    coord.capability_cache._expires_at = coord.capability_cache._retry_at = 0
    with patch.object(client, "create_job", AsyncMock()) as create:
        for options in ({"source": "Feeder"}, {"source": "Platen", "color": "color"}):
            response = await http.post("/api/escl_scan/start", json=options)
            assert response.status == 400
            assert "does not support" in (await response.json())["message"]
        create.assert_not_called()
    assert coord.current is None


def test_missing_duplex_resolutions_do_not_borrow_platen_values():
    caps = parse_scanner_capabilities(CAPS_XML)
    assert caps.snap_dpi(200, "Feeder", True) == 200
    assert caps.source_color_modes["Platen"] == ["Grayscale8", "RGB24"]
