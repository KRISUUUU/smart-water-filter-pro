"""Predictive engine to calculate estimated days left and confidence."""
import math
from typing import List, Dict, Any

class FilterPredictor:
    """Predicts filter exhaustion date based on usage trends and time limits."""

    def __init__(self, capacity_liters: float, used_liters: float) -> None:
        self.capacity_liters = float(capacity_liters)
        self.used_liters = float(used_liters)

    @property
    def remaining_liters(self) -> float:
        """Return remaining filter liters."""
        return max(0.0, self.capacity_liters - self.used_liters)

    def predict_remaining_days(
        self,
        daily_usage_ema: float,
        age_days: int,
        max_age_days: float
    ) -> int:
        """Forecast remaining days based on volume usage and maximum cartridge age."""
        max_age_days = float(max_age_days)
        age_days = int(age_days)
        
        # 1. Calculate time limits
        days_by_age = int(max(0.0, max_age_days - age_days))
        
        # 2. Calculate volume limits
        if daily_usage_ema <= 0.5:  # Handle near-zero usage
            return days_by_age
            
        days_by_volume = int(math.ceil(self.remaining_liters / daily_usage_ema))
        
        # Predicted remaining days is the minimum of age limit and volume limit
        return min(days_by_volume, days_by_age)

    def calculate_confidence(self, daily_history: List[Dict[str, Any]]) -> int:
        """Compute estimated confidence rating (0-100%) based on history length and stability."""
        if not daily_history:
            return 0

        n = len(daily_history)
        
        # 1. Base score by sample size: 5% per day, capped at 85% for 17+ days
        sample_score = min(85, n * 5)
        
        if n < 3:
            return sample_score

        # 2. Stability score: Standard deviation adjustment
        liters_list = [float(day["liters"]) for day in daily_history]
        mean = sum(liters_list) / n
        
        if mean <= 1.0:
            return sample_score  # Low usage has stable prediction bounds

        # Compute standard deviation
        variance = sum((x - mean) ** 2 for x in liters_list) / n
        std_dev = math.sqrt(variance)
        
        # Coefficient of variation (CV) = std_dev / mean
        cv = std_dev / mean

        # Penalty: high CV means highly volatile usage pattern
        # If CV = 0, penalty is 0. If CV >= 1.0, penalty is 30%
        penalty = min(30.0, cv * 30.0)

        # 3. Final confidence calculation
        final_score = sample_score - penalty
        
        # If we have 14+ days of history, grant a +15% stability bonus if CV < 0.20
        if n >= 14 and cv < 0.20:
            final_score += 15.0

        return int(max(0.0, min(100.0, round(final_score))))
