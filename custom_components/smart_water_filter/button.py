"""Button platform for Smart Water Filter."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import SmartWaterBaseEntity
from .coordinator import SmartWaterCoordinator

BUTTON_DESCRIPTIONS = [
    ButtonEntityDescription(
        key="reset_filter",
        translation_key="reset_filter",
    ),
    ButtonEntityDescription(
        key="clear_alarm",
        translation_key="clear_alarm",
    ),
    ButtonEntityDescription(
        key="smart_water_filter_export_backup",
        translation_key="smart_water_filter_export_backup",
    ),
]

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Smart Water Filter buttons."""
    coordinator: SmartWaterCoordinator = hass.data[DOMAIN][entry.entry_id]
    
    entities = [
        SmartWaterButton(coordinator, description)
        for description in BUTTON_DESCRIPTIONS
    ]
    async_add_entities(entities)

class SmartWaterButton(SmartWaterBaseEntity, ButtonEntity):
    """Smart Water Filter Button."""

    def __init__(
        self,
        coordinator: SmartWaterCoordinator,
        description: ButtonEntityDescription,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    async def async_press(self) -> None:
        """Press the button."""
        if self.entity_description_key == "reset_filter":
            reason = self.coordinator.current_replacement_reason
            await self.coordinator.async_reset_filter(reason=reason)
        elif self.entity_description_key == "clear_alarm":
            await self.coordinator.async_clear_alarm()
        elif self.entity_description_key == "smart_water_filter_export_backup":
            await self.coordinator.async_export_backup_file()
