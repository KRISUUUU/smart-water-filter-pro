"""Config flow to configure Smart Water Filter integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
import voluptuous as vol

from .const import (
    DOMAIN,
    CONF_SOURCE_SENSOR,
    CONF_SOURCE_TYPE,
    CONF_PULSES_PER_LITER,
    SOURCE_TYPE_PULSES,
    SOURCE_TYPE_LITERS,
    DEFAULT_PULSES_PER_LITER,
    localize_stage_name,
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
            source = user_input[CONF_SOURCE_SENSOR]
            await self.async_set_unique_id(source)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=f"Smart Filter ({source})",
                data=user_input,
            )

        entities = self.hass.states.async_entity_ids("sensor")

        schema = vol.Schema({
            vol.Required(CONF_SOURCE_SENSOR): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Required(CONF_SOURCE_TYPE, default=SOURCE_TYPE_PULSES): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[SOURCE_TYPE_PULSES, SOURCE_TYPE_LITERS],
                    translation_key="source_type",
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
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
        self.calibration_start_pulses: float = 0.0

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage option updates main menu."""
        if user_input is not None:
            action = user_input["action"]
            if action == "sensor_leak_settings":
                return await self.async_step_sensor_leak_settings()
            elif action == "calibrate_sensor":
                return await self.async_step_calibration_start()
            elif action == "add_stage":
                return await self.async_step_add_stage()
            elif action == "remove_stage":
                return await self.async_step_remove_stage()
            elif action == "edit_stage":
                return await self.async_step_edit_stage()
            elif action == "reset_stage":
                return await self.async_step_reset_stage()

        # POPRAWKA: Użycie oficjalnego SelectSelector zamiast surowego słownika
        schema = vol.Schema({
            vol.Required("action"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        "sensor_leak_settings",
                        "calibrate_sensor",
                        "add_stage",
                        "remove_stage",
                        "edit_stage",
                        "reset_stage",
                    ],
                    translation_key="options_action",
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            )
        })

        return self.async_show_form(step_id="init", data_schema=schema)

    async def async_step_sensor_leak_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure main sensor and leak profile settings."""
        coordinator = self.hass.data[DOMAIN][self.config_entry.entry_id]

        if user_input is not None:
            coordinator.source_sensor = user_input[CONF_SOURCE_SENSOR]
            coordinator.source_type = user_input[CONF_SOURCE_TYPE]
            coordinator.pulses_per_liter = user_input[CONF_PULSES_PER_LITER]
            coordinator.flow_engine.pulses_per_liter = user_input[CONF_PULSES_PER_LITER]
            
            await coordinator.async_set_leak_detection_mode(user_input["leak_detection_mode"])
            await coordinator.async_save_state()

            return self.async_create_entry(title="", data=user_input)

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

        schema = vol.Schema({
            vol.Required(CONF_SOURCE_SENSOR, default=current_sensor): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Required(CONF_SOURCE_TYPE, default=current_type): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[SOURCE_TYPE_PULSES, SOURCE_TYPE_LITERS],
                    translation_key="source_type",
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(CONF_PULSES_PER_LITER, default=current_pulses): vol.Coerce(float),
            vol.Required("leak_detection_mode", default=current_leak_mode): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=["standard", "kitchen_ro", "away", "disabled"],
                    translation_key="leak_detection_mode",
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
        })

        return self.async_show_form(step_id="sensor_leak_settings", data_schema=schema)

    async def async_step_calibration_start(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Start dynamic flow sensor calibration."""
        coordinator = self.hass.data[DOMAIN][self.config_entry.entry_id]

        if user_input is not None:
            state = self.hass.states.get(coordinator.source_sensor)
            try:
                self.calibration_start_pulses = float(state.state) if state else 0.0
            except ValueError:
                self.calibration_start_pulses = 0.0

            await coordinator.async_start_calibration()
            return await self.async_step_calibration_stop()

        return self.async_show_form(step_id="calibration_start")

    async def async_step_calibration_stop(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Finish dynamic flow sensor calibration and update settings."""
        coordinator = self.hass.data[DOMAIN][self.config_entry.entry_id]

        if user_input is not None:
            volume = user_input["volume_liters"]
            state = self.hass.states.get(coordinator.source_sensor)
            try:
                end_pulses = float(state.state) if state else 0.0
            except ValueError:
                end_pulses = 0.0

            start_pulses = getattr(self, "calibration_start_pulses", 0.0)
            if end_pulses >= start_pulses:
                delta_pulses = end_pulses - start_pulses
            else:
                delta_pulses = end_pulses

            if volume > 0.05 and delta_pulses > 1.0:
                new_factor = round(delta_pulses / volume, 2)
                coordinator.pulses_per_liter = new_factor
                coordinator.flow_engine.pulses_per_liter = new_factor

                new_options = {**self.config_entry.options, CONF_PULSES_PER_LITER: new_factor}
                self.hass.config_entries.async_update_entry(self.config_entry, options=new_options)
                await coordinator.async_save_state()
                await self.hass.config_entries.async_reload(self.config_entry.entry_id)

            await coordinator.async_finish_calibration(volume)
            return self.async_create_entry(title="", data=self.config_entry.options)

        schema = vol.Schema({
            vol.Required("volume_liters", default=1.0): vol.Coerce(float),
        })

        return self.async_show_form(step_id="calibration_stop", data_schema=schema)

    async def async_step_add_stage(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Add new stage preset step."""
        if user_input is not None:
            preset = user_input["preset_type"]
            self.temp_preset_type = preset
            
            if preset == "custom":
                return await self.async_step_add_stage_custom()
            
            return await self.async_step_add_stage_preset_details()

        # POPRAWKA: Selektor dla preset_type
        schema = vol.Schema({
            vol.Required("preset_type"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        "carbon_1",
                        "carbon_2",
                        "sediment_5um",
                        "sediment_10um",
                        "sediment_20um",
                        "membrana_ro",
                        "capillary",
                        "custom",
                    ],
                    translation_key="preset_type",
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
        })

        return self.async_show_form(step_id="add_stage", data_schema=schema)

    async def async_step_add_stage_preset_details(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure capacity and lifespan for a preset stage before adding it."""
        preset = self.temp_preset_type
        defaults = {
            "carbon_1": (4000.0, 365.0, "Carbon Filter 1"),
            "carbon_2": (4000.0, 365.0, "Carbon Filter 2"),
            "sediment_5um": (3000.0, 180.0, "Sediment Filter 5um"),
            "sediment_10um": (3000.0, 180.0, "Sediment Filter 10um"),
            "sediment_20um": (3000.0, 180.0, "Sediment Filter 20um"),
            "membrana_ro": (10000.0, 730.0, "RO Membrane"),
            "capillary": (5000.0, 365.0, "Capillary Filter"),
        }
        default_cap, default_age, default_name = defaults.get(preset, (3000.0, 365.0, "Filter Stage"))

        if user_input is not None:
            cap = user_input["capacity_liters"]
            max_age = user_input["max_age_days"]

            coordinator = self.hass.data[DOMAIN][self.config_entry.entry_id]
            await coordinator.async_add_filter_stage(
                name=default_name,
                stage_type=preset,
                capacity_liters=cap,
                max_age_days=max_age,
            )
            return self.async_create_entry(title="", data=self.config_entry.options)

        schema = vol.Schema({
            vol.Required("capacity_liters", default=default_cap): vol.Coerce(float),
            vol.Required("max_age_days", default=default_age): vol.Coerce(float),
        })

        return self.async_show_form(step_id="add_stage_preset_details", data_schema=schema)

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

        schema = vol.Schema({
            vol.Required("name"): str,
            vol.Required("capacity_liters", default=6000.0): vol.Coerce(float),
            vol.Required("max_age_days", default=365.0): vol.Coerce(float),
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

        stages = coordinator.filter_engine.stages
        if not stages:
            return self.async_abort(reason="no_stages")

        # POPRAWKA: Selector dla dynamicznych obiektów
        options = [
            {"value": sid, "label": f"{localize_stage_name(self.hass, s.name)} ({localize_stage_name(self.hass, s.type)})"}
            for sid, s in stages.items()
        ]

        schema = vol.Schema({
            vol.Required("stage_id"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=options,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
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

        stages = coordinator.filter_engine.stages
        if not stages:
            return self.async_abort(reason="no_stages")

        # POPRAWKA: Selector dla dynamicznych obiektów
        options = [
            {"value": sid, "label": f"{localize_stage_name(self.hass, s.name)} ({localize_stage_name(self.hass, s.type)})"}
            for sid, s in stages.items()
        ]

        schema = vol.Schema({
            vol.Required("stage_id"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=options,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
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

    async def async_step_reset_stage(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Reset a filter stage."""
        coordinator = self.hass.data[DOMAIN][self.config_entry.entry_id]

        if user_input is not None:
            stage_id = user_input["stage_id"]
            reason = user_input.get("reason", "routine")
            await coordinator.async_reset_filter(stage_id, reason=reason)
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            return self.async_create_entry(title="", data=self.config_entry.options)

        stages = coordinator.filter_engine.stages
        if not stages:
            return self.async_abort(reason="no_stages")

        options = [
            {"value": sid, "label": f"{localize_stage_name(self.hass, s.name)} ({localize_stage_name(self.hass, s.type)})"}
            for sid, s in stages.items()
        ]

        schema = vol.Schema({
            vol.Required("stage_id"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=options,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required("reason", default="routine"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=["routine", "taste", "clogged", "time"],
                    translation_key="replacement_reason",
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
        })

        return self.async_show_form(step_id="reset_stage", data_schema=schema)