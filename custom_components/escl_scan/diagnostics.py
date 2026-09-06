"""Diagnostics: what the scanner told us and what we did with it."""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_HOST, CONF_PASSWORD, CONF_USER, DOMAIN

TO_REDACT = {CONF_HOST, CONF_PASSWORD, CONF_USER, "unique_id"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    entry_data = hass.data.get(DOMAIN, {}).get(entry.entry_id) or {}
    coordinator = entry_data.get("coordinator")
    caps = coordinator.capabilities if coordinator else None
    return {
        "entry": async_redact_data(
            {"data": dict(entry.data), "options": dict(entry.options),
             "unique_id": entry.unique_id},
            TO_REDACT,
        ),
        "capabilities": asdict(caps) if caps else None,
        "current_scan": (
            coordinator.current.to_dict() if coordinator and coordinator.current else None
        ),
        "tracked_scans": (
            [s.to_dict() for s in coordinator._scans.values()] if coordinator else []
        ),
    }
