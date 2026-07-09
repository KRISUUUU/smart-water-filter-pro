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
        return SmartWaterOptionsFlow(config_entry)


class SmartWaterOptionsFlow(config_entries.OptionsFlow):
    """Handle options updates for Smart Water Filter."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage option updates."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # Get list of sensor entities in the system
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

        schema = vol.Schema({
            vol.Required(CONF_SOURCE_SENSOR, default=current_sensor): vol.In(entities),
            vol.Required(CONF_SOURCE_TYPE, default=current_type): vol.In([
                SOURCE_TYPE_PULSES,
                SOURCE_TYPE_LITERS,
            ]),
            vol.Required(CONF_PULSES_PER_LITER, default=current_pulses): vol.Coerce(float),
        })

        return self.async_show_form(step_id="init", data_schema=schema)
