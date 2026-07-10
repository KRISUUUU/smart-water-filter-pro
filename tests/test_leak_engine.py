"""Unit tests for LeakEngine."""
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
from smart_water_filter.leak_engine import LeakEngine

class TestLeakEngine(unittest.TestCase):
    """Test suite for LeakEngine logic and modes."""

    def setUp(self) -> None:
        """Set up test environment."""
        self.start_time = datetime(2026, 7, 8, 12, 0, 0)

    def test_standard_leak_severity(self) -> None:
        """Test Standard mode leak severity thresholds and times."""
        engine = LeakEngine(detection_mode="standard")
        
        # Flow = 0.06 L/min (Standard Micro threshold > 0.05 L/min)
        res1 = engine.analyze(0.06, self.start_time)
        self.assertFalse(res1["alarm_active"])

        # After 31 minutes -> triggers MICRO alarm
        res2 = engine.analyze(0.06, self.start_time + timedelta(minutes=31))
        self.assertTrue(res2["alarm_active"])
        self.assertEqual(res2["severity"], "micro")
        self.assertEqual(res2["leak_events_total"], 1)

    def test_high_leak_alarm(self) -> None:
        """Test High leak threshold (1.0 L/min for 10 minutes)."""
        engine = LeakEngine(detection_mode="standard")
        
        engine.analyze(1.5, self.start_time)
        res = engine.analyze(1.5, self.start_time + timedelta(minutes=11))
        self.assertTrue(res["alarm_active"])
        self.assertEqual(res["severity"], "high")

    def test_critical_leak_alarm(self) -> None:
        """Test Critical leak threshold (5.0 L/min instantly)."""
        engine = LeakEngine(detection_mode="standard")
        
        res = engine.analyze(5.1, self.start_time)
        self.assertTrue(res["alarm_active"])
        self.assertEqual(res["severity"], "critical")

    def test_away_mode_aggressive_detection(self) -> None:
        """Test Away mode aggressive thresholds (0.01 L/min for 2 min)."""
        engine = LeakEngine(detection_mode="away")
        
        engine.analyze(0.02, self.start_time)
        res = engine.analyze(0.02, self.start_time + timedelta(minutes=3))
        self.assertTrue(res["alarm_active"])
        self.assertEqual(res["severity"], "micro")

    def test_kitchen_ro_mode_slow_flush(self) -> None:
        """Test Kitchen/RO mode ignores low flows for up to 120 minutes."""
        engine = LeakEngine(detection_mode="kitchen_ro")
        
        # Flow = 0.03 L/min (Kitchen/RO Micro limit is 0.02 L/min for 120m)
        engine.analyze(0.03, self.start_time)
        
        # 60 minutes later -> still normal
        res1 = engine.analyze(0.03, self.start_time + timedelta(minutes=60))
        self.assertFalse(res1["alarm_active"])

        # 125 minutes later -> triggers MICRO alarm
        res2 = engine.analyze(0.03, self.start_time + timedelta(minutes=125))
        self.assertTrue(res2["alarm_active"])

    def test_persistent_start_timestamps(self) -> None:
        """Ensure leak start times restore and survive restarts."""
        # 1. Start a leak run
        engine = LeakEngine(detection_mode="standard")
        engine.analyze(0.06, self.start_time)
        
        micro_start_val = engine.micro_leak_start.isoformat()
        
        # 2. Simulate HA restart by reloading LeakEngine using stored timestamp
        restored_engine = LeakEngine(
            detection_mode="standard",
            micro_start_iso=micro_start_val
        )
        
        # 3. Analyze at t + 31 minutes -> Alarm should trigger immediately
        res = restored_engine.analyze(0.06, self.start_time + timedelta(minutes=31))
        self.assertTrue(res["alarm_active"])
        self.assertEqual(res["severity"], "micro")

    def test_immediate_drop_to_zero_clears_timers(self) -> None:
        """Verify that dropping to zero flow immediately clears pending timers."""
        engine = LeakEngine(detection_mode="standard")
        
        # Start a micro leak timer
        engine.analyze(0.06, self.start_time)
        self.assertIsNotNone(engine.micro_leak_start)
        
        # Drop to 0.0 flow -> should clear timers
        engine.analyze(0.0, self.start_time + timedelta(minutes=5))
        self.assertIsNone(engine.micro_leak_start)
        self.assertIsNone(engine.high_leak_start)
