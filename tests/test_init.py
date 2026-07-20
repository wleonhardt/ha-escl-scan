"""End-to-end setup/unload of the config entry against real HomeAssistant.
Exercises coordinator registration, sensor creation, view wiring, and the
unload -> coordinator.async_shutdown path.
"""
from unittest.mock import patch

from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.escl_scan.const import CONF_HOST, CONF_USE_TLS, DOMAIN


async def _noop_reap(*args, **kwargs):
    return None


async def test_setup_and_unload(hass):
    await async_setup_component(hass, "http", {})
    await hass.async_block_till_done()

    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "192.0.2.10", CONF_USE_TLS: False}
    )
    entry.add_to_hass(hass)

    # Avoid the frontend dependency and the background lovelace-reap task
    # (which would otherwise linger and trip the harness cleanup check).
    with (
        patch("custom_components.escl_scan.add_extra_js_url"),
        patch("custom_components.escl_scan._reap_lovelace_resources", _noop_reap),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        coord = hass.data[DOMAIN][entry.entry_id]["coordinator"]
        assert coord is not None
        assert coord.host == "192.0.2.10"
        assert hass.states.get("sensor.printer_current_scan") is not None

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.entry_id not in hass.data[DOMAIN]
    # shutdown closed the client session
    assert coord._client._session_obj is None
