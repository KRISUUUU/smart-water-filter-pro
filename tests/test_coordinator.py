"""Unit tests for the Smart Water Filter Coordinator."""
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
from datetime import datetime
from smart_water_filter.coordinator import SmartWaterCoordinator

class TestCoordinatorIntegration(unittest.IsolatedAsyncioTestCase):
    """Test suite for Coordinator lifecycle and operations."""

    async def test_coordinator_lifecycle(self) -> None:
        # 1. Create mocks for HA and config entry
        mock_hass = MagicMock()
        mock_hass.states.get.return_value = None
        
        mock_entry = MagicMock()
        mock_entry.entry_id = "test_entry_123"
        mock_entry.title = "Water Filter"
        mock_entry.data = {
            "name": "Smart Water Filter",
            "source_sensor": "sensor.water_pulses",
            "source_type": "pulses",
            "pulses_per_liter": 450.0,
        }
        mock_entry.options = {}

        # 2. Instantiate coordinator
        coordinator = SmartWaterCoordinator(mock_hass, mock_entry)

        # Mock underlying storage store load/save
        storage_data = {
            "stages": [
                {
                    "id": "main_filter",
                    "name": "Main Filter",
                    "type": "custom",
                    "capacity_liters": 3000.0,
                    "used_liters": 0.0,
                    "installed_date": "2026-07-01T00:00:00",
                    "baseline_flow_rate": 0.0,
                    "recent_max_flow_rate": 0.0,
                    "history": []
                }
            ]
        }
        async def mock_load():
            return storage_data
        async def mock_save(data):
            nonlocal storage_data
            storage_data = data
            return None

        coordinator.storage.store.async_load = AsyncMock(side_effect=mock_load)
        coordinator.storage.store.async_save = AsyncMock(side_effect=mock_save)

        # 3. Setup coordinator
        await coordinator.async_setup()
        coordinator.last_date_str = "2026-07-08"

        # Check default loaded states
        self.assertEqual(coordinator.lifetime_total_liters, 0.0)
        self.assertEqual(coordinator.today_used_liters, 0.0)
        self.assertEqual(coordinator.current_flow_rate, 0.0)
        self.assertEqual(coordinator.pulses_per_liter, 450.0)
        self.assertIn("main_filter", coordinator.filter_engine.stages)

        # 4. Inject pulses
        # Create a mock state representing 100 pulses at t0
        state0 = MagicMock()
        state0.state = "100"
        
        t0_time = datetime(2026, 7, 8, 12, 0, 0)
        with patch('smart_water_filter.coordinator.datetime') as mock_dt:
            mock_dt.now.return_value = t0_time
            coordinator._process_source_state(state0)
            
        self.assertEqual(coordinator.lifetime_total_liters, 0.0) # Delta is 0 on t0
        self.assertEqual(coordinator.flow_engine.last_pulse_count, 100.0)

        # Inject 550 pulses at t1 (delta 450 pulses = 1.0 Liters)
        state1 = MagicMock()
        state1.state = "550"
        
        now_time = datetime(2026, 7, 8, 12, 0, 10) # 10 seconds later
        
        with patch('smart_water_filter.coordinator.datetime') as mock_dt:
            # mock datetime.now() inside coordinator
            mock_dt.now.return_value = now_time
            coordinator._process_source_state(state1)

        # Verify volume and flow calculations
        self.assertEqual(coordinator.lifetime_total_liters, 1.0)
        self.assertEqual(coordinator.today_used_liters, 1.0)
        self.assertGreater(coordinator.current_flow_rate, 0.0)
        self.assertEqual(coordinator.filter_engine.stages["main_filter"].used_liters, 1.0)

        # 5. Save state
        await coordinator.async_save_state()
        
        # Verify saved data structure has stages and totals
        self.assertIn("totals", storage_data)
        self.assertEqual(storage_data["totals"]["lifetime_liters"], 1.0)
        self.assertEqual(storage_data["totals"]["today_liters"], 1.0)
        self.assertGreater(storage_data["totals"]["filtered_flow_rate"], 0.0)
        self.assertIn("stages", storage_data)
        self.assertEqual(storage_data["stages"][0]["used_liters"], 1.0)

        # 6. Reload from storage
        new_coordinator = SmartWaterCoordinator(mock_hass, mock_entry)
        new_coordinator.storage.store.async_load = AsyncMock(side_effect=mock_load)
        
        await new_coordinator.async_setup()

        # 7. Verify totals and stages restored
        self.assertEqual(new_coordinator.lifetime_total_liters, 1.0)
        self.assertEqual(new_coordinator.today_used_liters, 1.0)
        self.assertGreater(new_coordinator.current_flow_rate, 0.0)
        self.assertEqual(new_coordinator.filter_engine.stages["main_filter"].used_liters, 1.0)

    async def test_coordinator_liters_mode(self) -> None:
        """Test coordinator behavior when configured with SOURCE_TYPE_LITERS."""
        # 1. Create mocks for HA and config entry
        mock_hass = MagicMock()
        mock_hass.states.get.return_value = None
        
        mock_entry = MagicMock()
        mock_entry.entry_id = "test_entry_456"
        mock_entry.title = "Water Filter Liters"
        mock_entry.data = {
            "name": "Smart Water Filter",
            "source_sensor": "sensor.water_flow_rate",
            "source_type": "liters",
            "pulses_per_liter": 1.0,
        }
        mock_entry.options = {}

        # 2. Instantiate coordinator
        coordinator = SmartWaterCoordinator(mock_hass, mock_entry)

        # Mock underlying storage store load/save
        storage_data = {
            "stages": [
                {
                    "id": "main_filter",
                    "name": "Main Filter",
                    "type": "custom",
                    "capacity_liters": 3000.0,
                    "used_liters": 0.0,
                    "installed_date": "2026-07-01T00:00:00",
                    "baseline_flow_rate": 0.0,
                    "recent_max_flow_rate": 0.0,
                    "history": []
                }
            ]
        }
        async def mock_load():
            return storage_data
        async def mock_save(data):
            nonlocal storage_data
            storage_data = data
            return None

        coordinator.storage.store.async_load = AsyncMock(side_effect=mock_load)
        coordinator.storage.store.async_save = AsyncMock(side_effect=mock_save)

        # 3. Setup coordinator
        await coordinator.async_setup()
        coordinator.last_date_str = "2026-07-08"

        # Check default loaded states
        self.assertEqual(coordinator.lifetime_total_liters, 0.0)
        self.assertEqual(coordinator.current_flow_rate, 0.0)
        self.assertEqual(coordinator.source_type, "liters")

        # 4. Inject positive flow rate (e.g., 1.5 L/min) at t0
        state0 = MagicMock()
        state0.state = "1.5"
        
        t0_time = datetime(2026, 7, 8, 12, 0, 0)
        with patch('smart_water_filter.coordinator.datetime') as mock_dt:
            mock_dt.now.return_value = t0_time
            coordinator._process_source_state(state0)
            
        # At t0, dt is 0 since last_time was None (it sets last_time to t0)
        self.assertEqual(coordinator.lifetime_total_liters, 0.0)
        self.assertEqual(coordinator.current_flow_rate, 1.5)
        self.assertEqual(coordinator.flow_engine.current_flow_rate, 1.5)

        # 5. Inject flow rate of 1.5 L/min at t1 (10 seconds later)
        # Volume consumed: 1.5 L/min * (10s / 60s) = 0.25 Liters
        state1 = MagicMock()
        state1.state = "1.5"
        
        t1_time = datetime(2026, 7, 8, 12, 0, 10)
        with patch('smart_water_filter.coordinator.datetime') as mock_dt:
            mock_dt.now.return_value = t1_time
            coordinator._process_source_state(state1)

        self.assertEqual(coordinator.lifetime_total_liters, 0.25)
        self.assertEqual(coordinator.current_flow_rate, 1.5)
        self.assertEqual(coordinator.flow_engine.current_flow_rate, 1.5)

        # 6. Inject flow rate of 0.0 L/min (drops to zero)
        # It should immediately set current_flow_rate to 0.0, bypassing EMA
        state2 = MagicMock()
        state2.state = "0.0"
        
        t2_time = datetime(2026, 7, 8, 12, 0, 20)
        with patch('smart_water_filter.coordinator.datetime') as mock_dt:
            mock_dt.now.return_value = t2_time
            coordinator._process_source_state(state2)

        self.assertEqual(coordinator.current_flow_rate, 0.0)
        self.assertEqual(coordinator.flow_engine.current_flow_rate, 0.0)
        # Lifetime total liters should not increase since flow rate was 0.0 during this step
        self.assertEqual(coordinator.lifetime_total_liters, 0.25)
