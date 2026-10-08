"""Versioned source-specific capabilities for dashboard options."""
from __future__ import annotations

from .capability_cache import CapabilityCache
from .const import DOMAIN
from .scanner import ScannerCapabilities


def capability_snapshot(cache: CapabilityCache[ScannerCapabilities], entity_id: str | None) -> dict:
    caps = cache.value
    profiles = {}
    if caps:
        for key in ("Platen", "Feeder", "FeederDuplex"):
            values = caps.source_resolutions.get(key)
            modes = caps.source_color_modes.get(key)
            profiles[key] = {
                "resolutions": sorted({dpi for dpi in values if 50 <= dpi <= 1200})
                if values else None,
                "colors": [color for color, mode in (("color", "RGB24"), ("gray", "Grayscale8"))
                           if mode in modes] if modes else None,
            }
    return {
        "schema_version": 1,
        "domain": DOMAIN,
        "entity_id": entity_id,
        **cache.metadata(),
        "identity": {"model": (caps.make_and_model or "")[:256] or None if caps else None},
        "supported": {
            "sources": list(caps.sources) or None if caps else None,
            "automatic_duplex": caps.adf_duplex if caps and caps.adf_duplex_known else None,
            "manual_duplex": "Feeder" in caps.sources if caps and caps.sources else None,
            "profiles": profiles,
        },
        "request_options": ["source", "dpi", "color", "duplex"],
        "limits": {"dpi_min": 50, "dpi_max": 1200, "format": "application/pdf"},
    }
