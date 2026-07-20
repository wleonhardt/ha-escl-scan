"""Config- and options-flow tests."""
from unittest.mock import patch

from homeassistant import config_entries, data_entry_flow
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.escl_scan.const import (
    CONF_DEFAULT_DPI,
    CONF_FILE_TTL,
    CONF_HOST,
    DOMAIN,
)

_OK = "custom_components.escl_scan.config_flow.ScannerClient.get_scanner_status"


async def test_user_flow_success(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM

    with patch(_OK, return_value=None):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "192.0.2.10"}
        )
        await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HOST] == "192.0.2.10"


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


async def test_options_flow_rejects_bad_dpi(hass: HomeAssistant):
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "192.0.2.10"})
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    with pytest.raises(data_entry_flow.InvalidData):
        await hass.config_entries.options.async_configure(
            result["flow_id"],
            {CONF_HOST: "192.0.2.10", CONF_DEFAULT_DPI: 0, CONF_FILE_TTL: 120},
        )
