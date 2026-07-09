"""Unit tests for FlowEngine."""
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
from smart_water_filter.flow_engine import FlowEngine

class TestFlowEngine(unittest.TestCase):
    """Test suite for FlowEngine calculations and edge cases."""

    def setUp(self) -> None:
        """Set up test environment."""
        self.engine = FlowEngine(pulses_per_liter=450.0, alpha=0.2)
        self.start_time = datetime(2026, 7, 8, 12, 0, 0)

    def test_initial_reading(self) -> None:
        """First reading should return zero consumption and flow."""
        liters, flow = self.engine.update_pulses(100.0, self.start_time)
        self.assertEqual(liters, 0.0)
        self.assertEqual(flow, 0.0)

    def test_normal_pulses_calculation_with_ema(self) -> None:
        """Test delta volume and flow rate conversion under normal flow with EMA."""
        # Initial t0
        self.engine.update_pulses(100.0, self.start_time)
        
        # 450 pulses = 1 Liter. Time delta = 10s.
        # Raw Flow rate = (1L / 10s) * 60 = 6.0 L/min.
        # EMA Flow rate = 0.2 * 6.0 + 0.8 * 0.0 = 1.2 L/min.
        t1 = self.start_time + timedelta(seconds=10)
        liters, flow = self.engine.update_pulses(550.0, t1)
        
        self.assertEqual(liters, 1.0)
        self.assertAlmostEqual(flow, 1.2, places=2)

    def test_pulse_counter_reset(self) -> None:
        """If ESP reboots, pulse count jumps back to 0. Test reset handling."""
        self.engine.update_pulses(1000.0, self.start_time)
        
        # Reset: pulse count goes to 10 pulses after reboot.
        # Delta pulses should be assumed to be 10 pulses (delta_liters = 10 / 450).
        t1 = self.start_time + timedelta(seconds=5)
        liters, flow = self.engine.update_pulses(10.0, t1)
        
        self.assertAlmostEqual(liters, 10.0 / 450.0, places=5)
        self.assertGreater(flow, 0.0)

    def test_direct_liters_mode(self) -> None:
        """Test FlowEngine direct liters calculations."""
        # Initial
        self.engine.update_liters(10.0, self.start_time)
        
        # Add 5 Liters over 60 seconds -> Raw flow = 5 L/min.
        # EMA Flow = 0.2 * 5.0 + 0.8 * 0.0 = 1.0 L/min.
        t1 = self.start_time + timedelta(minutes=1)
        liters, flow = self.engine.update_liters(15.0, t1)
        
        self.assertEqual(liters, 5.0)
        self.assertAlmostEqual(flow, 1.0, places=2)

    def test_direct_liters_reset(self) -> None:
        """Test that direct liters counter resets are handled safely."""
        self.engine.update_liters(100.0, self.start_time)
        
        # Reset: value resets to 5.0
        t1 = self.start_time + timedelta(seconds=10)
        liters, flow = self.engine.update_liters(5.0, t1)
        
        self.assertEqual(liters, 5.0)
        self.assertGreater(flow, 0.0)

    def test_division_by_zero_protection(self) -> None:
        """Test that flow engine is protected against division by zero."""
        self.engine.pulses_per_liter = 0.0
        liters, flow = self.engine.update_pulses(500.0, self.start_time)
        self.assertEqual(liters, 0.0)
        self.assertEqual(flow, 0.0)
