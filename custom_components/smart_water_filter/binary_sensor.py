"""Binary sensor platform for Smart Water Filter."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import SmartWaterBaseEntity
from .coordinator import SmartWaterCoordinator

@dataclass(frozen=True, kw_only=True)
class SmartWaterBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Class describing Smart Water Filter binary sensor entities."""
    is_on_fn: Callable[[dict[str, Any]], bool]
    extra_attributes_fn: Callable[[dict[str, Any]], dict[str, Any] | None] = lambda data: None

BINARY_SENSOR_DESCRIPTIONS: list[SmartWaterBinarySensorEntityDescription] = [
    SmartWaterBinarySensorEntityDescription(
        key="water_leak_alarm",
        translation_key="water_leak_alarm",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on_fn=lambda data: bool(data["leak_alarm_active"]),
        extra_attributes_fn=lambda data: {
            "severity": data["leak_severity"],
            "events_total": data["leak_events_total"],
        }
    ),
    SmartWaterBinarySensorEntityDescription(
        key="filter_replace",
        translation_key="filter_replace",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on_fn=lambda data: data["filter_health_status"] in ("replace_soon", "replace_now"),
        extra_attributes_fn=lambda data: {
            "health_score": data["filter_health_score"],
            "remaining_liters": data["filter_remaining_liters"],
            "estimated_days": data["estimated_days"],
        }
    ),
    SmartWaterBinarySensorEntityDescription(
        key="sensor_fault",
        translation_key="sensor_fault",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on_fn=lambda data: data["water_sensor_health"] in ("warning", "offline"),
        extra_attributes_fn=lambda data: {
            "time_since_last_pulse_seconds": data["time_since_last_pulse_seconds"]
        }
    ),
]

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Smart Water Filter binary sensors."""
    coordinator: SmartWaterCoordinator = hass.data[DOMAIN][entry.entry_id]
    
    entities = [
        SmartWaterBinarySensor(coordinator, description)
        for description in BINARY_SENSOR_DESCRIPTIONS
    ]
    async_add_entities(entities)

class SmartWaterBinarySensor(SmartWaterBaseEntity, BinarySensorEntity):
    """Smart Water Filter Binary Sensor."""

    entity_description: SmartWaterBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: SmartWaterCoordinator,
        description: SmartWaterBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self.entity_description.is_on_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return any extra state attributes."""
        return self.entity_description.extra_attributes_fn(self.coordinator.data)
