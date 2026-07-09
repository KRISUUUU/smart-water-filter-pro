"""Config flow to configure Smart Water Filter integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
import voluptuous as vol

from .const import (
    DOMAIN,
    CONF_SOURCE_SENSOR,
    CONF_SOURCE_TYPE,
    CONF_PULSES_PER_LITER,
    SOURCE_TYPE_PULSES,
    SOURCE_TYPE_LITERS,
    DEFAULT_PULSES_PER_LITER,
)

_LOGGER = logging.getLogger(__name__)

class SmartWaterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Smart Water Filter."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle user step setup flow."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Prevent configuring duplicates
            source = user_input[CONF_SOURCE_SENSOR]
            await self.async_set_unique_id(source)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=f"Smart Filter ({source})",
                data=user_input,
            )

        # Get list of sensor entities in the system
        entities = self.hass.states.async_entity_ids("sensor")

        schema = vol.Schema({
            vol.Required(CONF_SOURCE_SENSOR): vol.In(entities),
            vol.Required(CONF_SOURCE_TYPE, default=SOURCE_TYPE_PULSES): vol.In([
                SOURCE_TYPE_PULSES,
                SOURCE_TYPE_LITERS,
            ]),
            vol.Required(CONF_PULSES_PER_LITER, default=DEFAULT_PULSES_PER_LITER): vol.Coerce(float),
        })

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> SmartWaterOptionsFlow:
        """Get the options flow for this entry."""
        return SmartWaterOptionsFlow()


class SmartWaterOptionsFlow(config_entries.OptionsFlow):
    """Handle options updates for Smart Water Filter."""

    def __init__(self) -> None:
        """Initialize options flow."""
        super().__init__()
        self.selected_stage_id: str | None = None
        self.temp_preset_type: str | None = None
        self.temp_stage_name: str | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage option updates main menu."""
        if user_input is not None:
            action = user_input["action"]
            if action == "sensor_leak_settings":
                return await self.async_step_sensor_leak_settings()
            elif action == "add_stage":
                return await self.async_step_add_stage()
            elif action == "remove_stage":
                return await self.async_step_remove_stage()
            elif action == "edit_stage":
                return await self.async_step_edit_stage()

        schema = vol.Schema({
            vol.Required("action"): vol.In({
                "sensor_leak_settings": "Configure Flow & Leak Settings",
                "add_stage": "Add New Filter Stage",
                "remove_stage": "Remove Filter Stage",
                "edit_stage": "View/Edit Filter Stages"
            })
        })

        return self.async_show_form(step_id="init", data_schema=schema)

    async def async_step_sensor_leak_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure main sensor and leak profile settings."""
        coordinator = self.hass.data[DOMAIN][self.config_entry.entry_id]

        if user_input is not None:
            # Update coordinator settings immediately
            coordinator.source_sensor = user_input[CONF_SOURCE_SENSOR]
            coordinator.source_type = user_input[CONF_SOURCE_TYPE]
            coordinator.pulses_per_liter = user_input[CONF_PULSES_PER_LITER]
            coordinator.flow_engine.pulses_per_liter = user_input[CONF_PULSES_PER_LITER]
            
            await coordinator.async_set_leak_detection_mode(user_input["leak_detection_mode"])
            await coordinator.async_set_replacement_reason(user_input["replacement_reason"])
            await coordinator.async_save_state()

            # Save options flow to trigger config entry reload
            return self.async_create_entry(title="", data=user_input)

        entities = self.hass.states.async_entity_ids("sensor")

        current_sensor = self.config_entry.options.get(
            CONF_SOURCE_SENSOR,
            self.config_entry.data.get(CONF_SOURCE_SENSOR)
        )
        current_type = self.config_entry.options.get(
            CONF_SOURCE_TYPE,
            self.config_entry.data.get(CONF_SOURCE_TYPE, SOURCE_TYPE_PULSES)
        )
        current_pulses = self.config_entry.options.get(
            CONF_PULSES_PER_LITER,
            self.config_entry.data.get(CONF_PULSES_PER_LITER, DEFAULT_PULSES_PER_LITER)
        )
        current_leak_mode = coordinator.leak_engine.detection_mode
        current_reason = coordinator.current_replacement_reason

        schema = vol.Schema({
            vol.Required(CONF_SOURCE_SENSOR, default=current_sensor): vol.In(entities),
            vol.Required(CONF_SOURCE_TYPE, default=current_type): vol.In([
                SOURCE_TYPE_PULSES,
                SOURCE_TYPE_LITERS,
            ]),
            vol.Required(CONF_PULSES_PER_LITER, default=current_pulses): vol.Coerce(float),
            vol.Required("leak_detection_mode", default=current_leak_mode): vol.In([
                "standard", "kitchen_ro", "away", "disabled"
            ]),
            vol.Required("replacement_reason", default=current_reason): vol.In([
                "routine", "taste", "clogged", "time"
            ]),
        })

        return self.async_show_form(step_id="sensor_leak_settings", data_schema=schema)

    async def async_step_add_stage(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Add new stage preset step."""
        if user_input is not None:
            preset = user_input["preset_type"]
            name = user_input.get("name")
            
            if preset == "custom":
                self.temp_preset_type = preset
                self.temp_stage_name = name
                return await self.async_step_add_stage_custom()
            
            # Preset types: use defaults
            defaults = {
                "carbon": (4000.0, 365.0, "Carbon Filter"),
                "capillary": (5000.0, 365.0, "Capillary Filter"),
                "sediment": (3000.0, 180.0, "Sediment Filter"),
            }
            cap, max_age, default_name = defaults.get(preset, (3000.0, 365.0, "Filter Stage"))
            stage_name = name if name and name.strip() else default_name

            coordinator = self.hass.data[DOMAIN][self.config_entry.entry_id]
            await coordinator.async_add_filter_stage(
                name=stage_name,
                stage_type=preset,
                capacity_liters=cap,
                max_age_days=max_age,
            )
            return self.async_create_entry(title="", data=self.config_entry.options)

        schema = vol.Schema({
            vol.Required("preset_type"): vol.In(["carbon", "capillary", "sediment", "custom"]),
            vol.Optional("name"): str,
        })

        return self.async_show_form(step_id="add_stage", data_schema=schema)

    async def async_step_add_stage_custom(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Add a custom filter stage with manual capacity and max age."""
        if user_input is not None:
            name = user_input["name"]
            cap = user_input["capacity_liters"]
            max_age = user_input["max_age_days"]

            coordinator = self.hass.data[DOMAIN][self.config_entry.entry_id]
            await coordinator.async_add_filter_stage(
                name=name,
                stage_type="custom",
                capacity_liters=cap,
                max_age_days=max_age,
            )
            return self.async_create_entry(title="", data=self.config_entry.options)

        default_name = self.temp_stage_name or ""
        schema = vol.Schema({
            vol.Required("name", default=default_name): str,
            vol.Required("capacity_liters", default=3000.0): vol.Coerce(float),
            vol.Required("max_age_days", default=365): vol.Coerce(int),
        })

        return self.async_show_form(step_id="add_stage_custom", data_schema=schema)

    async def async_step_remove_stage(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Remove filter stage step."""
        coordinator = self.hass.data[DOMAIN][self.config_entry.entry_id]

        if user_input is not None:
            stage_id = user_input["stage_id"]
            await coordinator.async_remove_filter_stage(stage_id)
            return self.async_create_entry(title="", data=self.config_entry.options)

        stages = {
            sid: f"{s.name} ({s.type})"
            for sid, s in coordinator.filter_engine.stages.items()
        }

        if not stages:
            return self.async_abort(reason="no_stages")

        schema = vol.Schema({
            vol.Required("stage_id"): vol.In(stages),
        })

        return self.async_show_form(step_id="remove_stage", data_schema=schema)

    async def async_step_edit_stage(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Select filter stage to edit."""
        coordinator = self.hass.data[DOMAIN][self.config_entry.entry_id]

        if user_input is not None:
            self.selected_stage_id = user_input["stage_id"]
            return await self.async_step_edit_stage_details()

        stages = {
            sid: f"{s.name} ({s.type})"
            for sid, s in coordinator.filter_engine.stages.items()
        }

        if not stages:
            return self.async_abort(reason="no_stages")

        schema = vol.Schema({
            vol.Required("stage_id"): vol.In(stages),
        })

        return self.async_show_form(step_id="edit_stage", data_schema=schema)

    async def async_step_edit_stage_details(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Edit selected stage details (capacity and max age)."""
        coordinator = self.hass.data[DOMAIN][self.config_entry.entry_id]
        stage = coordinator.filter_engine.stages[self.selected_stage_id]

        if user_input is not None:
            cap = user_input["capacity_liters"]
            max_age = user_input["max_age_days"]
            await coordinator.async_set_filter_capacity(self.selected_stage_id, cap)
            await coordinator.async_set_filter_max_age(self.selected_stage_id, max_age)
            return self.async_create_entry(title="", data=self.config_entry.options)

        schema = vol.Schema({
            vol.Required("capacity_liters", default=stage.capacity_liters): vol.Coerce(float),
            vol.Required("max_age_days", default=int(stage.max_age_days)): vol.Coerce(int),
        })

        return self.async_show_form(step_id="edit_stage_details", data_schema=schema)
