"""Base entity class for Smart Water Filter."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SmartWaterCoordinator

class SmartWaterBaseEntity(CoordinatorEntity[SmartWaterCoordinator]):
    """Base class for Smart Water Filter entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SmartWaterCoordinator, key: str) -> None:
        """Initialize the base entity."""
        super().__init__(coordinator)
        self.entity_description_key = key
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key}"
        self._attr_translation_key = key
        
        # Bind all entities under a unified device registry card
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.entry_id)},
            name="Smart Water Filter PRO",
            manufacturer="KRISUUUU",
            model="PRO Hardware Tier",
            sw_version="4.3.1",
        )
