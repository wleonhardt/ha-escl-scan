"""Shared constants."""
from __future__ import annotations

DOMAIN = "escl_scan"

# Config-entry data keys.
CONF_HOST = "host"
CONF_BASE_PATH = "base_path"  # eSCL resource path from mDNS `rs`, default "eSCL"
CONF_PORT = "port"
CONF_USE_TLS = "use_tls"
CONF_USER = "user"
CONF_PASSWORD = "password"
CONF_VERIFY_TLS = "verify_tls"
CONF_RELAXED_CIPHERS = "relaxed_ciphers"
CONF_DEFAULT_DPI = "default_dpi"
CONF_DEFAULT_COLOR = "default_color"
CONF_FILE_TTL = "file_ttl_seconds"
CONF_DEFAULT_DUPLEX = "default_duplex"

DEFAULT_PORT = 443
DEFAULT_BASE_PATH = "eSCL"
DEFAULT_USER = "anonymous"
DEFAULT_DPI = 300
DEFAULT_COLOR = "color"  # "color" | "gray"
DEFAULT_DUPLEX = False  # only honoured for Feeder scans on duplex-capable ADFs
DEFAULT_FILE_TTL = 3600  # 1h

# Card asset served via content-hash URL.
CARD_FILENAME = "card.js"
CARD_URL_PREFIX = "/escl_scan/card-"

# File storage subdir under hass.config.path(".storage/").
STORAGE_SUBDIR = "escl_scan"

# Public event names.
EVENT_STATE_CHANGED = "escl_scan_state_changed"
EVENT_COMPLETED = "escl_scan_completed"
