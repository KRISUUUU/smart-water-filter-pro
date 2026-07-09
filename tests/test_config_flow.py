"""Unit tests for the Smart Water Filter Config Flow and Options Flow."""
import sys
from unittest.mock import MagicMock, AsyncMock, patch

# Define custom mock base classes to avoid MagicMock inheritance method shadowing
class MockDataUpdateCoordinator:
    def __init__(self, hass, logger, name, update_interval=None) -> None:
        self.hass = hass
        self.logger = logger
        self.name = name
        self.update_interval = update_interval
        self.data = {}

    @classmethod
    def __class_getitem__(cls, item) -> type:
        return cls

class MockConfigFlow:
    def __init_subclass__(cls, **kwargs) -> None:
        pass

class MockOptionsFlow:
    def __init__(self, config_entry=None) -> None:
        if not hasattr(self, "config_entry") or config_entry is not None:
            self.config_entry = config_entry
        self.hass = None

    def async_create_entry(self, title, data):
        return {"type": "create_entry", "title": title, "data": data}

    def async_show_form(self, step_id, data_schema, errors=None):
        return {"type": "form", "step_id": step_id, "data_schema": data_schema, "errors": errors}

    def async_abort(self, reason):
        return {"type": "abort", "reason": reason}

# Setup package hierarchy mocks properly
mock_homeassistant = MagicMock()

mock_entries_module = MagicMock()
mock_entries_module.ConfigFlow = MockConfigFlow
mock_entries_module.OptionsFlow = MockOptionsFlow
mock_homeassistant.config_entries = mock_entries_module
sys.modules['homeassistant'] = mock_homeassistant
sys.modules['homeassistant.config_entries'] = mock_entries_module

sys.modules['homeassistant.core'] = MagicMock()

mock_helpers = MagicMock()
mock_helpers.storage = MagicMock()
mock_helpers.event = MagicMock()
mock_coord_module = MagicMock()
mock_coord_module.DataUpdateCoordinator = MockDataUpdateCoordinator
mock_coord_module.UpdateFailed = Exception
mock_helpers.update_coordinator = mock_coord_module
sys.modules['homeassistant.helpers'] = mock_helpers
sys.modules['homeassistant.helpers.storage'] = mock_helpers.storage
sys.modules['homeassistant.helpers.event'] = mock_helpers.event
sys.modules['homeassistant.helpers.update_coordinator'] = mock_coord_module

sys.modules['homeassistant.components'] = MagicMock()
sys.modules['homeassistant.components.sensor'] = MagicMock()
sys.modules['homeassistant.components.binary_sensor'] = MagicMock()
sys.modules['homeassistant.components.button'] = MagicMock()
sys.modules['homeassistant.components.number'] = MagicMock()
sys.modules['homeassistant.components.select'] = MagicMock()
sys.modules['homeassistant.const'] = MagicMock()
sys.modules['homeassistant.data_entry_flow'] = MagicMock()
sys.modules['voluptuous'] = MagicMock()

import unittest
from smart_water_filter.config_flow import SmartWaterOptionsFlow
from smart_water_filter.const import DOMAIN

class TestConfigFlow(unittest.IsolatedAsyncioTestCase):
    """Test suite for config flow and options flow logic."""

    async def test_options_flow_init(self) -> None:
        """Verify options flow init step can select an action."""
        mock_entry = MagicMock()
        mock_entry.entry_id = "test_entry_123"
        mock_entry.options = {}
        
        flow = SmartWaterOptionsFlow(mock_entry)
        flow.hass = MagicMock()
        
        # Test step_init GET form
        result = await flow.async_step_init()
        self.assertEqual(result["type"], "form")
        self.assertEqual(result["step_id"], "init")

        # Test step_init POST selection -> add_stage
        with patch.object(flow, 'async_step_add_stage', return_value={"type": "form", "step_id": "add_stage"}) as mock_add:
            result = await flow.async_step_init(user_input={"action": "add_stage"})
            mock_add.assert_called_once()
            self.assertEqual(result["step_id"], "add_stage")

    async def test_options_flow_add_preset_stage(self) -> None:
        """Verify options flow preset addition calls coordinator and returns success."""
        mock_entry = MagicMock()
        mock_entry.entry_id = "test_entry_123"
        mock_entry.options = {}
        
        flow = SmartWaterOptionsFlow(mock_entry)
        flow.hass = MagicMock()
        
        mock_coordinator = MagicMock()
        mock_coordinator.async_add_filter_stage = AsyncMock()
        flow.hass.data = {DOMAIN: {"test_entry_123": mock_coordinator}}
        
        # Test post Carbon preset
        result = await flow.async_step_add_stage(user_input={
            "preset_type": "carbon",
            "name": "Custom Carbon"
        })
        
        # Check coordinator called with preset defaults
        mock_coordinator.async_add_filter_stage.assert_called_once_with(
            name="Custom Carbon",
            stage_type="carbon",
            capacity_liters=4000.0,
            max_age_days=365.0
        )
        self.assertEqual(result["type"], "create_entry")
