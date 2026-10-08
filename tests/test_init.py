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
    assert diag["capabilities"]["serial_number"] == "**REDACTED**"
    assert diag["current_scan"] is None
    assert diag["tracked_scans"] == []


async def test_diagnostics_redact_scan_paths_errors_and_capability_identifiers(hass):
    from datetime import UTC, datetime
    from pathlib import Path

    from custom_components.escl_scan.coordinator import ScanCoordinator, TrackedScan
    from custom_components.escl_scan.diagnostics import async_get_config_entry_diagnostics

    from .fakes import FakeClient

    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "192.0.2.10"},
        options={CONF_COPY_DIR: "/private/consume"},
    )
    coord = ScanCoordinator(
        hass, FakeClient(), storage_dir=Path("/private/store"), default_dpi=300,
        default_color="color", file_ttl_seconds=3600,
    )
    coord._caps = ScannerCapabilities(serial_number="private-serial", uuid="private-uuid")
    scan = TrackedScan(
        scan_id="s1", source="Platen", dpi=300, color="color",
        submitted_at=datetime.now(UTC), state="completed", error="192.0.2.10",
        file_path=Path("/private/scan.pdf"), copied_to=Path("/private/consume/scan.pdf"),
    )
    coord._current = scan
    coord._scans[scan.scan_id] = scan
    hass.data[DOMAIN] = {entry.entry_id: {"coordinator": coord}}
    diag = await async_get_config_entry_diagnostics(hass, entry)
    assert diag["entry"]["options"][CONF_COPY_DIR] == "**REDACTED**"
    assert diag["capabilities"]["uuid"] == "**REDACTED**"
    for item in (diag["current_scan"], diag["tracked_scans"][0]):
        for key in ("file_path", "copied_to", "error"):
            assert item[key] == "**REDACTED**"


async def test_setup_failure_closes_client_and_removes_coordinator(hass):
    from .fakes import FakeClient

    client = FakeClient()
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "192.0.2.10"})
    entry.add_to_hass(hass)
    with (
        patch("custom_components.escl_scan.ScannerClient", return_value=client),
        patch("custom_components.escl_scan._card_url_sync", side_effect=OSError("missing card")),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert client.closed
    assert entry.entry_id not in hass.data[DOMAIN]


async def test_homeassistant_stop_closes_client_and_cleans_active_scan(hass, tmp_path):
    import asyncio

    from homeassistant.const import EVENT_HOMEASSISTANT_STOP

    from .fakes import FakeClient
    from .test_coordinator import _wait_for

    client = FakeClient(hang=True)
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "192.0.2.10"})
    entry.add_to_hass(hass)
    with (
        patch("custom_components.escl_scan.ScannerClient", return_value=client),
        patch("custom_components.escl_scan._reap_lovelace_resources", _noop_reap),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        coord = hass.data[DOMAIN][entry.entry_id]["coordinator"]
        coord._storage = tmp_path / "store"
        scan = await coord.start_scan()
        await _wait_for(lambda: bool(list(coord._storage.glob("*.part*"))))
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        async with asyncio.timeout(2):
            await hass.async_block_till_done()
        assert client.closed
        assert client.deleted == [scan.job_url]
        assert not list(coord._storage.iterdir())
