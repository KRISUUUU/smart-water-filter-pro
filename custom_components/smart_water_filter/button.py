"""Button platform for Smart Water Filter."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import SmartWaterBaseEntity
from .coordinator import SmartWaterCoordinator

GLOBAL_BUTTON_DESCRIPTIONS = [
    ButtonEntityDescription(
        key="clear_alarm",
        translation_key="clear_alarm",
    ),
    ButtonEntityDescription(
        key="smart_water_filter_export_backup",
        translation_key="smart_water_filter_export_backup",
    ),
]

STAGE_BUTTON_DESCRIPTION = ButtonEntityDescription(
    key="stage_reset",
)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Smart Water Filter buttons."""
    coordinator: SmartWaterCoordinator = hass.data[DOMAIN][entry.entry_id]
    
    entities: list[ButtonEntity] = []
    
    # 1. Register global buttons
    for description in GLOBAL_BUTTON_DESCRIPTIONS:
        entities.append(SmartWaterButton(coordinator, description))
        
    # 2. Register dynamic stage buttons
    for stage_id, stage_data in coordinator.data["stages"].items():
        stage_name = stage_data["name"]
        entities.append(
            SmartWaterStageButton(coordinator, stage_id, stage_name, STAGE_BUTTON_DESCRIPTION)
        )
        
    async_add_entities(entities)

class SmartWaterButton(SmartWaterBaseEntity, ButtonEntity):
    """Smart Water Filter Global Button."""

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
        if self.entity_description_key == "clear_alarm":
            await self.coordinator.async_clear_alarm()
        elif self.entity_description_key == "smart_water_filter_export_backup":
            await self.coordinator.async_export_backup_file()

class SmartWaterStageButton(SmartWaterBaseEntity, ButtonEntity):
    """Smart Water Filter Stage-Specific Reset Button."""

    def __init__(
        self,
        coordinator: SmartWaterCoordinator,
        stage_id: str,
        stage_name: str,
        description: ButtonEntityDescription,
    ) -> None:
        """Initialize the stage-specific button."""
        super().__init__(coordinator, f"reset_{stage_id}")
        self.entity_description = description
        self.stage_id = stage_id
        self.stage_name = stage_name
        
        # Override unique ID and translation config
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{stage_id}_reset"
        self._attr_translation_key = "stage_reset"
        self._attr_translation_placeholders = {"stage_name": stage_name}
        self._attr_entity_category = EntityCategory.CONFIG

    async def async_press(self) -> None:
        """Press the button to reset this specific filter stage."""
        reason = self.coordinator.current_replacement_reason
        await self.coordinator.async_reset_filter(stage_id=self.stage_id, reason=reason)
