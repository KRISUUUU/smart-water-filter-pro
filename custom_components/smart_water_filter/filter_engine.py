"""Filter engine to manage filter stages, capacity, lifetime tracking, and clogging."""
from datetime import datetime
import re
from typing import Dict, Any, List, Optional

def slugify(text: str) -> str:
    """Simplify a string into a slug."""
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s-]+", "_", text)
    return text.strip("_")

class FilterStage:
    """Tracks a single water filter stage's health, usage volume, age, and flow rate degradation."""

    def __init__(
        self,
        stage_id: str,
        name: str,
        stage_type: str = "custom",
        capacity_liters: float = 3000.0,
        used_liters: float = 0.0,
        installed_date: Optional[str] = None,
        max_age_days: float = 365.0,
        baseline_flow_rate: float = 0.0,
        recent_max_flow_rate: float = 0.0,
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        self.id = slugify(stage_id)
        self.name = name
        self.type = stage_type  # carbon, capillary, sediment, custom
        self.capacity_liters = float(capacity_liters)
        self.used_liters = float(used_liters)
        self.installed_date = installed_date or datetime.now().isoformat()
        self.max_age_days = float(max_age_days)
        self.baseline_flow_rate = float(baseline_flow_rate)
        self.recent_max_flow_rate = float(recent_max_flow_rate)
        self.history = history or []

    @property
    def remaining_liters(self) -> float:
        """Return remaining filter capacity in liters."""
        return max(0.0, self.capacity_liters - self.used_liters)

    @property
    def percentage(self) -> float:
        """Return remaining filter capacity percentage (0-100%)."""
        if self.capacity_liters <= 0.0:
            return 0.0
        return max(0.0, round((self.remaining_liters / self.capacity_liters) * 100.0, 1))

    @property
    def age_days(self) -> int:
        """Return number of days since the filter was installed."""
        try:
            installed = datetime.fromisoformat(self.installed_date)
            delta = datetime.now() - installed
            return max(0, delta.days)
        except (ValueError, TypeError):
            return 0

    @property
    def flow_degradation(self) -> float:
        """Return percentage drop in flow rate (0-100%)."""
        if self.baseline_flow_rate <= 0.5 or self.recent_max_flow_rate <= 0.0:
            return 0.0
        
        # If recent max is greater than baseline, no degradation
        if self.recent_max_flow_rate >= self.baseline_flow_rate:
            return 0.0
            
        drop = (self.baseline_flow_rate - self.recent_max_flow_rate) / self.baseline_flow_rate
        return round(drop * 100.0, 1)

    @property
    def clogging_status(self) -> str:
        """Return clogging status: normal, warning, restricted."""
        degr = self.flow_degradation
        if degr > 35.0:
            return "restricted"
        elif degr > 20.0:
            return "warning"
        return "normal"

    @property
    def health_score(self) -> int:
        """Calculate overall health score (0-100%) considering volume, time, and flow."""
        # 1. Volume health (0-100)
        vol_health = self.percentage
        
        # 2. Time health (max lifetime days)
        time_health = max(0.0, (self.max_age_days - self.age_days) / self.max_age_days * 100.0)
        
        # 3. Flow health (degradation subtracts from 100)
        flow_health = max(0.0, 100.0 - self.flow_degradation)

        # Hybrid weighted score: 40% volume, 20% age, 40% flow
        health = (vol_health * 0.4) + (time_health * 0.2) + (flow_health * 0.4)

        # Critical Overrides
        if flow_health < 30.0:
            health = min(health, 50.0)
        if vol_health == 0.0 or time_health == 0.0:
            health = min(health, 10.0)

        return int(round(health))

    @property
    def health_status(self) -> str:
        """Return health status descriptor."""
        score = self.health_score
        if score >= 80:
            return "excellent"
        elif score >= 50:
            return "good"
        elif score >= 20:
            return "fair"
        elif score > 0:
            return "replace_soon"
        else:
            return "replace_now"

    def record_usage(self, liters: float, flow_rate: float) -> None:
        """Record water usage and update flow rate baselines."""
        self.used_liters += liters
        
        # Capture baseline peak flow rate during the first 100L of usage
        if self.used_liters < 100.0:
            if flow_rate > self.baseline_flow_rate:
                self.baseline_flow_rate = flow_rate
        else:
            # Beyond 100L, capture recent flow rate peaks
            if flow_rate > self.recent_max_flow_rate:
                self.recent_max_flow_rate = flow_rate
            elif self.recent_max_flow_rate == 0.0:
                self.recent_max_flow_rate = flow_rate

    def reset_filter(self, new_capacity: float, reason: str = "manual") -> None:
        """Reset usage counters, save historical run, and initialize new cartridge."""
        history_entry = {
            "date": datetime.now().isoformat(),
            "liters_used": round(self.used_liters, 2),
            "capacity": self.capacity_liters,
            "age_days": self.age_days,
            "reason": reason,
        }
        self.history.append(history_entry)

        # Keep history capped at last 50 replacements
        if len(self.history) > 50:
            self.history = self.history[-50:]

        self.capacity_liters = float(new_capacity)
        self.used_liters = 0.0
        self.installed_date = datetime.now().isoformat()
        self.baseline_flow_rate = 0.0
        self.recent_max_flow_rate = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert stage state to dict for storage."""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "capacity_liters": self.capacity_liters,
            "used_liters": self.used_liters,
            "installed_date": self.installed_date,
            "max_age_days": self.max_age_days,
            "baseline_flow_rate": self.baseline_flow_rate,
            "recent_max_flow_rate": self.recent_max_flow_rate,
            "history": self.history,
        }


class FilterEngine:
    """Manages an array of FilterStage instances."""

    def __init__(self, stages_data: Optional[List[Dict[str, Any]]] = None) -> None:
        self.stages: Dict[str, FilterStage] = {}
        
        stages_data = stages_data or []
        for s in stages_data:
            stage_id = s.get("id") or slugify(s.get("name", "Filter Stage"))
            self.stages[stage_id] = FilterStage(
                stage_id=stage_id,
                name=s.get("name", "Filter Stage"),
                stage_type=s.get("type", "custom"),
                capacity_liters=s.get("capacity_liters", 3000.0),
                used_liters=s.get("used_liters", 0.0),
                installed_date=s.get("installed_date"),
                max_age_days=s.get("max_age_days", 365.0),
                baseline_flow_rate=s.get("baseline_flow_rate", 0.0),
                recent_max_flow_rate=s.get("recent_max_flow_rate", 0.0),
                history=s.get("history"),
            )

    def record_usage(self, liters: float, flow_rate: float) -> None:
        """Record water usage across all registered filter stages."""
        for stage in self.stages.values():
            stage.record_usage(liters, flow_rate)

    def add_stage(
        self,
        name: str,
        stage_type: str,
        capacity_liters: float = 3000.0,
        max_age_days: float = 365.0,
    ) -> FilterStage:
        """Add a new stage dynamically."""
        stage_id = slugify(name)
        if stage_id in self.stages:
            # Handle duplicate naming conflicts by appending integer suffix
            counter = 1
            while f"{stage_id}_{counter}" in self.stages:
                counter += 1
            stage_id = f"{stage_id}_{counter}"

        stage = FilterStage(
            stage_id=stage_id,
            name=name,
            stage_type=stage_type,
            capacity_liters=capacity_liters,
            max_age_days=max_age_days,
        )
        self.stages[stage.id] = stage
        return stage

    def remove_stage(self, stage_id: str) -> Optional[FilterStage]:
        """Remove a stage by ID."""
        return self.stages.pop(stage_id, None)

    def to_list(self) -> List[Dict[str, Any]]:
        """Return list representation of all stages for serialization."""
        return [stage.to_dict() for stage in self.stages.values()]
