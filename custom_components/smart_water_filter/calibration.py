"""Calibration engine to calculate pulses_per_liter factors dynamically."""

class CalibrationEngine:
    """Manages active interactive sensor calibration runs."""

    def __init__(self, active: bool = False, accumulated_pulses: float = 0.0) -> None:
        self.active = bool(active)
        self.accumulated_pulses = float(accumulated_pulses)

    def start(self) -> None:
        """Start the calibration run."""
        self.active = True
        self.accumulated_pulses = 0.0

    def add_pulses(self, pulses: float) -> None:
        """Add pulses to calibration counter if active."""
        if self.active:
            self.accumulated_pulses += float(pulses)

    def finish(self, actual_volume_liters: float) -> float:
        """Complete the calibration run and calculate the new factor.
        
        Returns the new pulses_per_liter value, or 0.0 if failed.
        """
        self.active = False
        actual_volume_liters = float(actual_volume_liters)
        
        if actual_volume_liters <= 0.05 or self.accumulated_pulses <= 5.0:
            self.accumulated_pulses = 0.0
            return 0.0
            
        new_factor = self.accumulated_pulses / actual_volume_liters
        self.accumulated_pulses = 0.0
        return round(new_factor, 2)
