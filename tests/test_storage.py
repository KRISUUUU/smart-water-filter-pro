"""Unit tests for storage schema migrations."""
import sys
from unittest.mock import MagicMock

# Mock Home Assistant and voluptuous before importing smart_water_filter
sys.modules['homeassistant'] = MagicMock()
sys.modules['homeassistant.config_entries'] = MagicMock()
sys.modules['homeassistant.core'] = MagicMock()
sys.modules['homeassistant.helpers'] = MagicMock()
sys.modules['homeassistant.helpers.storage'] = MagicMock()
sys.modules['homeassistant.helpers.event'] = MagicMock()
sys.modules['homeassistant.helpers.update_coordinator'] = MagicMock()
sys.modules['homeassistant.components'] = MagicMock()
sys.modules['homeassistant.components.sensor'] = MagicMock()
sys.modules['homeassistant.components.binary_sensor'] = MagicMock()
sys.modules['homeassistant.components.button'] = MagicMock()
sys.modules['homeassistant.components.number'] = MagicMock()
sys.modules['homeassistant.components.select'] = MagicMock()
sys.modules['homeassistant.const'] = MagicMock()
sys.modules['voluptuous'] = MagicMock()

import unittest
from smart_water_filter.migration import async_migrate_storage

class TestStorageMigration(unittest.IsolatedAsyncioTestCase):
    """Test suite for migration.py logic."""

    async def test_migration_v1_to_v5(self) -> None:
        """Verify v1 flat schema migrates correctly to nested v5 stages schema."""
        v1_data = {
            "total": 1250.5
        }
        
        v5_data = await async_migrate_storage(old_version=1, old_minor_version=1, data=v1_data)
        
        # Check totals
        self.assertEqual(v5_data["totals"]["lifetime_liters"], 1250.5)
        # Check defaults in v5 stages
        self.assertEqual(len(v5_data["stages"]), 1)
        self.assertEqual(v5_data["stages"][0]["id"], "main_filter")
        self.assertEqual(v5_data["stages"][0]["capacity_liters"], 3000.0)
        self.assertEqual(v5_data["stages"][0]["used_liters"], 0.0)
        self.assertEqual(v5_data["leak"]["severity"], "normal")
        self.assertEqual(v5_data["leak"]["events_total"], 0)
        self.assertEqual(v5_data["calibration"]["pulses_per_liter"], 450.0)

    async def test_migration_v2_to_v5(self) -> None:
        """Verify v2 schema migrates correctly to nested v5 stages schema."""
        v2_data = {
            "lifetime_total_liters": 1500.0,
            "filter_used_liters": 250.0,
            "filter_capacity_liters": 2000.0,
            "filter_installed_date": "2026-07-01T00:00:00",
            "filter_history": [{"date": "2026-01-01", "liters_used": 1900.0, "capacity": 2000.0, "reason": "expired"}],
            "daily_history": [{"date": "2026-07-02", "liters": 20.0}],
            "hourly_profile": {"12": 1.5},
            "leak_alarm_active": True,
            "leak_severity": "micro",
            "leak_counter": 2,
            "today_used_liters": 15.0,
            "active_time_seconds": 120.0,
            "last_date_str": "2026-07-02",
            "last_hour": 13,
            "hourly_accumulator": 0.5
        }

        v5_data = await async_migrate_storage(old_version=2, old_minor_version=1, data=v2_data)

        # Assert correct nestings
        self.assertEqual(v5_data["totals"]["lifetime_liters"], 1500.0)
        self.assertEqual(v5_data["totals"]["today_liters"], 15.0)
        self.assertEqual(v5_data["totals"]["active_time"], 120.0)
        self.assertEqual(v5_data["totals"]["last_date_str"], "2026-07-02")
        self.assertEqual(v5_data["totals"]["last_hour"], 13)
        self.assertEqual(v5_data["totals"]["hourly_accumulator"], 0.5)

        self.assertEqual(len(v5_data["stages"]), 1)
        self.assertEqual(v5_data["stages"][0]["id"], "main_filter")
        self.assertEqual(v5_data["stages"][0]["capacity_liters"], 2000.0)
        self.assertEqual(v5_data["stages"][0]["used_liters"], 250.0)
        self.assertEqual(v5_data["stages"][0]["installed_date"], "2026-07-01T00:00:00")
        self.assertEqual(len(v5_data["stages"][0]["history"]), 1)
        self.assertEqual(v5_data["stages"][0]["history"][0]["reason"], "expired")

        self.assertEqual(v5_data["leak"]["alarm_active"], True)
        self.assertEqual(v5_data["leak"]["severity"], "micro")
        self.assertEqual(v5_data["leak"]["events_total"], 2)
        
        self.assertEqual(v5_data["statistics"]["daily"][0]["liters"], 20.0)
        self.assertEqual(v5_data["statistics"]["hourly"]["12"], 1.5)

    async def test_migration_v3_to_v5(self) -> None:
        """Verify v3 nested schema migrates correctly to nested v5 stages schema."""
        v3_data = {
            "filter": {
                "capacity": 3000.0,
                "used": 120.0,
                "installed_date": "2026-07-01T00:00:00",
                "max_age_days": 365.0,
                "baseline_flow_rate": 2.0,
                "recent_max_flow_rate": 2.0,
                "history": []
            },
            "statistics": {
                "daily": [],
                "hourly": {}
            },
            "calibration": {
                "pulses_per_liter": 450.0
            },
            "events": [],
            "leak": {
                "alarm_active": False,
                "severity": "normal",
                "events_total": 0,
                "detection_mode": "standard"
            },
            "totals": {
                "lifetime_liters": 1000.0,
                "today_liters": 10.0,
                "active_time": 60.0,
                "last_date_str": "2026-07-08",
                "last_hour": 12,
                "hourly_accumulator": 0.5,
                "last_flow_time": None
            }
        }
        
        v5_data = await async_migrate_storage(old_version=3, old_minor_version=1, data=v3_data)
        
        # Verify filtered_flow_rate is added and default is 0.0
        self.assertEqual(v5_data["totals"]["filtered_flow_rate"], 0.0)
        # Verify micro/high leak start times are added and default is None
        self.assertIsNone(v5_data["leak"]["micro_start_iso"])
        self.assertIsNone(v5_data["leak"]["high_start_iso"])
        
        # Verify stage migrated
        self.assertEqual(len(v5_data["stages"]), 1)
        self.assertEqual(v5_data["stages"][0]["id"], "main_filter")
        self.assertEqual(v5_data["stages"][0]["capacity_liters"], 3000.0)

    async def test_migration_v4_to_v5(self) -> None:
        """Verify v4 nested schema migrates correctly to v5 stages schema."""
        v4_data = {
            "filter": {
                "capacity": 2500.0,
                "used": 120.0,
                "installed_date": "2026-07-01T00:00:00",
                "max_age_days": 180.0,
                "baseline_flow_rate": 2.2,
                "recent_max_flow_rate": 1.8,
                "history": [{"date": "2026-01-01", "liters_used": 1900.0, "capacity": 2000.0, "reason": "expired"}]
            },
            "leak": {
                "alarm_active": False,
                "severity": "normal"
            }
        }
        
        v5_data = await async_migrate_storage(old_version=4, old_minor_version=1, data=v4_data)
        
        # Verify "filter" is popped and "stages" is created
        self.assertNotIn("filter", v5_data)
        self.assertIn("stages", v5_data)
        self.assertEqual(len(v5_data["stages"]), 1)
        
        stage = v5_data["stages"][0]
        self.assertEqual(stage["id"], "main_filter")
        self.assertEqual(stage["name"], "Main Filter")
        self.assertEqual(stage["type"], "custom")
        self.assertEqual(stage["capacity_liters"], 2500.0)
        self.assertEqual(stage["max_age_days"], 180)
        self.assertEqual(stage["used_liters"], 120.0)
        self.assertEqual(stage["installed_date"], "2026-07-01T00:00:00")
        self.assertEqual(stage["baseline_flow_rate"], 2.2)
        self.assertEqual(stage["recent_max_flow_rate"], 1.8)
        self.assertEqual(len(stage["history"]), 1)
        self.assertEqual(stage["history"][0]["reason"], "expired")
