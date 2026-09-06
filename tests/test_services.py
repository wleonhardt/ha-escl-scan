"""escl_scan.start / escl_scan.cancel services and the Scan now button,
run through a real config entry with the scanner client faked."""
from unittest.mock import patch

from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
import voluptuous as vol

from custom_components.escl_scan.const import CONF_HOST, CONF_USE_TLS, DOMAIN

from .fakes import FakeClient
from .test_coordinator import VALID_PDF


async def _noop_reap(*args, **kwargs):
    return None


@pytest.fixture
async def setup(hass):
    """Set up the entry with a FakeClient; yields (entry, client)."""
    client = FakeClient(docs=[[VALID_PDF]])
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "192.0.2.10", CONF_USE_TLS: False})
    entry.add_to_hass(hass)
    with (
        patch("custom_components.escl_scan._reap_lovelace_resources", _noop_reap),
        patch("custom_components.escl_scan.ScannerClient", return_value=client),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        yield entry, client
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_services_registered(hass, setup):
    assert hass.services.has_service(DOMAIN, "start")
    assert hass.services.has_service(DOMAIN, "cancel")


async def test_start_service_returns_scan_and_updates_sensor(hass, setup):
    _, client = setup
    resp = await hass.services.async_call(
        DOMAIN, "start", {"source": "Platen", "dpi": 300, "color": "gray"},
        blocking=True, return_response=True,
    )
    assert resp["scan_id"] and resp["source"] == "Platen" and resp["color"] == "gray"
    coord = hass.data[DOMAIN][setup[0].entry_id]["coordinator"]
    for task in list(coord._driver_tasks.values()):
        await task
    await hass.async_block_till_done()
    assert hass.states.get("sensor.printer_current_scan").state == "completed"
    assert client.create_kwargs["color"] == "gray"


async def test_start_service_rejects_bad_source(hass, setup):
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(DOMAIN, "start", {"source": "Tray"}, blocking=True)


async def test_start_service_busy_raises_validation_error(hass, setup):
    import asyncio

    _, client = setup
    client._gate = asyncio.Event()
    await hass.services.async_call(DOMAIN, "start", {}, blocking=True)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN, "start", {}, blocking=True)
    client._gate.set()
    coord = hass.data[DOMAIN][setup[0].entry_id]["coordinator"]
    for task in list(coord._driver_tasks.values()):
        await task


async def test_cancel_service_without_id_cancels_current(hass, setup):
    import asyncio

    _, client = setup
    client._gate = asyncio.Event()
    resp = await hass.services.async_call(
        DOMAIN, "start", {}, blocking=True, return_response=True
    )
    await hass.services.async_call(DOMAIN, "cancel", {}, blocking=True)
    coord = hass.data[DOMAIN][setup[0].entry_id]["coordinator"]
    assert coord.get(resp["scan_id"]).state == "canceled"
    client._gate.set()
    for task in list(coord._driver_tasks.values()):
        await task


async def test_cancel_service_with_nothing_running(hass, setup):
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN, "cancel", {}, blocking=True)


BUTTON = "button.escl_scanner_192_0_2_10_scan_now"


async def test_scan_now_button(hass, setup):
    entry, client = setup
    assert hass.states.get(BUTTON) is not None
    await hass.services.async_call("button", "press", {"entity_id": BUTTON}, blocking=True)
    coord = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    assert coord.current is not None
    for task in list(coord._driver_tasks.values()):
        await task
    assert coord.current.state == "completed"


async def test_scan_now_button_busy(hass, setup):
    import asyncio

    entry, client = setup
    client._gate = asyncio.Event()
    await hass.services.async_call("button", "press", {"entity_id": BUTTON}, blocking=True)
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call("button", "press", {"entity_id": BUTTON}, blocking=True)
    client._gate.set()
    coord = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    for task in list(coord._driver_tasks.values()):
        await task
