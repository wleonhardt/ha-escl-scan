"""Config flow for eSCL Scan."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
import voluptuous as vol

from .const import (
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
    DEFAULT_COLOR,
    DEFAULT_DPI,
    DEFAULT_DUPLEX,
    DEFAULT_FILE_TTL,
    DEFAULT_PORT,
    DEFAULT_USER,
    DOMAIN,
)
from .scanner import ScannerClient

# Mask the credential in both flows instead of showing it in plain text.
_PASSWORD_SELECTOR = TextSelector(
    TextSelectorConfig(type=TextSelectorType.PASSWORD)
)
_PORT = vol.All(vol.Coerce(int), vol.Range(min=1, max=65535))
_DPI = vol.All(vol.Coerce(int), vol.Range(min=50, max=1200))
_TTL = vol.All(vol.Coerce(int), vol.Range(min=0))


class EsclScanConfigFlow(ConfigFlow, domain=DOMAIN):
    """Ask the user for scanner connection details and validate with a
    ScannerStatus probe. Any well-formed eSCL response confirms the path."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
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
                await self.async_set_unique_id(
                    device_id
                    or f"{user_input[CONF_HOST]}:{user_input.get(CONF_PORT, DEFAULT_PORT)}"
                )
                self._abort_if_unique_id_configured()
                model = caps.make_and_model if caps else None
                return self.async_create_entry(
                    title=model or f"eSCL scanner at {user_input[CONF_HOST]}",
                    data=user_input,
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): _PORT,
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
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        data = {**self.config_entry.data, **self.config_entry.options}
        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=data.get(CONF_HOST, "")): str,
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
                    CONF_FILE_TTL, default=data.get(CONF_FILE_TTL, DEFAULT_FILE_TTL)
                ): _TTL,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
