"""Pytest bootstrap for the escl_scan test suite.

Uses pytest-homeassistant-custom-component for the real `hass` fixture. Keep
this at the repo root so `custom_components.escl_scan...` imports resolve.
"""
import pytest

pytest_plugins = ["pytest_homeassistant_custom_component"]


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Let HA load the escl_scan custom component during tests."""
    yield
