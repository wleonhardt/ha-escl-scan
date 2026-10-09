"""eSCL Scan — trigger document scans on AirScan-capable network scanners
with per-job state tracking, bus events, and a Lovelace card."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import hashlib
import logging
from pathlib import Path

from aiohttp import web
from homeassistant.components.frontend import add_extra_js_url, remove_extra_js_url
from homeassistant.components.http import HomeAssistantView, StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType

from .capabilities import capability_snapshot
from .connection import DeviceConnection
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
    CONF_ROTATE_DUPLEX_BACKS,
    CONF_USE_TLS,
    CONF_USER,
    CONF_VERIFY_TLS,
    DEFAULT_BASE_PATH,
    DEFAULT_COLOR,
    DEFAULT_DPI,
    DEFAULT_DUPLEX,
    DEFAULT_FILE_TTL,
    DEFAULT_PORT,
    DEFAULT_ROTATE_DUPLEX_BACKS,
    DEFAULT_USER,
    DOMAIN,
    STORAGE_SUBDIR,
)
from .coordinator import ScanBusyError, ScanCoordinator
from .results import STORAGE_VERSION, store_key
from .scanner import ScannerClient
from .services import async_register_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["button", "sensor", "binary_sensor"]

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
        rotate_duplex_backs=data.get(
            CONF_ROTATE_DUPLEX_BACKS, DEFAULT_ROTATE_DUPLEX_BACKS
        ),
        file_ttl_seconds=data.get(CONF_FILE_TTL, DEFAULT_FILE_TTL),
        copy_dir=copy_dir,
        entry_id=entry.entry_id,
    )
    connection = DeviceConnection(hass, client.get_scanner_status, DOMAIN)

    async def _async_stop(event: Event) -> None:
        await connection.async_close()
        await coordinator.async_shutdown()

    entry.async_on_unload(hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, _async_stop))
    try:
        # Best-effort: setup must succeed when the scanner is asleep/offline.
        await coordinator.async_refresh_capabilities()
        await coordinator.latest.async_load()
        await coordinator.async_purge_now()
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN][entry.entry_id] = {
            "client": client,
            "coordinator": coordinator,
            "connection": connection,
        }

        # Views are idempotent — re-registering on reload is a no-op since the
        # URL is already taken. They resolve their coordinator from hass.data
        # on each request so option-flow reloads pick up new defaults.
        if not hass.data[DOMAIN].get("_views_registered"):
            hass.http.register_view(ScanStartView(hass))
            hass.http.register_view(ScanCancelView(hass))
            hass.http.register_view(ScanBacksView(hass))
            hass.http.register_view(ScanFileView(hass))
            hass.http.register_view(ScanCapabilitiesView(hass))
            hass.data[DOMAIN]["_views_registered"] = True
        _LOGGER.info(
            "%s: endpoints ready at /api/%s/{start,cancel,scan_backs,file/<id>} (scanner=%s)",
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
            registered.add(card_url)
        # Keep the routes registered, but load only the current module. An old
        # cached module can otherwise register the custom element first and
        # suppress the updated card, even after the browser page is refreshed.
        for old_url in registered - {card_url}:
            remove_extra_js_url(hass, old_url)
        add_extra_js_url(hass, card_url)
        hass.data[DOMAIN][entry.entry_id]["card_url"] = card_url
        # Dashboard resource loading also covers mobile clients that keep the
        # app shell alive across reconnects and integration updates.
        hass.async_create_task(_sync_lovelace_resources(hass))

        entry.async_on_unload(entry.add_update_listener(_async_update_listener))
        entry.async_on_unload(
            async_track_time_interval(hass, coordinator.async_purge_now, PURGE_INTERVAL)
        )
        connection.start()
        return True

    except BaseException:
        await connection.async_close()
        await coordinator.async_shutdown()
        if hass.data.get(DOMAIN, {}).get(entry.entry_id, {}).get("coordinator") is coordinator:
            hass.data[DOMAIN].pop(entry.entry_id, None)
        raise


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        data = hass.data[DOMAIN].pop(entry.entry_id, None)
        if data:
            if connection := data.get("connection"):
                await connection.async_close()
            coordinator = data.get("coordinator")
            if coordinator is not None:
                await coordinator.async_shutdown()
    return unloaded


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when its options are saved."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Forget result metadata when its configured scanner is removed."""
    await Store(hass, STORAGE_VERSION, store_key(entry.entry_id)).async_remove()


async def _sync_lovelace_resources(hass: HomeAssistant) -> None:
    """Keep one current dashboard resource; extra module loading is a fallback.

    Serialize reloads, load storage before inspecting items, and update an
    existing resource in place so clients don't briefly lose the resource.
    YAML resources are read-only. Collection failures must not fail setup.
    """
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
    if coll is None or not hasattr(coll, "async_create_item"):
        return
    async with hass.data[DOMAIN].setdefault("_resource_sync_lock", asyncio.Lock()):
        try:
            if not getattr(coll, "loaded", True):
                await coll.async_load()
                coll.loaded = True
            # Read the latest loaded entry after waiting for the collection
            # and lock; an older queued task must not restore an obsolete hash.
            card_url = next((
                data["card_url"] for key, data in hass.data[DOMAIN].items()
                if not key.startswith("_") and isinstance(data, dict) and data.get("card_url")
            ), None)
            if card_url is None:
                return
            owned = [item for item in coll.async_items()
                     if item.get("id") and item.get("url", "").startswith(CARD_URL_PREFIX)]
            current = next((item for item in owned if item["url"] == card_url), None)
            if current is None and owned:
                current = owned[0]
            if current is None:
                current = await coll.async_create_item({"res_type": "module", "url": card_url})
            elif current["url"] != card_url or current.get("type") != "module":
                await coll.async_update_item(current["id"], {"res_type": "module", "url": card_url})
            for item in owned:
                if item["id"] != current["id"]:
                    await coll.async_delete_item(item["id"])
        except Exception:
            _LOGGER.warning(
                "dashboard resource sync failed; using extra module loading", exc_info=True
            )


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


class ScanCapabilitiesView(HomeAssistantView):
    """Read-only capability snapshot, available without an active scan."""

    url = "/api/escl_scan/capabilities"
    name = "api:escl_scan:capabilities"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass

    async def get(self, request: web.Request) -> web.Response:
        if set(request.query) - {"entity_id"} or len(request.query.getall("entity_id", [])) > 1:
            return self.json_message("invalid capability query", status_code=400)
        live = {key: data for key, data in self._hass.data.get(DOMAIN, {}).items()
                if not key.startswith("_") and isinstance(data, dict) and "coordinator" in data}
        entity_id = request.query.get("entity_id")
        if not live:
            return self.json_message("integration not configured", status_code=503)
        registry = er.async_get(self._hass)
        if entity_id is not None:
            entity = registry.async_get(entity_id)
            if not entity or entity.platform != DOMAIN or entity.domain != "sensor":
                return self.json_message("target is not an eSCL scan sensor", status_code=404)
            entry_id = entity.config_entry_id
            if entry_id not in live:
                return self.json_message("target scanner is not loaded", status_code=404)
        elif len(live) == 1:
            entry_id = next(iter(live))
            entity_id = next((entry.entity_id for entry in er.async_entries_for_config_entry(
                registry, entry_id
            ) if entry.domain == "sensor"), None)
        else:
            return self.json_message("select a scanner with entity_id", status_code=400)
        coord = live[entry_id]["coordinator"]
        await coord.async_refresh_capabilities()
        if coord.capability_cache.closed:
            return self.json_message("integration unloaded", status_code=503)
        return self.json(capability_snapshot(coord.capability_cache, entity_id))


def _target_coordinator(hass: HomeAssistant, entity_id) -> ScanCoordinator | None:
    """Resolve a requested scan sensor; old requests may omit the single target."""
    if entity_id is None:
        return _current_coordinator(hass)
    entity = er.async_get(hass).async_get(entity_id) if isinstance(entity_id, str) else None
    if entity is None or entity.platform != DOMAIN or entity.domain != "sensor":
        raise ValueError("Select a scan sensor from the eSCL Scan integration.")
    coord = hass.data.get(DOMAIN, {}).get(entity.config_entry_id, {}).get("coordinator")
    if coord is None:
        raise ValueError("The selected scanner is not loaded. Check the integration.")
    return coord


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
            data = await request.json() if request.can_read_body else {}
        except ValueError:
            return self.json_message("invalid JSON", status_code=400)
        if not isinstance(data, dict):
            return self.json_message("JSON body must be an object", status_code=400)

        source = data.get("source")
        if source not in (None, "Platen", "Feeder"):
            return self.json_message("invalid 'source'", status_code=400)
        dpi = data.get("dpi")
        if dpi is not None and (type(dpi) is not int or dpi < 50 or dpi > 1200):
            return self.json_message("invalid 'dpi'", status_code=400)
        color = data.get("color")
        if color not in (None, "color", "gray"):
            return self.json_message("invalid 'color' (must be 'color' or 'gray')", status_code=400)
        duplex = data.get("duplex")
        if duplex is not None and not isinstance(duplex, bool):
            return self.json_message("invalid 'duplex' (must be a boolean)", status_code=400)

        try:
            coord = _target_coordinator(self._hass, data.get("entity_id"))
        except ValueError as exc:
            return self.json_message(str(exc), status_code=404)
        if coord is None:
            return self.json_message("integration not configured", status_code=503)
        try:
            scan = await coord.start_scan(
                source=source, dpi=dpi, color=color, duplex=duplex,
                page_size=data.get("page_size", "full"), width=data.get("width"),
                height=data.get("height"),
            )
        except ScanBusyError:
            current = coord.current
            if current is not None and current.state == "awaiting-back-sides":
                message = (
                    "A two-sided scan is waiting for the back sides. Load them and choose "
                    "Scan back sides, or cancel that scan before starting a new one."
                )
            elif current is not None and current.is_terminal():
                message = "The previous scan is finishing. Wait a few seconds, then try again."
            elif current is not None:
                message = (
                    "Another scan is in progress. Wait for it to finish, or cancel it "
                    "before starting a new scan."
                )
            else:
                message = (
                    "The scanner is starting or reconnecting. Wait a few seconds, then try again."
                )
            return self.json_message(message, status_code=409)
        except ValueError as exc:
            return self.json_message(str(exc), status_code=400)
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
                "duplex_mode": scan.duplex_mode,
                "scan_phase": scan.scan_phase,
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
        try:
            coord = _target_coordinator(self._hass, data.get("entity_id"))
        except ValueError as exc:
            return self.json_message(str(exc), status_code=404)
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
                "scan is already finishing or terminal",
                status_code=409,
            )
        return self.json({"ok": True, "scan_id": scan_id})


class ScanBacksView(ScanCancelView):
    """Resume a manual duplex scan after its backs have been loaded."""

    url = "/api/escl_scan/scan_backs"
    name = "api:escl_scan:scan_backs"

    async def post(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
        except ValueError:
            return self.json_message("invalid JSON", status_code=400)
        scan_id = data.get("scan_id") if isinstance(data, dict) else None
        if not isinstance(scan_id, str) or not scan_id:
            return self.json_message("missing or invalid 'scan_id'", status_code=400)
        reverse_back_order = data.get("reverse_back_order", False)
        if not isinstance(reverse_back_order, bool):
            return self.json_message("'reverse_back_order' must be a boolean", status_code=400)
        try:
            coord = _target_coordinator(self._hass, data.get("entity_id"))
        except ValueError as exc:
            return self.json_message(str(exc), status_code=404)
        if coord is None:
            return self.json_message("integration not configured", status_code=503)
        if coord.get(scan_id) is None:
            return self.json_message("scan not found", status_code=404)
        try:
            scan = await coord.async_scan_backs(scan_id, reverse_back_order=reverse_back_order)
        except ValueError as exc:
            return self.json_message(str(exc), status_code=409)
        except Exception:
            _LOGGER.exception("back-side scan kickoff failed")
            return self.json_message("could not check the scanner; try again", status_code=502)
        return self.json({"ok": True, "scan_id": scan_id, "state": scan.state})


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
        latest = coord.latest.snapshot()
        if scan is None and (not latest or latest["scan_id"] != scan_id):
            return self.json_message("not found", status_code=404)
        if scan is not None and scan.state != "completed":
            return self.json_message(
                f"scan not ready (state={scan.state})", status_code=409,
            )
        result = await coord.async_download_file(scan_id)
        if result is None:
            return self.json_message(
                "file expired or missing on disk", status_code=404,
            )
        return web.FileResponse(
            result[0],
            headers={
                "Content-Type": "application/pdf",
                "Content-Disposition": f'inline; filename="{result[1]}"',
                "Cache-Control": "private, no-store",
            },
        )
