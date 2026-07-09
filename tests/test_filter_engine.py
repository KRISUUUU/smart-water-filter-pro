"""Unit tests for FilterStage and FilterEngine."""
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
from smart_water_filter.filter_engine import FilterStage, FilterEngine

class TestFilterStageAndEngine(unittest.TestCase):
    """Test suite for FilterStage and FilterEngine state logic."""

    def test_stage_percentage_and_remaining(self) -> None:
        """Test remaining volume and life percentage calculations for a stage."""
        stage = FilterStage(stage_id="carbon_stage", name="Carbon Stage", capacity_liters=3000.0, used_liters=1200.0)
        self.assertEqual(stage.remaining_liters, 1800.0)
        self.assertEqual(stage.percentage, 60.0)

    def test_age_days(self) -> None:
        """Test filter stage age days tracking."""
        ten_days_ago = (datetime.now() - timedelta(days=10)).isoformat()
        stage = FilterStage(stage_id="carbon_stage", name="Carbon Stage", capacity_liters=3000.0, installed_date=ten_days_ago)
        self.assertEqual(stage.age_days, 10)

    def test_flow_degradation_and_clogging(self) -> None:
        """Test flow degradation and clogging warnings on a stage."""
        stage = FilterStage(stage_id="sediment_stage", name="Sediment Stage", capacity_liters=3000.0)
        
        # When new (< 100L used), establish baseline flow (e.g. 2.0 L/min)
        stage.record_usage(liters=50.0, flow_rate=2.0)
        self.assertEqual(stage.baseline_flow_rate, 2.0)
        self.assertEqual(stage.flow_degradation, 0.0)
        self.assertEqual(stage.clogging_status, "normal")

        # After 100L, record usage with a degraded flow rate (e.g. 1.2 L/min)
        stage.record_usage(liters=60.0, flow_rate=1.2)
        self.assertEqual(stage.flow_degradation, 40.0)
        self.assertEqual(stage.clogging_status, "restricted")

    def test_hybrid_health_score(self) -> None:
        """Test weighted hybrid health score calculation and overrides."""
        # 1. Normal healthy state
        stage = FilterStage(
            stage_id="sediment_stage",
            name="Sediment Stage",
            capacity_liters=1000.0,
            used_liters=200.0,            # 80% volume health
            max_age_days=100.0,
            installed_date=(datetime.now() - timedelta(days=20)).isoformat(), # 80% time health
            baseline_flow_rate=2.0,
            recent_max_flow_rate=2.0      # 100% flow health (0% degradation)
        )
        self.assertEqual(stage.health_score, 88)
        self.assertEqual(stage.health_status, "excellent")

        # 2. Capped by high clogging (flow health < 30%)
        stage2 = FilterStage(
            stage_id="sediment_stage",
            name="Sediment Stage",
            capacity_liters=1000.0,
            used_liters=100.0,
            max_age_days=100.0,
            installed_date=(datetime.now() - timedelta(days=10)).isoformat(),
            baseline_flow_rate=2.0,
            recent_max_flow_rate=0.5      # 75% degradation -> 25% flow health
        )
        self.assertEqual(stage2.health_score, 50)
        self.assertEqual(stage2.health_status, "good")

        # 3. Capped by depleted volume
        stage3 = FilterStage(
            stage_id="sediment_stage",
            name="Sediment Stage",
            capacity_liters=1000.0,
            used_liters=1000.0,
            max_age_days=100.0,
            installed_date=(datetime.now() - timedelta(days=10)).isoformat(),
            baseline_flow_rate=2.0,
            recent_max_flow_rate=2.0
        )
        self.assertEqual(stage3.health_score, 10)
        self.assertEqual(stage3.health_status, "replace_soon")

    def test_reset_filter_history(self) -> None:
        """Reset should archive statistics to history log and clear states."""
        stage = FilterStage(stage_id="sediment_stage", name="Sediment Stage", capacity_liters=3000.0, used_liters=2500.0)
        stage.reset_filter(new_capacity=2000.0, reason="clogged")
        
        self.assertEqual(len(stage.history), 1)
        self.assertEqual(stage.history[0]["liters_used"], 2500.0)
        self.assertEqual(stage.history[0]["reason"], "clogged")
        
        self.assertEqual(stage.capacity_liters, 2000.0)
        self.assertEqual(stage.used_liters, 0.0)
        self.assertEqual(stage.baseline_flow_rate, 0.0)

    def test_engine_orchestration(self) -> None:
        """Test FilterEngine adds, removes, and records usage across stages."""
        engine = FilterEngine([
            {
                "id": "stage_1",
                "name": "Stage 1",
                "type": "sediment",
                "capacity_liters": 2000.0,
                "used_liters": 500.0,
            }
        ])
        
        self.assertIn("stage_1", engine.stages)
        self.assertEqual(engine.stages["stage_1"].name, "Stage 1")
        self.assertEqual(engine.stages["stage_1"].used_liters, 500.0)
        
        # Add a stage
        engine.add_stage(name="Stage 2", stage_type="carbon", capacity_liters=4000.0)
        self.assertIn("stage_2", engine.stages)
        self.assertEqual(engine.stages["stage_2"].capacity_liters, 4000.0)
        
        # Record usage
        engine.record_usage(liters=100.0, flow_rate=2.5)
        self.assertEqual(engine.stages["stage_1"].used_liters, 600.0)
        self.assertEqual(engine.stages["stage_2"].used_liters, 100.0)
        
        # Remove stage
        engine.remove_stage("stage_1")
        self.assertNotIn("stage_1", engine.stages)
