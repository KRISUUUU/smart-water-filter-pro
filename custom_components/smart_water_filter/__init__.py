"""Smart Water Filter integration setup and platform forwards."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.helpers import config_validation as cv

from .const import (
    DOMAIN,
    CONF_SOURCE_SENSOR,
    CONF_SOURCE_TYPE,
    CONF_PULSES_PER_LITER,
)
from .coordinator import SmartWaterCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "binary_sensor", "button", "number", "select"]

# Service Schema Definitions
RESET_FILTER_SCHEMA = vol.Schema({
    vol.Optional("capacity"): vol.Coerce(float),
    vol.Optional("reason"): cv.string,
})

FINISH_CALIBRATION_SCHEMA = vol.Schema({
    vol.Required("actual_volume"): vol.Coerce(float),
})

SET_LEAK_MODE_SCHEMA = vol.Schema({
    vol.Required("mode"): vol.In(["standard", "kitchen_ro", "away", "disabled"]),
})

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Smart Water Filter from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    coordinator = SmartWaterCoordinator(hass, entry)
    await coordinator.async_setup()
    
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Forward entry setups to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services
    async def handle_reset_filter(call: ServiceCall) -> None:
        cap = call.data.get("capacity")
        reason = call.data.get("reason", "manual")
        await coordinator.async_reset_filter(new_capacity=cap, reason=reason)

    async def handle_clear_alarm(call: ServiceCall) -> None:
        await coordinator.async_clear_alarm()

    async def handle_start_calibration(call: ServiceCall) -> None:
        await coordinator.async_start_calibration()

    async def handle_finish_calibration(call: ServiceCall) -> ServiceResponse:
        vol_liters = call.data["actual_volume"]
        new_factor = await coordinator.async_finish_calibration(vol_liters)
        return {"new_calibration_factor": new_factor}

    async def handle_set_leak_mode(call: ServiceCall) -> None:
        mode = call.data["mode"]
        await coordinator.async_set_leak_detection_mode(mode)

    async def handle_export_history(call: ServiceCall) -> ServiceResponse:
        # Returns current states and event history
        return {
            "lifetime_total_liters": coordinator.lifetime_total_liters,
            "today_used_liters": coordinator.today_used_liters,
            "current_flow_rate": coordinator.current_flow_rate,
            "filter_remaining_liters": coordinator.filter_engine.remaining_liters,
            "filter_percentage": coordinator.filter_engine.percentage,
            "filter_health_score": coordinator.filter_engine.health_score,
            "filter_health_status": coordinator.filter_engine.health_status,
            "filter_installed_date": coordinator.filter_engine.installed_date,
            "estimated_days": coordinator.data["estimated_days"],
            "leak_events_total": coordinator.leak_engine.leak_events_total,
            "pulses_per_liter": coordinator.pulses_per_liter,
            "events": coordinator.event_logger.to_list(),
            "history": coordinator.filter_engine.history,
        }

    hass.services.async_register(
        DOMAIN, "reset_filter", handle_reset_filter, schema=RESET_FILTER_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "clear_alarm", handle_clear_alarm
    )
    hass.services.async_register(
        DOMAIN, "start_calibration", handle_start_calibration
    )
    hass.services.async_register(
        DOMAIN, "finish_calibration", handle_finish_calibration,
        schema=FINISH_CALIBRATION_SCHEMA,
        supports_response=SupportsResponse.ONLY
    )
    hass.services.async_register(
        DOMAIN, "set_leak_mode", handle_set_leak_mode, schema=SET_LEAK_MODE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "export_history", handle_export_history,
        supports_response=SupportsResponse.ONLY
    )

    # Register reload update listener
    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        # Unsubscribe state listener inside coordinator
        coordinator = hass.data[DOMAIN].pop(entry.entry_id)
        if coordinator._unsub_state:
            coordinator._unsub_state()

        # Remove services if no other entries exist
        if not hass.data[DOMAIN]:
            for svc in ["reset_filter", "clear_alarm", "start_calibration", "finish_calibration", "set_leak_mode", "export_history"]:
                hass.services.async_remove(DOMAIN, svc)

    return unload_ok

async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options/config entry update updates."""
    await hass.config_entries.async_reload(entry.entry_id)
