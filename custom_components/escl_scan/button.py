"""button.<device>_scan_now — one-tap scan from any stock dashboard card."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ScanBusyError, ScanCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: ScanCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([ScanNowButton(coordinator, entry.entry_id)])


class ScanNowButton(ButtonEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "scan_now"
    _attr_icon = "mdi:scanner"

    def __init__(self, coordinator: ScanCoordinator, entry_id: str) -> None:
        self._coord = coordinator
        self._attr_unique_id = f"{entry_id}_scan_now"
        self._attr_device_info = coordinator.device_info(entry_id)

    async def async_press(self) -> None:
        try:
            await self._coord.start_scan()
        except ScanBusyError as exc:
            raise HomeAssistantError("a scan is already running") from exc
        except Exception as exc:
            raise HomeAssistantError(f"scan kickoff failed: {exc}") from exc
