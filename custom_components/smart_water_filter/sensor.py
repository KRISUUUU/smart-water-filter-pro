"""Sensor platform for Smart Water Filter."""
from __future__ import annotations

from dataclasses import dataclass
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

SENSOR_DESCRIPTIONS: list[SmartWaterSensorEntityDescription] = [
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

    # Filter Volume Sensors
    SmartWaterSensorEntityDescription(
        key="filter_capacity",
        translation_key="filter_capacity",
        native_unit_of_measurement=UnitOfVolume.LITERS,
        device_class=SensorDeviceClass.WATER,
        value_fn=lambda data: data["filter_capacity_liters"],
    ),
    SmartWaterSensorEntityDescription(
        key="filter_used",
        translation_key="filter_used",
        native_unit_of_measurement=UnitOfVolume.LITERS,
        device_class=SensorDeviceClass.WATER,
        value_fn=lambda data: data["filter_used_liters"],
    ),
    SmartWaterSensorEntityDescription(
        key="filter_remaining",
        translation_key="filter_remaining",
        native_unit_of_measurement=UnitOfVolume.LITERS,
        device_class=SensorDeviceClass.WATER,
        value_fn=lambda data: data["filter_remaining_liters"],
    ),
    SmartWaterSensorEntityDescription(
        key="filter_percentage",
        translation_key="filter_percentage",
        native_unit_of_measurement="%",
        value_fn=lambda data: data["filter_percentage"],
    ),

    # Filter Lifetime & Degradation Sensors
    SmartWaterSensorEntityDescription(
        key="filter_max_age",
        translation_key="filter_max_age",
        native_unit_of_measurement=UnitOfTime.DAYS,
        value_fn=lambda data: data["filter_max_age_days"],
    ),
    SmartWaterSensorEntityDescription(
        key="filter_age_days",
        translation_key="filter_age_days",
        native_unit_of_measurement=UnitOfTime.DAYS,
        value_fn=lambda data: (datetime.now() - datetime.fromisoformat(data["filter_installed_date"])).days
        if data["filter_installed_date"] else 0,
    ),
    SmartWaterSensorEntityDescription(
        key="filter_flow_degradation",
        translation_key="filter_flow_degradation",
        native_unit_of_measurement="%",
        value_fn=lambda data: data["filter_flow_degradation"],
    ),
    SmartWaterSensorEntityDescription(
        key="filter_clogging_status",
        translation_key="filter_clogging_status",
        options=["normal", "warning", "restricted"],
        value_fn=lambda data: data["filter_clogging_status"],
    ),
    SmartWaterSensorEntityDescription(
        key="filter_health_score",
        translation_key="filter_health_score",
        native_unit_of_measurement="%",
        value_fn=lambda data: data["filter_health_score"],
    ),
    SmartWaterSensorEntityDescription(
        key="filter_health",
        translation_key="filter_health",
        options=["excellent", "good", "fair", "replace_soon", "replace_now"],
        value_fn=lambda data: data["filter_health_status"],
    ),
    SmartWaterSensorEntityDescription(
        key="water_usage_trend",
        translation_key="water_usage_trend",
        options=["stable", "increasing", "decreasing"],
        value_fn=lambda data: data["usage_trend"],
    ),
    SmartWaterSensorEntityDescription(
        key="estimated_days",
        translation_key="estimated_days",
        native_unit_of_measurement=UnitOfTime.DAYS,
        value_fn=lambda data: data["estimated_days"],
    ),
    SmartWaterSensorEntityDescription(
        key="confidence",
        translation_key="confidence",
        native_unit_of_measurement="%",
        value_fn=lambda data: data["confidence"],
    ),
]

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Smart Water Filter sensors."""
    coordinator: SmartWaterCoordinator = hass.data[DOMAIN][entry.entry_id]
    
    entities = [
        SmartWaterSensor(coordinator, description)
        for description in SENSOR_DESCRIPTIONS
    ]
    async_add_entities(entities)

from datetime import datetime

class SmartWaterSensor(SmartWaterBaseEntity, SensorEntity):
    """Smart Water Filter Sensor."""

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
