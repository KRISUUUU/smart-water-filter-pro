"""Binary sensor platform for Smart Water Filter."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, localize_stage_name
from .entity import SmartWaterBaseEntity
from .coordinator import SmartWaterCoordinator

@dataclass(frozen=True, kw_only=True)
class SmartWaterBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Class describing Smart Water Filter binary sensor entities."""
    is_on_fn: Callable[[dict[str, Any]], bool]
    extra_attributes_fn: Callable[[dict[str, Any]], dict[str, Any] | None] = lambda data: None

GLOBAL_BINARY_DESCRIPTIONS: list[SmartWaterBinarySensorEntityDescription] = [
    SmartWaterBinarySensorEntityDescription(
        key="water_leak_alarm",
        translation_key="water_leak_alarm",
        is_on_fn=lambda data: bool(data["leak_alarm_active"]),
        extra_attributes_fn=lambda data: {
            "severity": data["leak_severity"],
            "events_total": data["leak_events_total"],
        }
    ),
    SmartWaterBinarySensorEntityDescription(
        key="sensor_fault",
        translation_key="sensor_fault",
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda data: data["water_sensor_health"] in ("warning", "offline"),
        extra_attributes_fn=lambda data: {
            "time_since_last_pulse_seconds": data["time_since_last_pulse_seconds"]
        }
    ),
]

STAGE_BINARY_DESCRIPTION = BinarySensorEntityDescription(
    key="stage_replace_required",
    entity_category=EntityCategory.DIAGNOSTIC,
)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Smart Water Filter binary sensors."""
    coordinator: SmartWaterCoordinator = hass.data[DOMAIN][entry.entry_id]
    
    entities: list[BinarySensorEntity] = []
    
    # 1. Register global binary sensors
    for description in GLOBAL_BINARY_DESCRIPTIONS:
        entities.append(SmartWaterBinarySensor(coordinator, description))
        
    # 2. Register dynamic stage binary sensors
    for stage_id, stage_data in coordinator.data["stages"].items():
        stage_name = stage_data["name"]
        entities.append(
            SmartWaterStageBinarySensor(coordinator, stage_id, stage_name, STAGE_BINARY_DESCRIPTION)
        )
        
    async_add_entities(entities)

class SmartWaterBinarySensor(SmartWaterBaseEntity, BinarySensorEntity):
    """Smart Water Filter Global Binary Sensor."""

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

class SmartWaterStageBinarySensor(SmartWaterBaseEntity, BinarySensorEntity):
    """Smart Water Filter Stage replacement warning binary sensor."""

    def __init__(
        self,
        coordinator: SmartWaterCoordinator,
        stage_id: str,
        stage_name: str,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize the stage-specific binary sensor."""
        super().__init__(coordinator, f"{stage_id}_replace_required")
        self.entity_description = description
        self.stage_id = stage_id
        self.stage_name = stage_name
        
        # Override unique ID and translation details
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{stage_id}_replace_required"
        self._attr_translation_key = "stage_replace_required"
        self._attr_translation_placeholders = {
            "stage_name": localize_stage_name(coordinator.hass, stage_name)
        }

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on (replacement required)."""
        stage_data = self.coordinator.data["stages"].get(self.stage_id)
        if not stage_data:
            return False
        return stage_data.get("health_status") in ("replace_soon", "replace_now")

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return stage attributes."""
        stage_data = self.coordinator.data["stages"].get(self.stage_id)
        if not stage_data:
            return None
        return {
            "health_score": stage_data.get("health_score"),
            "remaining_liters": stage_data.get("remaining_liters"),
            "estimated_days": stage_data.get("estimated_days"),
            "clogging_status": stage_data.get("clogging_status"),
        }
