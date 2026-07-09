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
    vol.Required("stage_id"): cv.string,
    vol.Optional("capacity"): vol.Coerce(float),
    vol.Optional("reason"): cv.string,
})

ADD_FILTER_STAGE_SCHEMA = vol.Schema({
    vol.Required("name"): cv.string,
    vol.Required("type"): vol.In(["carbon", "capillary", "sediment", "custom"]),
    vol.Optional("capacity"): vol.Coerce(float),
    vol.Optional("max_age_days"): vol.Coerce(float),
})

REMOVE_FILTER_STAGE_SCHEMA = vol.Schema({
    vol.Required("stage_id"): cv.string,
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
        stage_id = call.data["stage_id"]
        cap = call.data.get("capacity")
        reason = call.data.get("reason", "manual")
        await coordinator.async_reset_filter(stage_id=stage_id, new_capacity=cap, reason=reason)

    async def handle_add_filter_stage(call: ServiceCall) -> None:
        name = call.data["name"]
        stype = call.data["type"]
        cap = call.data.get("capacity", 3000.0)
        max_age = call.data.get("max_age_days", 365.0)
        await coordinator.async_add_filter_stage(
            name=name,
            stage_type=stype,
            capacity_liters=cap,
            max_age_days=max_age,
        )

    async def handle_remove_filter_stage(call: ServiceCall) -> None:
        stage_id = call.data["stage_id"]
        await coordinator.async_remove_filter_stage(stage_id=stage_id)

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
            "stages": [
                {
                    "id": stage.id,
                    "name": stage.name,
                    "type": stage.type,
                    "capacity_liters": stage.capacity_liters,
                    "used_liters": stage.used_liters,
                    "remaining_liters": stage.remaining_liters,
                    "percentage": stage.percentage,
                    "health_score": stage.health_score,
                    "health_status": stage.health_status,
                    "history": stage.history,
                }
                for stage in coordinator.filter_engine.stages.values()
            ],
            "leak_events_total": coordinator.leak_engine.leak_events_total,
            "pulses_per_liter": coordinator.pulses_per_liter,
            "events": coordinator.event_logger.to_list(),
        }

    hass.services.async_register(
        DOMAIN, "reset_filter", handle_reset_filter, schema=RESET_FILTER_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "add_filter_stage", handle_add_filter_stage, schema=ADD_FILTER_STAGE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "remove_filter_stage", handle_remove_filter_stage, schema=REMOVE_FILTER_STAGE_SCHEMA
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
            for svc in [
                "reset_filter",
                "add_filter_stage",
                "remove_filter_stage",
                "clear_alarm",
                "start_calibration",
                "finish_calibration",
                "set_leak_mode",
                "export_history"
            ]:
                hass.services.async_remove(DOMAIN, svc)

    return unload_ok

async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options/config entry update updates."""
    await hass.config_entries.async_reload(entry.entry_id)
