"""sensor.printer_current_scan — mirrors the active eSCL scan state."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ScanCoordinator

SCAN_STATES = [
    "idle",
    "pending",
    "processing",
    "processing-stopped",
    "canceled",
    "aborted",
    "completed",
    "failed",
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: ScanCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([ScannerScanSensor(coordinator, entry.entry_id)])


class ScannerScanSensor(SensorEntity):
    """Mirrors ScanCoordinator.current as a sensor entity."""

    _attr_has_entity_name = True
    _attr_translation_key = "current_scan"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = SCAN_STATES
    _attr_should_poll = False

    def __init__(self, coordinator: ScanCoordinator, entry_id: str) -> None:
        self._coord = coordinator
        self._attr_unique_id = f"{entry_id}_current_scan"
        self._attr_device_info = coordinator.device_info(entry_id)
        # Stable entity_id so the card can find it without renames.
        self.entity_id = "sensor.printer_current_scan"
        self._unsub = None

    async def async_added_to_hass(self) -> None:
        self._unsub = self._coord.register_update_listener(self._handle_update)
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub:
            self._unsub()
            self._unsub = None

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()

    @property
    def native_value(self) -> str:
        scan = self._coord.current
        return "idle" if scan is None else scan.state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        scan = self._coord.current
        return {"scan_id": None} if scan is None else scan.to_dict()
