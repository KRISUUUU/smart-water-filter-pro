"""Unit tests for StatisticsEngine."""
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
from smart_water_filter.statistics import StatisticsEngine

class TestStatisticsEngine(unittest.TestCase):
    """Test suite for StatisticsEngine math."""

    def test_sma_calculation(self) -> None:
        """Verify SMA7 matches expected average of last 7 daily entries."""
        engine = StatisticsEngine()
        
        # Feed 10 days of usage
        for i in range(1, 11):
            engine.record_daily_usage(f"2026-07-0{i}" if i < 10 else "2026-07-10", float(i * 10))
            
        # Last 7 days: [40, 50, 60, 70, 80, 90, 100] -> SMA = 70.0.
        self.assertAlmostEqual(engine.sma_7, 70.0, places=2)

    def test_ema_calculation(self) -> None:
        """Verify EMA7 calculations."""
        engine = StatisticsEngine()
        
        engine.record_daily_usage("2026-07-01", 10.0)
        engine.record_daily_usage("2026-07-02", 20.0)
        engine.record_daily_usage("2026-07-03", 30.0)
        
        self.assertAlmostEqual(engine.ema_7, 16.88, places=2)

    def test_usage_trends(self) -> None:
        """Verify usage trend evaluations."""
        # 1. Increasing trend
        engine1 = StatisticsEngine()
        engine1.record_daily_usage("2026-07-01", 10.0)
        engine1.record_daily_usage("2026-07-02", 10.0)
        engine1.record_daily_usage("2026-07-03", 10.0)
        engine1.record_daily_usage("2026-07-04", 40.0)
        engine1.record_daily_usage("2026-07-05", 80.0)
        self.assertEqual(engine1.usage_trend, "increasing")

        # 2. Decreasing trend
        engine2 = StatisticsEngine()
        for d in range(1, 8):
            engine2.record_daily_usage(f"2026-07-0{d}", 10.0)
        engine2.record_daily_usage("2026-07-08", 1.0)
        self.assertEqual(engine2.usage_trend, "decreasing")

        # 3. Stable trend
        engine3 = StatisticsEngine()
        engine3.record_daily_usage("2026-07-01", 20.0)
        engine3.record_daily_usage("2026-07-02", 20.0)
        engine3.record_daily_usage("2026-07-03", 20.0)
        self.assertEqual(engine3.usage_trend, "stable")

    def test_hourly_profile_ema(self) -> None:
        """Verify hourly profile EMA increments."""
        engine = StatisticsEngine()
        
        engine.record_hourly_usage(14, 10.0)
        self.assertAlmostEqual(engine.hourly_profile["14"], 1.5, places=2)
        
        engine.record_hourly_usage(14, 20.0)
        self.assertAlmostEqual(engine.hourly_profile["14"], 4.275, places=2)
