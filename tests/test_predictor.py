"""Unit tests for FilterPredictor."""
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
from smart_water_filter.predictor import FilterPredictor

class TestFilterPredictor(unittest.TestCase):
    """Test suite for FilterPredictor logic."""

    def test_predict_remaining_days(self) -> None:
        """Verify remaining days are predicted correctly and capped by age limits."""
        # 1. Bounded by volume usage
        predictor = FilterPredictor(capacity_liters=1000.0, used_liters=200.0)
        days = predictor.predict_remaining_days(daily_usage_ema=10.0, age_days=50, max_age_days=365.0)
        self.assertEqual(days, 80)

        # 2. Bounded by age limits
        days_capped = predictor.predict_remaining_days(daily_usage_ema=2.0, age_days=90, max_age_days=100.0)
        self.assertEqual(days_capped, 10)

    def test_calculate_confidence_length(self) -> None:
        """Verify confidence grows with more history entries."""
        predictor = FilterPredictor(capacity_liters=3000.0, used_liters=0.0)
        
        # 1. No history
        self.assertEqual(predictor.calculate_confidence([]), 0)

        # 2. 1 day history
        conf_1 = predictor.calculate_confidence([{"date": "2026-07-01", "liters": 150.0}])
        self.assertGreater(conf_1, 0)
        self.assertLessEqual(conf_1, 10)

        # 3. 14 days stable history
        stable_history = [{"date": f"2026-07-{d}", "liters": 150.0} for d in range(1, 15)]
        conf_14 = predictor.calculate_confidence(stable_history)
        self.assertGreater(conf_14, 80)
        self.assertEqual(conf_14, 85)

    def test_calculate_confidence_stability(self) -> None:
        """Verify high variance reduces confidence score."""
        predictor = FilterPredictor(capacity_liters=3000.0, used_liters=0.0)
        
        # Stable usage: 10 days of exactly 100L
        stable = [{"date": f"2026-07-{d}", "liters": 100.0} for d in range(1, 11)]
        conf_stable = predictor.calculate_confidence(stable)

        # Volatile usage: alternates between 10L and 190L (mean 100L, high variance)
        volatile = []
        for d in range(1, 11):
            liters = 10.0 if d % 2 == 0 else 190.0
            volatile.append({"date": f"2026-07-{d}", "liters": liters})
            
        conf_volatile = predictor.calculate_confidence(volatile)
        self.assertLess(conf_volatile, conf_stable)
