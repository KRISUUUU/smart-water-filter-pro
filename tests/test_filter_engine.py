"""Unit tests for FilterEngine."""
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

from datetime import datetime, timedelta
import unittest
from smart_water_filter.filter_engine import FilterEngine

class TestFilterEngine(unittest.TestCase):
    """Test suite for FilterEngine state logic."""

    def test_filter_percentage_and_remaining(self) -> None:
        """Test remaining volume and life percentage calculations."""
        engine = FilterEngine(capacity_liters=3000.0, used_liters=1200.0)
        self.assertEqual(engine.remaining_liters, 1800.0)
        self.assertEqual(engine.percentage, 60.0)

    def test_age_days(self) -> None:
        """Test filter age days tracking."""
        ten_days_ago = (datetime.now() - timedelta(days=10)).isoformat()
        engine = FilterEngine(capacity_liters=3000.0, installed_date=ten_days_ago)
        self.assertEqual(engine.age_days, 10)

    def test_flow_degradation_and_clogging(self) -> None:
        """Test flow degradation and clogging warnings."""
        engine = FilterEngine(capacity_liters=3000.0)
        
        # When new (< 100L used), establish baseline flow (e.g. 2.0 L/min)
        engine.record_usage(liters=50.0, flow_rate=2.0)
        self.assertEqual(engine.baseline_flow_rate, 2.0)
        self.assertEqual(engine.flow_degradation, 0.0)
        self.assertEqual(engine.clogging_status, "normal")

        # After 100L, record usage with a degraded flow rate (e.g. 1.2 L/min)
        engine.record_usage(liters=60.0, flow_rate=1.2)
        self.assertEqual(engine.flow_degradation, 40.0)
        self.assertEqual(engine.clogging_status, "restricted")

    def test_hybrid_health_score(self) -> None:
        """Test weighted hybrid health score calculation and overrides."""
        # 1. Normal healthy state
        engine = FilterEngine(
            capacity_liters=1000.0,
            used_liters=200.0,            # 80% volume health
            max_age_days=100.0,
            installed_date=(datetime.now() - timedelta(days=20)).isoformat(), # 80% time health
            baseline_flow_rate=2.0,
            recent_max_flow_rate=2.0      # 100% flow health (0% degradation)
        )
        self.assertEqual(engine.health_score, 88)
        self.assertEqual(engine.health_status, "excellent")

        # 2. Capped by high clogging (flow health < 30%)
        # volume: 90% -> 90 * 0.4 = 36
        # time: 90% -> 90 * 0.2 = 18
        # flow: 25% -> 25 * 0.4 = 10
        # Weighted = 64%. But flow health < 30% caps overall health at 50%.
        engine2 = FilterEngine(
            capacity_liters=1000.0,
            used_liters=100.0,
            max_age_days=100.0,
            installed_date=(datetime.now() - timedelta(days=10)).isoformat(),
            baseline_flow_rate=2.0,
            recent_max_flow_rate=0.5      # 75% degradation -> 25% flow health
        )
        self.assertEqual(engine2.health_score, 50)
        self.assertEqual(engine2.health_status, "good")

        # 3. Capped by depleted volume
        engine3 = FilterEngine(
            capacity_liters=1000.0,
            used_liters=1000.0,
            max_age_days=100.0,
            installed_date=(datetime.now() - timedelta(days=10)).isoformat(),
            baseline_flow_rate=2.0,
            recent_max_flow_rate=2.0
        )
        self.assertEqual(engine3.health_score, 10)
        self.assertEqual(engine3.health_status, "replace_soon")

    def test_reset_filter_history(self) -> None:
        """Reset should archive statistics to history log and clear states."""
        engine = FilterEngine(capacity_liters=3000.0, used_liters=2500.0)
        engine.reset_filter(new_capacity=2000.0, reason="clogged")
        
        self.assertEqual(len(engine.history), 1)
        self.assertEqual(engine.history[0]["liters_used"], 2500.0)
        self.assertEqual(engine.history[0]["reason"], "clogged")
        
        self.assertEqual(engine.capacity_liters, 2000.0)
        self.assertEqual(engine.used_liters, 0.0)
        self.assertEqual(engine.baseline_flow_rate, 0.0)
