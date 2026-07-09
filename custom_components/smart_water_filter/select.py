"""Select platform for Smart Water Filter."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import SmartWaterBaseEntity
from .coordinator import SmartWaterCoordinator

SELECT_DESCRIPTIONS = [
    SelectEntityDescription(
        key="replacement_reason",
        translation_key="replacement_reason",
        options=["routine", "clogged", "taste", "time"],
    ),
    SelectEntityDescription(
        key="leak_detection_mode",
        translation_key="leak_detection_mode",
        options=["standard", "kitchen_ro", "away", "disabled"],
    ),
]

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Smart Water Filter selects."""
    coordinator: SmartWaterCoordinator = hass.data[DOMAIN][entry.entry_id]
    
    entities = [
        SmartWaterSelect(coordinator, description)
        for description in SELECT_DESCRIPTIONS
    ]
    async_add_entities(entities)

class SmartWaterSelect(SmartWaterBaseEntity, SelectEntity):
    """Smart Water Filter Select Input."""

    def __init__(
        self,
        coordinator: SmartWaterCoordinator,
        description: SelectEntityDescription,
    ) -> None:
        """Initialize the select."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def current_option(self) -> str | None:
        """Return the selected option."""
        if self.entity_description.key == "replacement_reason":
            return self.coordinator.current_replacement_reason
        elif self.entity_description.key == "leak_detection_mode":
            return self.coordinator.data["leak_detection_mode"]
        return None

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        if self.entity_description.key == "replacement_reason":
            await self.coordinator.async_set_replacement_reason(option)
        elif self.entity_description.key == "leak_detection_mode":
            await self.coordinator.async_set_leak_detection_mode(option)
