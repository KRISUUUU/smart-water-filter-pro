"""Diagnostics support for Smart Water Filter."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.components.diagnostics import async_redact_data

from .const import DOMAIN, CONF_SOURCE_SENSOR
from .coordinator import SmartWaterCoordinator

TO_REDACT = {
    CONF_SOURCE_SENSOR,
}

async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: SmartWaterCoordinator = hass.data[DOMAIN][entry.entry_id]

    diagnostics_data = {
        "config_entry": {
            "title": entry.title,
            "data": {k: v for k, v in entry.data.items()},
            "options": entry.options,
        },
        "coordinator_data": {
            k: v for k, v in coordinator.data.items() if k != "events"
        },
        "event_logs_count": len(coordinator.data.get("events", [])),
    }

    # Redact sensitive parameters (e.g. source sensor entity ID)
    return async_redact_data(diagnostics_data, TO_REDACT)
