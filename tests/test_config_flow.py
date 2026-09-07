"""Config- and options-flow tests."""
from ipaddress import ip_address
from unittest.mock import patch

from homeassistant import config_entries, data_entry_flow
from homeassistant.core import HomeAssistant
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.escl_scan.const import (
    CONF_BASE_PATH,
    CONF_COPY_DIR,
    CONF_DEFAULT_DPI,
    CONF_FILE_TTL,
    CONF_HOST,
    CONF_PORT,
    CONF_USE_TLS,
    DOMAIN,
)
from custom_components.escl_scan.scanner import ScannerCapabilities

_OK = "custom_components.escl_scan.config_flow.ScannerClient.get_scanner_status"
_SETUP = "custom_components.escl_scan.async_setup_entry"
_CAPS = "custom_components.escl_scan.config_flow.ScannerClient.get_capabilities"


async def test_user_flow_success(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM

    caps = ScannerCapabilities(make_and_model="Canon TR8600", serial_number="ABC123")
    with patch(_OK, return_value=None), patch(_CAPS, return_value=caps):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "192.0.2.10"}
        )
        await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HOST] == "192.0.2.10"
    assert result["title"] == "Canon TR8600"
    assert result["result"].unique_id == "ABC123"


async def test_user_flow_without_capabilities_falls_back_to_host(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(_OK, return_value=None), patch(_CAPS, side_effect=OSError("404")):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "192.0.2.10"}
        )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "192.0.2.10:443"


async def test_user_flow_cannot_connect(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(_OK, side_effect=OSError("refused")):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "192.0.2.11"}
        )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"


async def test_single_config_entry_aborts_second(hass: HomeAssistant):
    MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "192.0.2.10"}).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


def _zeroconf(type_="_uscans._tcp.local.", port=443, props=None):
    return ZeroconfServiceInfo(
        ip_address=ip_address("192.0.2.20"),
        ip_addresses=[ip_address("192.0.2.20")],
        port=port,
        hostname="NPI1234.local.",
        type=type_,
        name=f"HP LaserJet MFP M234sdw [1234].{type_}",
        properties=props if props is not None else {
            "rs": "eSCL", "ty": "HP LaserJet MFP M234sdw", "UUID": "uuid-abc",
        },
    )


async def test_zeroconf_discovery_confirm_creates_entry(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=_zeroconf()
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"
    assert result["description_placeholders"]["name"] == "HP LaserJet MFP M234sdw"

    with patch(_SETUP, return_value=True):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "HP LaserJet MFP M234sdw"
    assert result["result"].unique_id == "uuid-abc"
    data = result["data"]
    assert data[CONF_HOST] == "192.0.2.20"
    assert data[CONF_PORT] == 443
    assert data[CONF_USE_TLS] is True
    assert data[CONF_BASE_PATH] == "eSCL"


async def test_zeroconf_plain_http_and_custom_resource_path(hass: HomeAssistant):
    # HP advertises lowercase `uuid`; the lookup must be case-insensitive.
    info = _zeroconf("_uscan._tcp.local.", port=8080, props={"rs": "/escl/", "uuid": "u2"})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=info
    )
    with patch(_SETUP, return_value=True):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["data"][CONF_USE_TLS] is False
    assert result["data"][CONF_PORT] == 8080
    assert result["data"][CONF_BASE_PATH] == "escl"
    assert result["result"].unique_id == "u2"
    # No `ty` → falls back to the service instance name.
    assert result["title"] == "HP LaserJet MFP M234sdw [1234]"


async def test_zeroconf_aborts_when_host_already_configured(hass: HomeAssistant):
    MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "192.0.2.20"}).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=_zeroconf()
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT


async def test_options_flow_saves_valid(hass: HomeAssistant):
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "192.0.2.10"})
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == data_entry_flow.FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.0.2.10", CONF_DEFAULT_DPI: 600, CONF_FILE_TTL: 120},
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_DEFAULT_DPI] == 600


async def test_options_flow_rejects_copy_dir_outside_allowlist(hass: HomeAssistant):
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "192.0.2.10"})
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.0.2.10", CONF_COPY_DIR: "/definitely/not/allowed"},
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {CONF_COPY_DIR: "path_not_allowed"}


async def test_options_flow_accepts_allowed_copy_dir(hass: HomeAssistant, tmp_path):
    hass.config.allowlist_external_dirs = {str(tmp_path)}
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "192.0.2.10"})
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.0.2.10", CONF_COPY_DIR: f" {tmp_path}/consume "},
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_COPY_DIR] == f"{tmp_path}/consume"


async def test_options_flow_rejects_bad_dpi(hass: HomeAssistant):
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "192.0.2.10"})
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    with pytest.raises(data_entry_flow.InvalidData):
        await hass.config_entries.options.async_configure(
            result["flow_id"],
            {CONF_HOST: "192.0.2.10", CONF_DEFAULT_DPI: 0, CONF_FILE_TTL: 120},
        )
