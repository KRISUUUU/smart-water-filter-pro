"""Filter engine to manage filter capacity, lifetime tracking, and clogging."""
from datetime import datetime
from typing import Dict, Any, List, Optional

class FilterEngine:
    """Tracks water filter health, usage volume, age, and flow rate degradation."""

    def __init__(
        self,
        capacity_liters: float,
        used_liters: float = 0.0,
        installed_date: Optional[str] = None,
        max_age_days: float = 365.0,
        baseline_flow_rate: float = 0.0,
        recent_max_flow_rate: float = 0.0,
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
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
        """Convert engine state to dict for storage."""
        return {
            "capacity": self.capacity_liters,
            "used": self.used_liters,
            "installed_date": self.installed_date,
            "max_age_days": self.max_age_days,
            "baseline_flow_rate": self.baseline_flow_rate,
            "recent_max_flow_rate": self.recent_max_flow_rate,
            "history": self.history,
        }
