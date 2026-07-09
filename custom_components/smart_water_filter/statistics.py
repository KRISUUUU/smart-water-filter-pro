"""Statistics engine to analyze daily usage trends and hourly profiles."""
from typing import Dict, Any, List, Optional

class StatisticsEngine:
    """Computes daily averages, EMAs, hourly profiles, and trend directions."""

    def __init__(
        self,
        daily_history: Optional[List[Dict[str, Any]]] = None,
        hourly_profile: Optional[Dict[str, float]] = None,
    ) -> None:
        self.daily_history = daily_history or []
        # Profiles stored as string hour -> float liters (e.g. "12": 15.5)
        self.hourly_profile = hourly_profile or {str(h): 0.0 for h in range(24)}

    @property
    def sma_7(self) -> float:
        """Return 7-day Simple Moving Average of water consumption."""
        if not self.daily_history:
            return 0.0
        last_7 = self.daily_history[-7:]
        total = sum(float(day["liters"]) for day in last_7)
        return round(total / len(last_7), 2)

    @property
    def ema_7(self) -> float:
        """Return 7-day Exponential Moving Average of water consumption."""
        if not self.daily_history:
            return 0.0
        
        # Smooth factor alpha = 2 / (N + 1) -> for 7 days, alpha = 0.25
        alpha = 0.25
        ema = float(self.daily_history[0]["liters"])
        
        for day in self.daily_history[1:]:
            val = float(day["liters"])
            ema = (alpha * val) + ((1.0 - alpha) * ema)
            
        return round(ema, 2)

    @property
    def usage_trend(self) -> str:
        """Evaluate and return trend direction: stable, increasing, decreasing."""
        # Need at least 3 days to determine a trend
        if len(self.daily_history) < 3:
            return "stable"

        sma = self.sma_7
        ema = self.ema_7

        if sma <= 0.5:
            return "stable"

        diff_pct = (ema - sma) / sma
        if diff_pct > 0.10:
            return "increasing"
        elif diff_pct < -0.10:
            return "decreasing"
        return "stable"

    def record_daily_usage(self, date_str: str, liters: float) -> None:
        """Record the total water consumed on a specific date."""
        # Prevent duplicate entries for the same date
        self.daily_history = [d for d in self.daily_history if d["date"] != date_str]
        
        self.daily_history.append({
            "date": date_str,
            "liters": round(float(liters), 2)
        })

        # Capped to 30 days of daily history
        if len(self.daily_history) > 30:
            self.daily_history = self.daily_history[-30:]

    def record_hourly_usage(self, hour: int, liters: float) -> None:
        """Merge new hourly usage using a rolling EMA (alpha = 0.15)."""
        hour_str = str(hour)
        liters = float(liters)
        current = float(self.hourly_profile.get(hour_str, 0.0))
        
        # EMA alpha = 0.15
        alpha = 0.15
        new_val = (alpha * liters) + ((1.0 - alpha) * current)
        self.hourly_profile[hour_str] = round(new_val, 3)

    def to_dict(self) -> Dict[str, Any]:
        """Convert statistics state to dict for storage."""
        return {
            "daily": self.daily_history,
            "hourly": self.hourly_profile,
        }
