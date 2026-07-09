"""Coordinator for Smart Water Filter integration."""
from __future__ import annotations

from datetime import datetime, timedelta
import json
import logging
import os
from typing import Any, Dict, List, Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
try:
    from homeassistant.util.text import slugify
except ImportError:
    import re
    def slugify(text: str) -> str:
        """Fallback slugify for test environment."""
        text = text.lower()
        text = re.sub(r"[^\w\s-]", "", text)
        text = re.sub(r"[\s-]+", "_", text)
        return text.strip("_")

from .const import (
    DOMAIN,
    CONF_SOURCE_SENSOR,
    CONF_SOURCE_TYPE,
    CONF_PULSES_PER_LITER,
    SOURCE_TYPE_PULSES,
    FLOW_MIN_THRESHOLD,
    DEFAULT_CAPACITY,
    DEFAULT_PULSES_PER_LITER,
    EMA_ALPHA,
)
from .flow_engine import FlowEngine
from .filter_engine import FilterEngine, FilterStage
from .statistics import StatisticsEngine
from .predictor import FilterPredictor
from .leak_engine import LeakEngine
from .calibration import CalibrationEngine
from .event_log import EventLogger
from .storage import WaterStorage

_LOGGER = logging.getLogger(__name__)

class SmartWaterCoordinator(DataUpdateCoordinator[Dict[str, Any]]):
    """Central coordinator to manage water filter data updates."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=15),
        )
        self.entry = entry
        
        # Setup config attributes
        self.source_sensor = entry.options.get(CONF_SOURCE_SENSOR, entry.data.get(CONF_SOURCE_SENSOR))
        self.source_type = entry.options.get(CONF_SOURCE_TYPE, entry.data.get(CONF_SOURCE_TYPE, SOURCE_TYPE_PULSES))
        
        # Storage
        self.storage = WaterStorage(hass, f"{DOMAIN}_{entry.entry_id}")

        # Core states
        self.lifetime_total_liters = 0.0
        self.today_used_liters = 0.0
        self.active_time_seconds = 0.0
        self.last_date_str: Optional[str] = None
        self.last_hour: Optional[int] = None
        self.hourly_accumulator = 0.0
        self.last_flow_time: Optional[datetime] = None
        self.current_flow_rate = 0.0
        self.last_pulse_received_time: Optional[datetime] = None
        self.current_replacement_reason = "routine"
        self._unsub_state = None

    async def async_setup(self) -> None:
        """Load persistent states and initialize engines."""
        stored = await self.storage.load()

        # Load totals and configuration metadata
        totals = stored.get("totals", {})
        self.lifetime_total_liters = float(totals.get("lifetime_liters", 0.0))
        self.today_used_liters = float(totals.get("today_liters", 0.0))
        self.active_time_seconds = float(totals.get("active_time", 0.0))
        self.last_date_str = totals.get("last_date_str") or datetime.now().strftime("%Y-%m-%d")
        self.last_hour = totals.get("last_hour") if totals.get("last_hour") is not None else datetime.now().hour
        self.hourly_accumulator = float(totals.get("hourly_accumulator", 0.0))
        self.current_flow_rate = float(totals.get("filtered_flow_rate", 0.0))
        
        last_flow_iso = totals.get("last_flow_time")
        self.last_flow_time = datetime.fromisoformat(last_flow_iso) if last_flow_iso else None

        # Load calibration factor
        cal = stored.get("calibration", {})
        self.pulses_per_liter = float(cal.get(
            "pulses_per_liter",
            self.entry.options.get(CONF_PULSES_PER_LITER, self.entry.data.get(CONF_PULSES_PER_LITER, DEFAULT_PULSES_PER_LITER))
        ))

        # Instantiate engines
        stages_data = stored.get("stages", [])
        self.filter_engine = FilterEngine(stages_data)

        stats_data = stored.get("statistics", {})
        self.statistics_engine = StatisticsEngine(
            daily_history=stats_data.get("daily"),
            hourly_profile=stats_data.get("hourly"),
        )

        leak_data = stored.get("leak", {})
        self.leak_engine = LeakEngine(
            alarm_active=leak_data.get("alarm_active", False),
            severity=leak_data.get("severity", "normal"),
            leak_events_total=leak_data.get("events_total", 0),
            detection_mode=leak_data.get("detection_mode", "standard"),
            micro_start_iso=leak_data.get("micro_start_iso"),
            high_start_iso=leak_data.get("high_start_iso"),
        )

        self.calibration_engine = CalibrationEngine(
            active=stored.get("calibration", {}).get("calibration_active", False),
            accumulated_pulses=stored.get("calibration", {}).get("calibration_accumulated_pulses", 0.0),
        )

        self.event_logger = EventLogger(stored.get("events"))
        self.flow_engine = FlowEngine(
            pulses_per_liter=self.pulses_per_liter,
            alpha=EMA_ALPHA,
            current_flow_rate=self.current_flow_rate
        )

        # Track source sensor changes in real-time
        if self.source_sensor:
            self._unsub_state = async_track_state_change_event(
                self.hass, [self.source_sensor], self._async_handle_source_sensor_event
            )
            # Fetch initial state
            init_state = self.hass.states.get(self.source_sensor)
            if init_state:
                self._process_source_state(init_state)

        # Populate coordinator's default data
        self.data = self._build_coordinator_data()

    async def _async_update_data(self) -> Dict[str, Any]:
        """Periodic update loop (runs every 15 seconds)."""
        now = datetime.now()

        # Timeout check: If water stopped flowing, reset flow rate to 0
        if self.last_pulse_received_time:
            idle_duration = (now - self.last_pulse_received_time).total_seconds()
            if idle_duration > 15.0 and self.current_flow_rate > 0.0:
                self.current_flow_rate = 0.0
                self.flow_engine.current_flow_rate = 0.0
                self.leak_engine.analyze(0.0, now)
                await self.async_save_state()

        # Run overnight/no-flow date and hour rollovers
        self._check_rollovers(now)

        return self._build_coordinator_data()

    @callback
    def _async_handle_source_sensor_event(self, event: Any) -> None:
        """Handle real-time state change updates of the source sensor."""
        new_state = event.data.get("new_state")
        if new_state is None or new_state.state in ("unknown", "unavailable"):
            return

        self._process_source_state(new_state)
        
        # Instantly update coordinator data and push to HA entities
        self.async_set_updated_data(self._build_coordinator_data())

    def _process_source_state(self, state: Any) -> None:
        """Extract sensor state values, execute delta math, and feed engines."""
        try:
            val = float(state.state)
        except ValueError:
            return

        now = datetime.now()
        dt = 0.0
        if self.flow_engine.last_time:
            dt = (now - self.flow_engine.last_time).total_seconds()

        # Run delta engine calculations
        if self.source_type == SOURCE_TYPE_PULSES:
            last_pulses = self.flow_engine.last_pulse_count
            delta_liters, flow_rate = self.flow_engine.update_pulses(val, now)
            
            # If calibration is active, calculate raw pulses added
            if self.calibration_engine.active and last_pulses is not None:
                delta_pulses = val - last_pulses if val >= last_pulses else val
                self.calibration_engine.add_pulses(delta_pulses)
        else:
            delta_liters, flow_rate = self.flow_engine.update_liters(val, now)

        # Accumulate metrics if we got new volume
        if delta_liters > 0.0:
            self.lifetime_total_liters += delta_liters
            self.today_used_liters += delta_liters
            self.hourly_accumulator += delta_liters
            self.last_flow_time = now
            self.last_pulse_received_time = now
            self.current_flow_rate = flow_rate

            if flow_rate > FLOW_MIN_THRESHOLD and dt > 0.0:
                self.active_time_seconds += dt

            # Record usage in all filter stages
            self.filter_engine.record_usage(delta_liters, flow_rate)

        # Update leak engine
        self.leak_engine.analyze(self.current_flow_rate, now)

        # Check date/hour rollovers
        self._check_rollovers(now)

    def _check_rollovers(self, now: datetime) -> None:
        """Check and handle midnight and hourly statistics rollovers."""
        current_date = now.strftime("%Y-%m-%d")
        current_hour = now.hour

        # Date Rollover (resets daily usage at midnight)
        if self.last_date_str and current_date != self.last_date_str:
            self.statistics_engine.record_daily_usage(self.last_date_str, self.today_used_liters)
            self.event_logger.log_event(
                "daily_summary",
                f"Daily water usage summary for {self.last_date_str}: {round(self.today_used_liters, 2)} L",
                {"date": self.last_date_str, "liters": self.today_used_liters}
            )
            self.today_used_liters = 0.0
            self.last_date_str = current_date
            self.hass.async_create_task(self.async_save_state())

        # Hourly Rollover (tracks profiles)
        if self.last_hour is not None and current_hour != self.last_hour:
            self.statistics_engine.record_hourly_usage(self.last_hour, self.hourly_accumulator)
            self.hourly_accumulator = 0.0
            self.last_hour = current_hour
            self.hass.async_create_task(self.async_save_state())

    def _build_coordinator_data(self) -> Dict[str, Any]:
        """Synthesize metrics from all internal engines for HA entities."""
        # Diagnose sensor health
        sensor_health_state = "good"
        time_since_pulse = 0.0
        if self.last_pulse_received_time:
            time_since_pulse = (datetime.now() - self.last_pulse_received_time).total_seconds()
            if time_since_pulse > 86400.0:
                sensor_health_state = "warning"
        
        source_state = self.hass.states.get(self.source_sensor) if self.source_sensor else None
        if source_state and source_state.state in ("unknown", "unavailable"):
            sensor_health_state = "offline"

        daily_ema = self.statistics_engine.ema_7

        stages_dict = {}
        for stage in self.filter_engine.stages.values():
            predictor = FilterPredictor(stage.capacity_liters, stage.used_liters)
            remaining_days = predictor.predict_remaining_days(
                daily_usage_ema=daily_ema,
                age_days=stage.age_days,
                max_age_days=stage.max_age_days
            )
            confidence = predictor.calculate_confidence(self.statistics_engine.daily_history)
            stages_dict[stage.id] = {
                "id": stage.id,
                "name": stage.name,
                "type": stage.type,
                "capacity_liters": stage.capacity_liters,
                "used_liters": round(stage.used_liters, 2),
                "remaining_liters": round(stage.remaining_liters, 2),
                "percentage": round(stage.percentage, 1),
                "max_age_days": stage.max_age_days,
                "age_days": stage.age_days,
                "installed_date": stage.installed_date,
                "flow_degradation": stage.flow_degradation,
                "clogging_status": stage.clogging_status,
                "health_score": stage.health_score,
                "health_status": stage.health_status,
                "history": stage.history,
                "estimated_days": remaining_days,
                "confidence": confidence,
            }

        return {
            "lifetime_total_liters": round(self.lifetime_total_liters, 2),
            "today_used_liters": round(self.today_used_liters, 2),
            "current_flow_rate": round(self.current_flow_rate, 3),
            "average_flow_rate": round(
                (self.lifetime_total_liters / (self.active_time_seconds / 60.0))
                if self.active_time_seconds > 0 else 0.0,
                2
            ),
            "active_time_minutes": round(self.active_time_seconds / 60.0, 1),
            "last_flow_time": self.last_flow_time.isoformat() if self.last_flow_time else None,
            
            # Stages mapping
            "stages": stages_dict,
            
            # Statistics
            "daily_history": self.statistics_engine.daily_history,
            "hourly_profile": self.statistics_engine.hourly_profile,
            "sma_7": self.statistics_engine.sma_7,
            "ema_7": self.statistics_engine.ema_7,
            "usage_trend": self.statistics_engine.usage_trend,
            
            # Leak engine
            "leak_alarm_active": self.leak_engine.alarm_active,
            "leak_severity": self.leak_engine.severity,
            "leak_events_total": self.leak_engine.leak_events_total,
            "leak_detection_mode": self.leak_engine.detection_mode,
            
            # Calibration state
            "calibration_active": self.calibration_engine.active,
            "calibration_accumulated_pulses": self.calibration_engine.accumulated_pulses,
            "pulses_per_liter": self.pulses_per_liter,

            # Health check diagnostics
            "water_sensor_health": sensor_health_state,
            "time_since_last_pulse_seconds": round(time_since_pulse, 1),
            
            # Event logging
            "events": self.event_logger.to_list(),
        }

    async def async_save_state(self) -> None:
        """Write current engine configuration and histories to persistent storage."""
        data = {
            "stages": self.filter_engine.to_list(),
            "statistics": self.statistics_engine.to_dict(),
            "calibration": {
                "pulses_per_liter": self.pulses_per_liter,
                "calibration_active": self.calibration_engine.active,
                "calibration_accumulated_pulses": self.calibration_engine.accumulated_pulses,
            },
            "events": self.event_logger.to_list(),
            "leak": self.leak_engine.to_dict(),
            "totals": {
                "lifetime_liters": self.lifetime_total_liters,
                "today_liters": self.today_used_liters,
                "active_time": self.active_time_seconds,
                "last_date_str": self.last_date_str,
                "last_hour": self.last_hour,
                "hourly_accumulator": self.hourly_accumulator,
                "last_flow_time": self.last_flow_time.isoformat() if self.last_flow_time else None,
                "filtered_flow_rate": self.current_flow_rate,
            }
        }
        await self.storage.save(data)

    # Programmatic service actions
    async def async_add_filter_stage(
        self,
        name: str,
        stage_type: str,
        capacity_liters: float = 3000.0,
        max_age_days: float = 365.0,
    ) -> None:
        """Inject a new stage dynamically and reload integration to configure entities."""
        stage = self.filter_engine.add_stage(
            name=name,
            stage_type=stage_type,
            capacity_liters=capacity_liters,
            max_age_days=max_age_days,
        )
        self.event_logger.log_event(
            "stage_added",
            f"Added filter stage: {name} (type: {stage_type}, capacity: {capacity_liters} L)",
            {"stage_id": stage.id, "name": name, "type": stage_type}
        )
        await self.async_save_state()
        await self.async_request_refresh()
        await self.hass.config_entries.async_reload(self.entry.entry_id)

    async def async_remove_stage_entities(self, stage_id: str) -> None:
        """Remove all entities associated with a specific stage_id from the registry."""
        try:
            from homeassistant.helpers import entity_registry as er
            from homeassistant.helpers import device_registry as dr

            ent_reg = er.async_get(self.hass)
            dev_reg = dr.async_get(self.hass)

            # Find and remove entities
            unique_id_prefix = f"{self.entry.entry_id}_{stage_id}_"
            entities_to_remove = [
                entry.entity_id
                for entry in er.async_entries_for_config_entry(ent_reg, self.entry.entry_id)
                if entry.unique_id.startswith(unique_id_prefix)
            ]
            for entity_id in entities_to_remove:
                try:
                    ent_reg.async_remove(entity_id)
                    _LOGGER.info("Removed orphaned entity from registry: %s", entity_id)
                except KeyError:
                    pass
        except Exception as err:
            _LOGGER.error("Error during stage entities cleanup: %s", err)

    async def async_remove_filter_stage(self, stage_id: str) -> None:
        """Remove a stage dynamically and reload integration."""
        removed = self.filter_engine.remove_stage(stage_id)
        if removed:
            self.event_logger.log_event(
                "stage_removed",
                f"Removed filter stage: {removed.name} ({stage_id})",
                {"stage_id": stage_id, "name": removed.name}
            )
            await self.async_save_state()
            await self.async_remove_stage_entities(stage_id)
            await self.async_request_refresh()
            await self.hass.config_entries.async_reload(self.entry.entry_id)

    async def async_reset_filter(self, stage_id: str, new_capacity: float = None, reason: str = "manual") -> None:
        """Reset the water filter usage counters for a specific stage and log details."""
        if stage_id not in self.filter_engine.stages:
            _LOGGER.error("Cannot reset filter stage: stage %s not found", stage_id)
            return

        stage = self.filter_engine.stages[stage_id]
        cap = new_capacity if new_capacity is not None else stage.capacity_liters
        stage.reset_filter(cap, reason)
        self.event_logger.log_event(
            "filter_reset",
            f"Filter stage '{stage.name}' ({stage_id}) reset. Capacity: {cap} L, Reason: {reason}",
            {"stage_id": stage_id, "capacity": cap, "reason": reason}
        )
        await self.async_save_state()
        await self.async_request_refresh()

    async def async_clear_alarm(self) -> None:
        """Manually dismiss the latched leak alarm."""
        self.leak_engine.clear_alarm()
        self.event_logger.log_event(
            "alarm_cleared",
            "Water leak alarm has been cleared manually"
        )
        await self.async_save_state()
        await self.async_request_refresh()

    async def async_set_filter_capacity(self, stage_id: str, capacity: float) -> None:
        """Set the target capacity for a specific stage."""
        if stage_id in self.filter_engine.stages:
            self.filter_engine.stages[stage_id].capacity_liters = float(capacity)
            await self.async_save_state()
            await self.async_request_refresh()

    async def async_set_filter_max_age(self, stage_id: str, max_age_days: float) -> None:
        """Set the maximum age limit for a specific stage."""
        if stage_id in self.filter_engine.stages:
            self.filter_engine.stages[stage_id].max_age_days = float(max_age_days)
            await self.async_save_state()
            await self.async_request_refresh()

    async def async_set_replacement_reason(self, reason: str) -> None:
        """Update the selected replacement reason state."""
        self.current_replacement_reason = reason
        await self.async_request_refresh()

    async def async_set_leak_detection_mode(self, mode: str) -> None:
        """Change the sensitivity profile of the leak engine."""
        self.leak_engine.detection_mode = mode
        self.event_logger.log_event(
            "leak_mode_changed",
            f"Leak detection mode changed to: {mode}",
            {"mode": mode}
        )
        await self.async_save_state()
        await self.async_request_refresh()

    async def async_start_calibration(self) -> None:
        """Begin flow sensor pulse calibration run."""
        self.calibration_engine.start()
        self.event_logger.log_event(
            "calibration_start",
            "Interactive calibration run started. Run water now."
        )
        await self.async_save_state()
        await self.async_request_refresh()

    async def async_finish_calibration(self, actual_volume: float) -> float:
        """Complete calibration, update factor, and persist changes."""
        old_factor = self.pulses_per_liter
        new_factor = self.calibration_engine.finish(actual_volume)
        if new_factor > 0.0:
            self.pulses_per_liter = new_factor
            self.flow_engine.pulses_per_liter = new_factor
            
            # Persist dynamically to config entry options
            new_options = {**self.entry.options, CONF_PULSES_PER_LITER: new_factor}
            self.hass.config_entries.async_update_entry(self.entry, options=new_options)

            self.event_logger.log_event(
                "calibration_finish",
                f"Calibration completed. Old: {old_factor}/L, New: {new_factor}/L",
                {"old_factor": old_factor, "new_factor": new_factor, "volume": actual_volume}
            )
        else:
            self.event_logger.log_event(
                "calibration_failed",
                "Calibration run finished but failed to compute a new factor (zero pulses or invalid volume)."
            )

        await self.async_save_state()
        await self.async_request_refresh()
        return new_factor

    async def async_export_backup_file(self) -> str:
        """Export pretty-printed storage JSON copy to config folder with date stamping."""
        date_str = datetime.now().strftime("%Y-%m-%d")
        base_filename = f"smart_water_filter_backup_{date_str}.json"
        filepath = self.hass.config.path(base_filename)
        
        # Handle naming conflicts: append counter suffix
        if os.path.exists(filepath):
            counter = 1
            while True:
                filename = f"smart_water_filter_backup_{date_str}_{counter}.json"
                filepath = self.hass.config.path(filename)
                if not os.path.exists(filepath):
                    break
                counter += 1

        export_data = {
            "stages": self.filter_engine.to_list(),
            "statistics": self.statistics_engine.to_dict(),
            "calibration": {
                "pulses_per_liter": self.pulses_per_liter,
                "calibration_active": self.calibration_engine.active,
                "calibration_accumulated_pulses": self.calibration_engine.accumulated_pulses,
            },
            "events": self.event_logger.to_list(),
            "leak": self.leak_engine.to_dict(),
            "totals": {
                "lifetime_liters": self.lifetime_total_liters,
                "today_liters": self.today_used_liters,
                "active_time": self.active_time_seconds,
                "last_date_str": self.last_date_str,
                "last_hour": self.last_hour,
                "hourly_accumulator": self.hourly_accumulator,
                "last_flow_time": self.last_flow_time.isoformat() if self.last_flow_time else None,
                "filtered_flow_rate": self.current_flow_rate,
            }
        }

        # Write Pretty JSON backup supporting UTF-8 Polish characters
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=4, ensure_ascii=False)
            
            self.event_logger.log_event(
                "backup_exported",
                f"Pretty JSON Backup exported to: {os.path.basename(filepath)}"
            )
            await self.async_save_state()
            await self.async_request_refresh()
            return filepath
        except Exception as err:
            _LOGGER.error("Failed to write smart water filter backup: %s", err)
            raise
