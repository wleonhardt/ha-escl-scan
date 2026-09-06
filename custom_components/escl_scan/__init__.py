"""eSCL Scan — trigger document scans on AirScan-capable network scanners
with per-job state tracking, bus events, and a Lovelace card."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import hashlib
import logging
from pathlib import Path

from aiohttp import web
from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import HomeAssistantView, StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType

from .const import (
    CARD_FILENAME,
    CARD_URL_PREFIX,
    CONF_BASE_PATH,
    CONF_COPY_DIR,
    CONF_DEFAULT_COLOR,
    CONF_DEFAULT_DPI,
    CONF_DEFAULT_DUPLEX,
    CONF_FILE_TTL,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_RELAXED_CIPHERS,
    CONF_USE_TLS,
    CONF_USER,
    CONF_VERIFY_TLS,
    DEFAULT_BASE_PATH,
    DEFAULT_COLOR,
    DEFAULT_DPI,
    DEFAULT_DUPLEX,
    DEFAULT_FILE_TTL,
    DEFAULT_PORT,
    DEFAULT_USER,
    DOMAIN,
    STORAGE_SUBDIR,
)
from .coordinator import ScanBusyError, ScanCoordinator
from .scanner import ScannerClient
from .services import async_register_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["button", "sensor"]

_CARD_FILE = Path(__file__).parent / "static" / CARD_FILENAME

# Sweep TTL-expired scan files even when no new scan is started.
PURGE_INTERVAL = timedelta(minutes=15)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


def _card_url_sync() -> str:
    """Compute the content-hashed card URL. Reads card.js from disk;
    must be called from an executor, not the event loop."""
    digest = hashlib.sha256(_CARD_FILE.read_bytes()).hexdigest()[:12]
    return f"{CARD_URL_PREFIX}{digest}.js"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    async_register_services(hass)
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
        base_path=data.get(CONF_BASE_PATH, DEFAULT_BASE_PATH),
    )
    storage_dir = Path(hass.config.path(".storage")) / STORAGE_SUBDIR
    copy_dir: Path | None = None
    if raw_copy := data.get(CONF_COPY_DIR):
        if hass.config.is_allowed_path(raw_copy):
            copy_dir = Path(raw_copy)
        else:
            _LOGGER.warning(
                "copy_to_dir %s is outside allowlist_external_dirs; ignoring", raw_copy
            )
    coordinator = ScanCoordinator(
        hass,
        client,
        storage_dir=storage_dir,
        default_dpi=data.get(CONF_DEFAULT_DPI, DEFAULT_DPI),
        default_color=data.get(CONF_DEFAULT_COLOR, DEFAULT_COLOR),
        default_duplex=data.get(CONF_DEFAULT_DUPLEX, DEFAULT_DUPLEX),
        file_ttl_seconds=data.get(CONF_FILE_TTL, DEFAULT_FILE_TTL),
        copy_dir=copy_dir,
    )
    # Model/serial/bed size for device info and scan regions. Best-effort —
    # setup must succeed even when the scanner is asleep or offline.
    await coordinator.async_refresh_capabilities()
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

    # Content-hash card URL for cache-busting. Track which URLs we've
    # already registered so reloads (options change → async_reload) don't
    # re-call register_static_paths on the same URL — aiohttp rejects
    # duplicate GET routes with "Added route will never be executed".
    card_url = await hass.async_add_executor_job(_card_url_sync)
    registered = hass.data[DOMAIN].setdefault("_card_urls_registered", set())
    if card_url not in registered:
        await hass.http.async_register_static_paths(
            [StaticPathConfig(card_url, str(_CARD_FILE), False)]
        )
        add_extra_js_url(hass, card_url)
        registered.add(card_url)
    hass.data[DOMAIN][entry.entry_id]["card_url"] = card_url
    if not hass.data[DOMAIN].get("_resources_reaped"):
        hass.data[DOMAIN]["_resources_reaped"] = True
        hass.async_create_task(_reap_lovelace_resources(hass))

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    entry.async_on_unload(
        async_track_time_interval(hass, coordinator.async_purge_now, PURGE_INTERVAL)
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        data = hass.data[DOMAIN].pop(entry.entry_id, None)
        if data:
            coordinator = data.get("coordinator")
            if coordinator is not None:
                await coordinator.async_shutdown()
    return unloaded


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when its options are saved."""
    await hass.config_entries.async_reload(entry.entry_id)


async def _reap_lovelace_resources(hass: HomeAssistant) -> None:
    """One-shot cleanup of lovelace resource entries this integration
    auto-registered in older versions. The card now loads solely via
    add_extra_js_url, so any `escl_scan/card-*.js` resource entry is redundant
    and its content-hash URL 404s after an update. We only ever DELETE here —
    never create — which sidesteps the concurrent-reload duplicate-entry race
    the old sync had. Touching lovelace internals is best-effort and must
    never fail setup."""
    coll = None
    for _ in range(30):
        lovelace = hass.data.get("lovelace")
        coll = hass.data.get("lovelace_resources") or (
            lovelace.get("resources")
            if isinstance(lovelace, dict)
            else getattr(lovelace, "resources", None)
        )
        if coll is not None:
            break
        await asyncio.sleep(1)
    if coll is None:
        return
    try:
        for item in list(coll.async_items()):
            url = item.get("url", "")
            sid = item.get("id")
            if sid and url.startswith(CARD_URL_PREFIX):
                await coll.async_delete_item(sid)
                _LOGGER.info("removed redundant lovelace resource %s", url)
    except Exception:
        _LOGGER.debug("lovelace resource cleanup skipped", exc_info=True)


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
    """POST /api/escl_scan/start

    Optional JSON body: {"dpi": int, "color": "color"|"gray",
    "source": "Platen"|"Feeder", "duplex": bool}."""

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
        duplex = data.get("duplex")
        if duplex is not None and not isinstance(duplex, bool):
            return self.json_message("invalid 'duplex' (must be a boolean)", status_code=400)

        coord = self._coord
        if coord is None:
            return self.json_message("integration not configured", status_code=503)
        try:
            scan = await coord.start_scan(
                source=source, dpi=dpi, color=color, duplex=duplex
            )
        except ScanBusyError:
            return self.json_message("a scan is already running", status_code=409)
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
                "duplex": scan.duplex,
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
