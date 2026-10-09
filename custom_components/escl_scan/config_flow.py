"""Config flow for eSCL Scan."""
from __future__ import annotations

from typing import Any
from urllib.parse import unquote

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
import voluptuous as vol

from .const import (
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
)
from .scanner import ScannerClient

_ZEROCONF_TLS_TYPE = "_uscans._tcp.local."

# Mask the credential in both flows instead of showing it in plain text.
_PASSWORD_SELECTOR = TextSelector(
    TextSelectorConfig(type=TextSelectorType.PASSWORD)
)
_PORT = vol.All(vol.Coerce(int), vol.Range(min=1, max=65535))
_DPI = vol.All(vol.Coerce(int), vol.Range(min=50, max=1200))
_TTL = vol.All(vol.Coerce(int), vol.Range(min=0))


def _base_path(value: str) -> str:
    decoded = unquote(value)
    if (len(value) > 512 or any(c in decoded for c in "?#\\\r\n")
            or "://" in decoded or any(part in (".", "..") for part in decoded.split("/"))):
        raise vol.Invalid("enter a scanner resource path, such as eSCL")
    return value.strip("/")


def _normalize_uuid(value: str | None) -> str | None:
    return value.strip().casefold().removeprefix("urn:uuid:").strip("{}") or None if value else None


class EsclScanConfigFlow(ConfigFlow, domain=DOMAIN):
    """Ask the user for scanner connection details and validate with a
    ScannerStatus probe. Any well-formed eSCL response confirms the path."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovered: dict[str, Any] = {}
        self._discovered_name = ""

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """eSCL scanners advertise _uscan._tcp (HTTP) / _uscans._tcp (HTTPS).
        TXT keys: `rs` = resource path (usually "eSCL"), `ty` = model name,
        `UUID` = device id. Never creates an entry without confirmation."""
        # TXT keys vary in case between vendors (HP: `uuid`, others: `UUID`).
        props = {str(k).lower(): v for k, v in discovery_info.properties.items()}
        host = discovery_info.host
        uuid = _normalize_uuid(props.get("uuid"))
        name = props.get("ty") or discovery_info.name.split(".", 1)[0]
        self._discovered = {
            CONF_HOST: host,
            CONF_PORT: discovery_info.port or DEFAULT_PORT,
            CONF_USE_TLS: discovery_info.type == _ZEROCONF_TLS_TYPE,
            CONF_BASE_PATH: _base_path(props.get("rs") or DEFAULT_BASE_PATH),
            CONF_USER: DEFAULT_USER,
            CONF_PASSWORD: "",
            CONF_VERIFY_TLS: False,
            CONF_RELAXED_CIPHERS: False,
        }
        for entry in self._async_current_entries():
            effective = {**entry.data, **entry.options}
            live = self.hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
            coordinator = live.get("coordinator")
            caps = coordinator.capabilities if coordinator else None
            known = _normalize_uuid(
                entry.data.get("discovery_uuid") or (caps.uuid if caps else None) or entry.unique_id
            )
            if uuid and known == uuid:
                # A serial-based legacy ID remains unchanged. Match UUID
                # only from saved/probed evidence, never infer it from a model.
                if (effective.get(CONF_USE_TLS, True) == self._discovered[CONF_USE_TLS]
                        and effective.get(CONF_BASE_PATH, DEFAULT_BASE_PATH).strip("/")
                        == self._discovered[CONF_BASE_PATH]):
                    changes = {CONF_HOST: host, CONF_PORT: self._discovered[CONF_PORT]}
                    self.hass.config_entries.async_update_entry(
                        entry, data={**entry.data, **changes, "discovery_uuid": uuid},
                        options={**entry.options,
                                 **{k: v for k, v in changes.items() if k in entry.options}},
                    )
                return self.async_abort(reason="already_configured")
        self._async_abort_entries_match({CONF_HOST: host})
        if uuid:
            self._discovered["discovery_uuid"] = uuid
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        await self.async_set_unique_id(uuid or f"{host}:{self._discovered[CONF_PORT]}")
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})
        self.context["title_placeholders"] = {"name": name}
        self._discovered_name = name
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if user_input is None:
            return self.async_show_form(
                step_id="zeroconf_confirm",
                description_placeholders={"name": self._discovered_name},
            )
        return self.async_create_entry(title=self._discovered_name, data=self._discovered)

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        # Enforce the single-scanner policy here so discovery can first
        # reconcile an existing scanner after its DHCP address changes.
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        errors: dict[str, str] = {}
        if user_input is not None:
            client = ScannerClient(
                host=user_input[CONF_HOST],
                port=user_input.get(CONF_PORT, DEFAULT_PORT),
                use_tls=user_input.get(CONF_USE_TLS, True),
                user=user_input.get(CONF_USER) or DEFAULT_USER,
                password=user_input.get(CONF_PASSWORD, ""),
                verify_tls=user_input.get(CONF_VERIFY_TLS, False),
                relaxed_ciphers=user_input.get(CONF_RELAXED_CIPHERS, False),
                timeout=10.0,
                base_path=user_input.get(CONF_BASE_PATH, DEFAULT_BASE_PATH),
            )
            caps = None
            try:
                await client.get_scanner_status()
                try:
                    caps = await client.get_capabilities()
                except Exception:  # noqa: BLE001 — optional endpoint
                    caps = None
            except Exception as exc:
                errors["base"] = "cannot_connect"
                self._last_error = str(exc)
            finally:
                await client.async_close()
            if not errors:
                # Serial/UUID survives a DHCP address change; host:port is
                # the fallback for devices that don't serve capabilities.
                device_id = caps.device_id if caps else None
                if caps and caps.uuid:
                    user_input["discovery_uuid"] = _normalize_uuid(caps.uuid)
                await self.async_set_unique_id(
                    device_id
                    or f"{user_input[CONF_HOST]}:{user_input.get(CONF_PORT, DEFAULT_PORT)}"
                )
                self._abort_if_unique_id_configured()
                if self._async_current_entries():
                    return self.async_abort(reason="single_instance_allowed")
                model = caps.make_and_model if caps else None
                return self.async_create_entry(
                    title=model or f"eSCL scanner at {user_input[CONF_HOST]}",
                    data=user_input,
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): _PORT,
                vol.Optional(CONF_BASE_PATH, default=DEFAULT_BASE_PATH): vol.All(str, _base_path),
                vol.Optional(CONF_USE_TLS, default=True): bool,
                vol.Optional(CONF_USER, default=DEFAULT_USER): str,
                vol.Optional(CONF_PASSWORD, default=""): _PASSWORD_SELECTOR,
                vol.Optional(CONF_VERIFY_TLS, default=False): bool,
                vol.Optional(CONF_RELAXED_CIPHERS, default=False): bool,
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "error_detail": getattr(self, "_last_error", "") or ""
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return EsclScanOptionsFlow()


class EsclScanOptionsFlow(OptionsFlow):
    """Edit credentials/options without re-creating the entry.

    Note: modern HA injects `self.config_entry` automatically. The older
    pattern of accepting the entry in `__init__` short-circuits HA's
    update-listener wiring, which is why this class deliberately has no
    constructor.
    """

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            copy_dir = (user_input.get(CONF_COPY_DIR) or "").strip()
            user_input[CONF_COPY_DIR] = copy_dir
            if copy_dir and not self.hass.config.is_allowed_path(copy_dir):
                errors[CONF_COPY_DIR] = "path_not_allowed"
            else:
                return self.async_create_entry(title="", data=user_input)
        data = {**self.config_entry.data, **self.config_entry.options, **(user_input or {})}
        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=data.get(CONF_HOST, "")): str,
                vol.Optional(CONF_BASE_PATH, default=data.get(CONF_BASE_PATH, DEFAULT_BASE_PATH)):
                    vol.All(str, _base_path),
                vol.Optional(
                    CONF_PORT, default=data.get(CONF_PORT, DEFAULT_PORT)
                ): _PORT,
                vol.Optional(
                    CONF_USE_TLS, default=data.get(CONF_USE_TLS, True)
                ): bool,
                vol.Optional(
                    CONF_USER, default=data.get(CONF_USER, DEFAULT_USER)
                ): str,
                vol.Optional(
                    CONF_PASSWORD, default=data.get(CONF_PASSWORD, "")
                ): _PASSWORD_SELECTOR,
                vol.Optional(
                    CONF_VERIFY_TLS, default=data.get(CONF_VERIFY_TLS, False)
                ): bool,
                vol.Optional(
                    CONF_RELAXED_CIPHERS,
                    default=data.get(CONF_RELAXED_CIPHERS, False),
                ): bool,
                vol.Optional(
                    CONF_DEFAULT_DPI, default=data.get(CONF_DEFAULT_DPI, DEFAULT_DPI)
                ): _DPI,
                vol.Optional(
                    CONF_DEFAULT_COLOR,
                    default=data.get(CONF_DEFAULT_COLOR, DEFAULT_COLOR),
                ): vol.In(["color", "gray"]),
                vol.Optional(
                    CONF_DEFAULT_DUPLEX,
                    default=data.get(CONF_DEFAULT_DUPLEX, DEFAULT_DUPLEX),
                ): bool,
                vol.Optional(
                    CONF_ROTATE_DUPLEX_BACKS,
                    default=data.get(
                        CONF_ROTATE_DUPLEX_BACKS, DEFAULT_ROTATE_DUPLEX_BACKS
                    ),
                ): bool,
                vol.Optional(
                    CONF_FILE_TTL, default=data.get(CONF_FILE_TTL, DEFAULT_FILE_TTL)
                ): _TTL,
                vol.Optional(
                    CONF_COPY_DIR, default=data.get(CONF_COPY_DIR, "")
                ): str,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
