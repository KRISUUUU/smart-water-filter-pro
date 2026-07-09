"""Number platform for Smart Water Filter."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import SmartWaterBaseEntity
from .coordinator import SmartWaterCoordinator

NUMBER_DESCRIPTIONS = [
    NumberEntityDescription(
        key="filter_capacity",
        translation_key="filter_capacity",
        native_min_value=100.0,
        native_max_value=20000.0,
        native_step=50.0,
        native_unit_of_measurement="L",
    ),
    NumberEntityDescription(
        key="filter_max_age",
        translation_key="filter_max_age",
        native_min_value=30.0,
        native_max_value=1095.0,  # 3 years
        native_step=1.0,
        native_unit_of_measurement="d",
    ),
    NumberEntityDescription(
        key="pulses_per_liter",
        translation_key="pulses_per_liter",
        native_min_value=10.0,
        native_max_value=2000.0,
        native_step=0.1,
    ),
]

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Smart Water Filter number entities."""
    coordinator: SmartWaterCoordinator = hass.data[DOMAIN][entry.entry_id]
    
    entities = [
        SmartWaterNumber(coordinator, description)
        for description in NUMBER_DESCRIPTIONS
    ]
    async_add_entities(entities)

class SmartWaterNumber(SmartWaterBaseEntity, NumberEntity):
    """Smart Water Filter Number Setting."""

    def __init__(
        self,
        coordinator: SmartWaterCoordinator,
        description: NumberEntityDescription,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | None:
        """Return the entity value."""
        if self.entity_description.key == "filter_capacity":
            return self.coordinator.data["filter_capacity_liters"]
        elif self.entity_description.key == "filter_max_age":
            return self.coordinator.data["filter_max_age_days"]
        elif self.entity_description.key == "pulses_per_liter":
            return self.coordinator.data["pulses_per_liter"]
        return None

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        if self.entity_description.key == "filter_capacity":
            await self.coordinator.async_set_filter_capacity(value)
        elif self.entity_description.key == "filter_max_age":
            await self.coordinator.async_set_filter_max_age(value)
        elif self.entity_description.key == "pulses_per_liter":
            self.coordinator.pulses_per_liter = value
            self.coordinator.flow_engine.pulses_per_liter = value
            await self.coordinator.async_save_state()
            await self.coordinator.async_request_refresh()
