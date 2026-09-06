"""Domain services: escl_scan.start / escl_scan.cancel.

Registered once per hass (not per entry) so automations can call them
without a REST command + long-lived token. The handlers resolve the
coordinator on each call, like the HTTP views do.
"""
from __future__ import annotations

from typing import Any

from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
import voluptuous as vol

from .const import DOMAIN
from .coordinator import ScanBusyError, ScanCoordinator

SERVICE_START = "start"
SERVICE_CANCEL = "cancel"

ATTR_SOURCE = "source"
ATTR_DPI = "dpi"
ATTR_COLOR = "color"
ATTR_DUPLEX = "duplex"
ATTR_SCAN_ID = "scan_id"

START_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_SOURCE): vol.In(["Platen", "Feeder"]),
        vol.Optional(ATTR_DPI): vol.All(vol.Coerce(int), vol.Range(min=50, max=1200)),
        vol.Optional(ATTR_COLOR): vol.In(["color", "gray"]),
        vol.Optional(ATTR_DUPLEX): bool,
    }
)
CANCEL_SCHEMA = vol.Schema({vol.Optional(ATTR_SCAN_ID): str})


def _coordinator(hass: HomeAssistant) -> ScanCoordinator:
    from . import _current_coordinator  # avoid an import cycle at module load

    coord = _current_coordinator(hass)
    if coord is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="not_configured"
        )
    return coord


@callback
def async_register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_START):
        return

    async def _start(call: ServiceCall) -> ServiceResponse:
        coord = _coordinator(hass)
        try:
            scan = await coord.start_scan(
                source=call.data.get(ATTR_SOURCE),
                dpi=call.data.get(ATTR_DPI),
                color=call.data.get(ATTR_COLOR),
                duplex=call.data.get(ATTR_DUPLEX),
            )
        except ScanBusyError as exc:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="scan_busy"
            ) from exc
        except Exception as exc:
            raise HomeAssistantError(f"scan kickoff failed: {exc}") from exc
        result: dict[str, Any] = scan.to_dict()
        return result if call.return_response else None

    async def _cancel(call: ServiceCall) -> None:
        coord = _coordinator(hass)
        scan_id = call.data.get(ATTR_SCAN_ID)
        scan = coord.get(scan_id) if scan_id else coord.current
        if scan is None or scan.is_terminal():
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="no_active_scan"
            )
        if not await coord.async_cancel(scan.scan_id):
            raise HomeAssistantError("scanner refused cancel")

    hass.services.async_register(
        DOMAIN, SERVICE_START, _start, schema=START_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(DOMAIN, SERVICE_CANCEL, _cancel, schema=CANCEL_SCHEMA)
