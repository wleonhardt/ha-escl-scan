"""End-to-end setup/unload of the config entry against real HomeAssistant.
Exercises coordinator registration, sensor creation, view wiring, and the
unload -> coordinator.async_shutdown path.
"""
from unittest.mock import patch

from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.escl_scan.const import (
    CONF_COPY_DIR,
    CONF_HOST,
    CONF_USE_TLS,
    DOMAIN,
)
from custom_components.escl_scan.scanner import ScannerCapabilities

_CAPS = "custom_components.escl_scan.scanner.ScannerClient.get_capabilities"


async def _noop_reap(*args, **kwargs):
    return None


async def test_setup_and_unload(hass):
    await async_setup_component(hass, "http", {})
    await hass.async_block_till_done()

    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "192.0.2.10", CONF_USE_TLS: False}
    )
    entry.add_to_hass(hass)

    # Skip the background lovelace-reap task (it would linger and trip the
    # harness cleanup check).
    caps = ScannerCapabilities(make_and_model="HP LaserJet MFP M234sdw", serial_number="SN1")
    with (
        patch("custom_components.escl_scan._reap_lovelace_resources", _noop_reap),
        patch(_CAPS, return_value=caps),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        coord = hass.data[DOMAIN][entry.entry_id]["coordinator"]
        assert coord is not None
        assert coord.host == "192.0.2.10"
        assert coord.capabilities is caps
        assert hass.states.get("sensor.printer_current_scan") is not None

        dev_reg = dr.async_get(hass)
        device = dev_reg.async_get_device_by_identifier((DOMAIN, entry.entry_id), entry.entry_id)
        assert device.manufacturer == "HP"
        assert device.model == "LaserJet MFP M234sdw"
        assert device.serial_number == "SN1"

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.entry_id not in hass.data[DOMAIN]
    # shutdown closed the client session
    assert coord._client._session_obj is None


async def test_copy_dir_outside_allowlist_is_ignored(hass, caplog):
    await async_setup_component(hass, "http", {})
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.0.2.10", CONF_USE_TLS: False},
        options={CONF_COPY_DIR: "/nope/consume"},
    )
    entry.add_to_hass(hass)
    with (
        patch("custom_components.escl_scan._reap_lovelace_resources", _noop_reap),
        patch(_CAPS, side_effect=OSError("no caps")),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        coord = hass.data[DOMAIN][entry.entry_id]["coordinator"]
        assert coord._copy_dir is None
        assert "allowlist_external_dirs" in caplog.text
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_diagnostics(hass):
    from custom_components.escl_scan.diagnostics import (
        async_get_config_entry_diagnostics,
    )

    await async_setup_component(hass, "http", {})
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.0.2.10", CONF_USE_TLS: False, "password": "hunter2"},
        unique_id="SN1",
    )
    entry.add_to_hass(hass)
    caps = ScannerCapabilities(make_and_model="Canon TR8600", serial_number="SN1")
    with (
        patch("custom_components.escl_scan._reap_lovelace_resources", _noop_reap),
        patch(_CAPS, return_value=caps),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        diag = await async_get_config_entry_diagnostics(hass, entry)
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

    assert diag["entry"]["data"]["host"] == "**REDACTED**"
    assert diag["entry"]["data"]["password"] == "**REDACTED**"
    assert diag["entry"]["unique_id"] == "**REDACTED**"
    assert diag["capabilities"]["make_and_model"] == "Canon TR8600"
    assert diag["current_scan"] is None
    assert diag["tracked_scans"] == []
