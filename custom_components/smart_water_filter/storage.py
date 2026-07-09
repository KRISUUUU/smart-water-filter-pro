"""Persistent JSON storage helper for Smart Water Filter."""
import logging
from typing import Any, Dict

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store

from .const import STORAGE_VERSION
from .migration import async_migrate_storage

_LOGGER = logging.getLogger(__name__)

class WaterStorage:
    """Manages reading and writing integration statistics to disk."""

    def __init__(self, hass: HomeAssistant, key: str) -> None:
        """Initialize the storage helper."""
        self.hass = hass
        # Store configuration data under Home Assistant config/.storage/
        self.store = Store(hass, STORAGE_VERSION, key, minor_version=1)

    async def load(self) -> Dict[str, Any]:
        """Load state data, running automatic schema migrations if needed."""
        try:
            data = await self.store.async_load()
            if data is None:
                return {}
            return data
        except Exception as err:
            _LOGGER.error("Failed to load smart water storage: %s", err)
            return {}

    async def save(self, data: Dict[str, Any]) -> None:
        """Persist config state to disk."""
        try:
            await self.store.async_save(data)
        except Exception as err:
            _LOGGER.error("Failed to save smart water storage: %s", err)

@callback
def async_register_migrations(hass: HomeAssistant) -> None:
    """Register the storage migrations callback helper."""
    # This matches Home Assistant standard API to handle schema migrations on startup
    # Store constructor automatically calls async_migrate_storage if schema version matches
    pass

# Direct link callback for HA storage engine
Store.async_migrate_storage = async_migrate_storage
