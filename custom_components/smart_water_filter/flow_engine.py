"""Flow engine to calculate water volume and flow rate from sensor states."""
from datetime import datetime
from typing import Optional, Tuple

class FlowEngine:
    """Calculates water consumption and real-time flow rate from pulse/volume changes."""

    def __init__(self, pulses_per_liter: float, alpha: float = 0.2, current_flow_rate: float = 0.0) -> None:
        self.pulses_per_liter = float(pulses_per_liter)
        self.alpha = float(alpha)
        self.last_pulse_count: Optional[float] = None
        self.last_volume_liters: Optional[float] = None
        self.last_time: Optional[datetime] = None
        self.current_flow_rate = float(current_flow_rate)

    def update_pulses(self, pulse_count: float, now: datetime) -> Tuple[float, float]:
        """Process new pulse counter reading.
        
        Returns tuple of (delta_liters, flow_rate_l_min).
        """
        pulse_count = float(pulse_count)
        if self.pulses_per_liter <= 0.0:
            return 0.0, 0.0

        if self.last_pulse_count is None or self.last_time is None:
            self.last_pulse_count = pulse_count
            self.last_time = now
            return 0.0, self.current_flow_rate

        # Handle sensor reset/wrap-around
        if pulse_count < self.last_pulse_count:
            delta_pulses = pulse_count
        else:
            delta_pulses = pulse_count - self.last_pulse_count

        delta_liters = delta_pulses / self.pulses_per_liter
        dt = (now - self.last_time).total_seconds()

        if dt > 0.05:  # Prevent division by near-zero time differences
            raw_flow_rate = (delta_liters / dt) * 60.0
            self.current_flow_rate = (self.alpha * raw_flow_rate) + ((1.0 - self.alpha) * self.current_flow_rate)

        self.last_pulse_count = pulse_count
        self.last_time = now

        return delta_liters, self.current_flow_rate

    def update_liters(self, volume_liters: float, now: datetime) -> Tuple[float, float]:
        """Process new direct liters volume reading.
        
        Returns tuple of (delta_liters, flow_rate_l_min).
        """
        volume_liters = float(volume_liters)
        if self.last_volume_liters is None or self.last_time is None:
            self.last_volume_liters = volume_liters
            self.last_time = now
            return 0.0, self.current_flow_rate

        # Handle sensor reset/wrap-around
        if volume_liters < self.last_volume_liters:
            delta_liters = volume_liters
        else:
            delta_liters = volume_liters - self.last_volume_liters

        dt = (now - self.last_time).total_seconds()

        if dt > 0.05:
            raw_flow_rate = (delta_liters / dt) * 60.0
            self.current_flow_rate = (self.alpha * raw_flow_rate) + ((1.0 - self.alpha) * self.current_flow_rate)

        self.last_volume_liters = volume_liters
        self.last_time = now

        return delta_liters, self.current_flow_rate
