"""Number platform for Smart Water Filter."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import SmartWaterBaseEntity
from .coordinator import SmartWaterCoordinator

GLOBAL_NUMBER_DESCRIPTIONS = [
    NumberEntityDescription(
        key="pulses_per_liter",
        translation_key="pulses_per_liter",
        native_min_value=10.0,
        native_max_value=2000.0,
        native_step=0.1,
    ),
]

STAGE_CAPACITY_DESCRIPTION = NumberEntityDescription(
    key="stage_capacity",
    native_min_value=100.0,
    native_max_value=20000.0,
    native_step=50.0,
    native_unit_of_measurement="L",
)

STAGE_MAX_AGE_DESCRIPTION = NumberEntityDescription(
    key="stage_max_age",
    native_min_value=30.0,
    native_max_value=1095.0,  # 3 years
    native_step=1.0,
    native_unit_of_measurement="d",
)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Smart Water Filter number entities."""
    coordinator: SmartWaterCoordinator = hass.data[DOMAIN][entry.entry_id]
    
    entities: list[NumberEntity] = []
    
    # 1. Register global number entities
    for description in GLOBAL_NUMBER_DESCRIPTIONS:
        entities.append(SmartWaterNumber(coordinator, description))
        
    # 2. Register dynamic stage number entities
    for stage_id, stage_data in coordinator.data["stages"].items():
        stage_name = stage_data["name"]
        entities.append(
            SmartWaterStageNumber(coordinator, stage_id, stage_name, "capacity", STAGE_CAPACITY_DESCRIPTION)
        )
        entities.append(
            SmartWaterStageNumber(coordinator, stage_id, stage_name, "max_age", STAGE_MAX_AGE_DESCRIPTION)
        )
        
    async_add_entities(entities)

class SmartWaterNumber(SmartWaterBaseEntity, NumberEntity):
    """Smart Water Filter Global Number Setting."""

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
        if self.entity_description.key == "pulses_per_liter":
            return self.coordinator.data["pulses_per_liter"]
        return None

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        if self.entity_description.key == "pulses_per_liter":
            self.coordinator.pulses_per_liter = value
            self.coordinator.flow_engine.pulses_per_liter = value
            await self.coordinator.async_save_state()
            await self.coordinator.async_request_refresh()

class SmartWaterStageNumber(SmartWaterBaseEntity, NumberEntity):
    """Smart Water Filter Stage-Specific Number Setting (Capacity or Max Age)."""

    def __init__(
        self,
        coordinator: SmartWaterCoordinator,
        stage_id: str,
        stage_name: str,
        metric: str,
        description: NumberEntityDescription,
    ) -> None:
        """Initialize the stage-specific number entity."""
        super().__init__(coordinator, f"{stage_id}_{metric}")
        self.entity_description = description
        self.stage_id = stage_id
        self.stage_name = stage_name
        self.metric = metric
        
        # Override unique ID and translation options
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{stage_id}_{metric}"
        self._attr_translation_key = f"stage_{metric}"
        self._attr_translation_placeholders = {"stage_name": stage_name}

    @property
    def native_value(self) -> float | None:
        """Return the entity value."""
        stage_data = self.coordinator.data["stages"].get(self.stage_id)
        if not stage_data:
            return None
        
        if self.metric == "capacity":
            return stage_data.get("capacity_liters")
        elif self.metric == "max_age":
            return stage_data.get("max_age_days")
        return None

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        if self.metric == "capacity":
            await self.coordinator.async_set_filter_capacity(self.stage_id, value)
        elif self.metric == "max_age":
            await self.coordinator.async_set_filter_max_age(self.stage_id, value)
