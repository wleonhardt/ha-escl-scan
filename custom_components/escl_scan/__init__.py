"""eSCL Scan — trigger document scans on AirScan-capable network scanners
with per-job state tracking, bus events, and a Lovelace card."""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from aiohttp import web

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import HomeAssistantView, StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    CARD_FILENAME,
    CARD_URL_PREFIX,
    CONF_DEFAULT_COLOR,
    CONF_DEFAULT_DPI,
    CONF_FILE_TTL,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_RELAXED_CIPHERS,
    CONF_USER,
    CONF_USE_TLS,
    CONF_VERIFY_TLS,
    DEFAULT_COLOR,
    DEFAULT_DPI,
    DEFAULT_FILE_TTL,
    DEFAULT_PORT,
    DEFAULT_USER,
    DOMAIN,
    STORAGE_SUBDIR,
)
from .coordinator import ScanCoordinator
from .scanner import ScannerClient

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]

_CARD_FILE = Path(__file__).parent / "static" / CARD_FILENAME

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


def _card_url_sync() -> str:
    """Compute the content-hashed card URL. Reads card.js from disk;
    must be called from an executor, not the event loop."""
    digest = hashlib.sha256(_CARD_FILE.read_bytes()).hexdigest()[:12]
    return f"{CARD_URL_PREFIX}{digest}.js"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    data = {**entry.data, **entry.options}
    client = ScannerClient(
        host=data[CONF_HOST],
        port=data.get(CONF_PORT, DEFAULT_PORT),
        use_tls=data.get(CONF_USE_TLS, True),
        user=data.get(CONF_USER) or DEFAULT_USER,
        password=data.get(CONF_PASSWORD, ""),
        verify_tls=data.get(CONF_VERIFY_TLS, False),
        relaxed_ciphers=data.get(CONF_RELAXED_CIPHERS, False),
    )
    storage_dir = Path(hass.config.path(".storage")) / STORAGE_SUBDIR
    coordinator = ScanCoordinator(
        hass,
        client,
        storage_dir=storage_dir,
        default_dpi=data.get(CONF_DEFAULT_DPI, DEFAULT_DPI),
        default_color=data.get(CONF_DEFAULT_COLOR, DEFAULT_COLOR),
        file_ttl_seconds=data.get(CONF_FILE_TTL, DEFAULT_FILE_TTL),
    )
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "coordinator": coordinator,
    }

    # Views are idempotent — re-registering on reload is a no-op since the
    # URL is already taken. They resolve their coordinator from hass.data
    # on each request so option-flow reloads pick up new defaults.
    if not hass.data[DOMAIN].get("_views_registered"):
        hass.http.register_view(ScanStartView(hass))
        hass.http.register_view(ScanCancelView(hass))
        hass.http.register_view(ScanFileView(hass))
        hass.data[DOMAIN]["_views_registered"] = True
    _LOGGER.info(
        "%s: endpoints ready at /api/%s/{start,cancel,file/<id>} (scanner=%s)",
        DOMAIN, DOMAIN, data[CONF_HOST],
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Content-hash card URL for cache-busting.
    card_url = await hass.async_add_executor_job(_card_url_sync)
    await hass.http.async_register_static_paths(
        [StaticPathConfig(card_url, str(_CARD_FILE), False)]
    )
    add_extra_js_url(hass, card_url)
    hass.data[DOMAIN][entry.entry_id]["card_url"] = card_url
    hass.async_create_task(_sync_lovelace_resource(hass, card_url))

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when its options are saved."""
    await hass.config_entries.async_reload(entry.entry_id)


async def _sync_lovelace_resource(hass: HomeAssistant, card_url: str) -> None:
    """Mirror of ipp_print's resource sync. Make the global lovelace resource
    collection match `card_url`, dropping any stale entries from older hashes
    so the OLD card class can't register first and beat the new one's
    customElements.define race."""
    import asyncio
    for _ in range(60):
        coll = hass.data.get("lovelace_resources") or (
            hass.data.get("lovelace", {}).get("resources")
            if isinstance(hass.data.get("lovelace"), dict)
            else getattr(hass.data.get("lovelace"), "resources", None)
        )
        if coll is not None:
            break
        await asyncio.sleep(1)
    else:
        _LOGGER.warning("lovelace resources collection never appeared")
        return
    try:
        items = list(coll.async_items())
        current_id = None
        stale_ids: list[str] = []
        for item in items:
            url = item.get("url", "")
            if url == card_url:
                current_id = item.get("id")
            elif url.startswith(CARD_URL_PREFIX):
                stale_ids.append(item.get("id"))
        for sid in stale_ids:
            if sid:
                await coll.async_delete_item(sid)
                _LOGGER.info("reaped stale lovelace resource %s", sid)
        if current_id is None:
            await coll.async_create_item({"res_type": "module", "url": card_url})
            _LOGGER.info("registered %s in lovelace resources", card_url)
    except Exception:
        _LOGGER.exception("failed to sync lovelace resources")


def _current_coordinator(hass: HomeAssistant) -> ScanCoordinator | None:
    """Return the most-recently-set-up scan coordinator from hass.data,
    or None if no entry is configured. Views resolve through this on
    every request so option-flow reloads see the new coordinator instance
    without needing the views themselves to be re-registered."""
    entries = hass.data.get(DOMAIN, {})
    for key, entry_data in entries.items():
        if key.startswith("_") or not isinstance(entry_data, dict):
            continue
        c = entry_data.get("coordinator")
        if c is not None:
            return c
    return None


class ScanStartView(HomeAssistantView):
    """POST /api/escl_scan/start  body (optional): {"dpi": int, "color": "color"|"gray", "source": "Platen"|"Feeder"}"""

    url = "/api/escl_scan/start"
    name = "api:escl_scan:start"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass

    @property
    def _coord(self) -> ScanCoordinator | None:
        return _current_coordinator(self._hass)

    async def post(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
        except Exception:
            data = {}
        if not isinstance(data, dict):
            data = {}

        source = data.get("source")
        if source not in (None, "Platen", "Feeder"):
            return self.json_message("invalid 'source'", status_code=400)
        dpi = data.get("dpi")
        if dpi is not None and (not isinstance(dpi, int) or dpi <= 0 or dpi > 1200):
            return self.json_message("invalid 'dpi'", status_code=400)
        color = data.get("color")
        if color not in (None, "color", "gray"):
            return self.json_message("invalid 'color' (must be 'color' or 'gray')", status_code=400)

        coord = self._coord
        if coord is None:
            return self.json_message("integration not configured", status_code=503)
        try:
            scan = await coord.start_scan(source=source, dpi=dpi, color=color)
        except Exception as exc:
            _LOGGER.exception("scan kickoff failed")
            return self.json_message(f"scan kickoff failed: {exc}", status_code=502)

        return self.json(
            {
                "ok": True,
                "scan_id": scan.scan_id,
                "source": scan.source,
                "dpi": scan.dpi,
                "color": scan.color,
                "state": scan.state,
            }
        )


class ScanCancelView(HomeAssistantView):
    """POST /api/escl_scan/cancel  body: {"scan_id": "..."}"""

    url = "/api/escl_scan/cancel"
    name = "api:escl_scan:cancel"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass

    @property
    def _coord(self) -> ScanCoordinator | None:
        return _current_coordinator(self._hass)

    async def post(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
        except Exception:
            return self.json_message("invalid JSON", status_code=400)
        scan_id = data.get("scan_id") if isinstance(data, dict) else None
        if not isinstance(scan_id, str) or not scan_id:
            return self.json_message("missing or invalid 'scan_id'", status_code=400)
        coord = self._coord
        if coord is None:
            return self.json_message("integration not configured", status_code=503)
        scan = coord.get(scan_id)
        if scan is None:
            return self.json_message("scan not found", status_code=404)
        if scan.is_terminal():
            return self.json_message(
                f"scan already terminal (state={scan.state})", status_code=409,
            )
        ok = await coord.async_cancel(scan_id)
        if not ok:
            return self.json_message(
                "scanner refused cancel — job may still be running",
                status_code=502,
            )
        return self.json({"ok": True, "scan_id": scan_id})


class ScanFileView(HomeAssistantView):
    """GET /api/escl_scan/file/{scan_id}  streams the PDF."""

    url = "/api/escl_scan/file/{scan_id}"
    name = "api:escl_scan:file"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass

    @property
    def _coord(self) -> ScanCoordinator | None:
        return _current_coordinator(self._hass)

    async def get(self, request: web.Request, scan_id: str) -> web.Response:
        coord = self._coord
        if coord is None:
            return self.json_message("integration not configured", status_code=503)
        scan = coord.get(scan_id)
        # Status precedence:
        #   404 — scan_id unknown OR file already TTL-purged from disk
        #   409 — scan_id valid but not ready (in progress, canceled,
        #         failed: anything not 'completed')
        if scan is None:
            return self.json_message("not found", status_code=404)
        if scan.state != "completed":
            return self.json_message(
                f"scan not ready (state={scan.state})", status_code=409,
            )
        if scan.file_path is None or not scan.file_path.exists():
            return self.json_message(
                "file expired or missing on disk", status_code=404,
            )
        return web.FileResponse(
            scan.file_path,
            headers={
                "Content-Type": "application/pdf",
                "Content-Disposition": f'inline; filename="{scan.filename}"',
            },
        )
