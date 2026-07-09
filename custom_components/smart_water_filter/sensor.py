"""Sensor platform for Smart Water Filter."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    UnitOfTime,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import SmartWaterBaseEntity
from .coordinator import SmartWaterCoordinator

@dataclass(frozen=True, kw_only=True)
class SmartWaterSensorEntityDescription(SensorEntityDescription):
    """Class describing Smart Water Filter sensor entities."""
    value_fn: Callable[[dict[str, Any]], Any]

GLOBAL_SENSOR_DESCRIPTIONS: list[SmartWaterSensorEntityDescription] = [
    # Water Usage Sensors
    SmartWaterSensorEntityDescription(
        key="water_total_liters",
        translation_key="water_total_liters",
        native_unit_of_measurement=UnitOfVolume.LITERS,
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data["lifetime_total_liters"],
    ),
    SmartWaterSensorEntityDescription(
        key="water_today_liters",
        translation_key="water_today_liters",
        native_unit_of_measurement=UnitOfVolume.LITERS,
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data["today_used_liters"],
    ),
    SmartWaterSensorEntityDescription(
        key="water_current_flow",
        translation_key="water_current_flow",
        native_unit_of_measurement="L/min",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["current_flow_rate"],
    ),
    SmartWaterSensorEntityDescription(
        key="water_average_flow",
        translation_key="water_average_flow",
        native_unit_of_measurement="L/min",
        value_fn=lambda data: data["average_flow_rate"],
    ),
    SmartWaterSensorEntityDescription(
        key="active_time_minutes",
        translation_key="active_time_minutes",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data["active_time_minutes"],
    ),
    SmartWaterSensorEntityDescription(
        key="last_flow_time",
        translation_key="last_flow_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data["last_flow_time"],
    ),
    SmartWaterSensorEntityDescription(
        key="water_usage_trend",
        translation_key="water_usage_trend",
        device_class=SensorDeviceClass.ENUM,
        options=["stable", "increasing", "decreasing"],
        value_fn=lambda data: data["usage_trend"],
    ),
]

STAGE_SENSOR_DESCRIPTIONS = {
    "remaining_liters": SensorEntityDescription(
        key="stage_remaining_liters",
        native_unit_of_measurement=UnitOfVolume.LITERS,
        device_class=SensorDeviceClass.WATER,
    ),
    "estimated_days": SensorEntityDescription(
        key="stage_remaining_days",
        native_unit_of_measurement=UnitOfTime.DAYS,
    ),
    "health_score": SensorEntityDescription(
        key="stage_health_score",
        native_unit_of_measurement="%",
    ),
}

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Smart Water Filter sensors."""
    coordinator: SmartWaterCoordinator = hass.data[DOMAIN][entry.entry_id]
    
    entities: list[SensorEntity] = []
    
    # 1. Register global entities
    for description in GLOBAL_SENSOR_DESCRIPTIONS:
        entities.append(SmartWaterSensor(coordinator, description))
        
    # 2. Register dynamic stage-specific entities
    for stage_id, stage_data in coordinator.data["stages"].items():
        stage_name = stage_data["name"]
        for metric, desc in STAGE_SENSOR_DESCRIPTIONS.items():
            entities.append(
                SmartWaterStageSensor(coordinator, stage_id, stage_name, metric, desc)
            )
            
    async_add_entities(entities)

class SmartWaterSensor(SmartWaterBaseEntity, SensorEntity):
    """Smart Water Filter Global Sensor."""

    entity_description: SmartWaterSensorEntityDescription

    def __init__(
        self,
        coordinator: SmartWaterCoordinator,
        description: SmartWaterSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)

class SmartWaterStageSensor(SmartWaterBaseEntity, SensorEntity):
    """Smart Water Filter Stage-Specific Sensor."""

    def __init__(
        self,
        coordinator: SmartWaterCoordinator,
        stage_id: str,
        stage_name: str,
        metric: str,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the stage-specific sensor."""
        super().__init__(coordinator, f"{stage_id}_{metric}")
        self.entity_description = description
        self.stage_id = stage_id
        self.stage_name = stage_name
        self.metric = metric
        
        # Override unique ID and translations using HAs deterministic stages guidelines
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{stage_id}_{metric}"
        self._attr_translation_key = f"stage_{metric}"
        self._attr_translation_placeholders = {"stage_name": stage_name}

    @property
    def native_value(self) -> Any:
        """Return the state of the stage sensor."""
        stage_data = self.coordinator.data["stages"].get(self.stage_id)
        if not stage_data:
            return None
        
        # Mapping metric keys
        if self.metric == "remaining_liters":
            return stage_data.get("remaining_liters")
        elif self.metric == "estimated_days":
            return stage_data.get("estimated_days")
        elif self.metric == "health_score":
            return stage_data.get("health_score")
        return None
