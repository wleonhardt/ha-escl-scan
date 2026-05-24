"""eSCL Scan — placeholder entry point.

Full implementation lands in phases:
  - Phase 2: scanner.py (eSCL wire format + client)
  - Phase 3: coordinator.py (job tracking + bus events)
  - Phase 4: sensor.py (sensor.printer_current_scan)
  - Phase 5: HTTP views (/api/escl_scan/{start,cancel,file/{id}})
  - Phase 6: static/card.js (Lovelace card)
"""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {}
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data[DOMAIN].pop(entry.entry_id, None)
    return True
