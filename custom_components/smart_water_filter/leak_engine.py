"""Leak detection engine based on flow rate, duration, and sensitivity modes."""
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

class LeakEngine:
    """Analyzes flow rate over time to detect potential water leaks."""

    def __init__(
        self,
        alarm_active: bool = False,
        severity: str = "normal",
        leak_events_total: int = 0,
        detection_mode: str = "standard",
        micro_start_iso: Optional[str] = None,
        high_start_iso: Optional[str] = None,
    ) -> None:
        self.alarm_active = alarm_active
        self.severity = severity  # "normal", "micro", "high", "critical"
        self.leak_events_total = int(leak_events_total)
        self.detection_mode = detection_mode  # "standard", "kitchen_ro", "away", "disabled"

        # Parse stored timestamps or set None
        try:
            self.micro_leak_start = datetime.fromisoformat(micro_start_iso) if micro_start_iso else None
        except (ValueError, TypeError):
            self.micro_leak_start = None

        try:
            self.high_leak_start = datetime.fromisoformat(high_start_iso) if high_start_iso else None
        except (ValueError, TypeError):
            self.high_leak_start = None

    def analyze(self, flow_rate: float, now: Optional[datetime] = None) -> Dict[str, Any]:
        """Analyze flow rate and return leak status based on detection mode."""
        if now is None:
            now = datetime.now()

        flow_rate = float(flow_rate)

        if flow_rate == 0.0:
            self.micro_leak_start = None
            self.high_leak_start = None

        if self.detection_mode == "disabled":
            self.micro_leak_start = None
            self.high_leak_start = None
            if not self.alarm_active:
                self.severity = "normal"
            return self._status_dict()

        # Retrieve thresholds based on mode
        # 1. Away Mode (very aggressive)
        if self.detection_mode == "away":
            micro_limit = 0.01
            micro_time = timedelta(minutes=2)
            high_limit = 0.2
            high_time = timedelta(minutes=1)
            critical_limit = 1.0
        # 2. Kitchen/RO Mode (for slow reverse osmosis membrane flushing)
        elif self.detection_mode == "kitchen_ro":
            micro_limit = 0.02
            micro_time = timedelta(minutes=120)
            high_limit = 0.5
            high_time = timedelta(minutes=20)
            critical_limit = 3.0
        # 3. Standard Mode
        else:
            micro_limit = 0.05
            micro_time = timedelta(minutes=30)
            high_limit = 1.0
            high_time = timedelta(minutes=10)
            critical_limit = 5.0

        # Critical leak detection
        if flow_rate >= critical_limit:
            if not self.alarm_active or self.severity != "critical":
                if not self.alarm_active:
                    self.leak_events_total += 1
                self.alarm_active = True
                self.severity = "critical"
            return self._status_dict()

        # High leak detection
        if flow_rate >= high_limit:
            if self.high_leak_start is None:
                self.high_leak_start = now
            elif now - self.high_leak_start >= high_time:
                if not self.alarm_active or self.severity not in ("high", "critical"):
                    if not self.alarm_active:
                        self.leak_events_total += 1
                    self.alarm_active = True
                    self.severity = "high"
        else:
            self.high_leak_start = None

        # Micro leak detection
        if flow_rate >= micro_limit:
            if self.micro_leak_start is None:
                self.micro_leak_start = now
            elif now - self.micro_leak_start >= micro_time:
                if not self.alarm_active or self.severity == "normal":
                    if not self.alarm_active:
                        self.leak_events_total += 1
                    self.alarm_active = True
                    self.severity = "micro"
        else:
            self.micro_leak_start = None

        # Alarm is latched. Severity persists until cleared.
        if not self.alarm_active:
            self.severity = "normal"

        return self._status_dict()

    def clear_alarm(self) -> None:
        """Manually clear the active leak alarm."""
        self.alarm_active = False
        self.severity = "normal"
        self.micro_leak_start = None
        self.high_leak_start = None

    def _status_dict(self) -> Dict[str, Any]:
        """Return status dict representation."""
        return {
            "alarm_active": self.alarm_active,
            "severity": self.severity,
            "leak_events_total": self.leak_events_total,
            "detection_mode": self.detection_mode,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert engine state to dict for storage."""
        return {
            "alarm_active": self.alarm_active,
            "severity": self.severity,
            "events_total": self.leak_events_total,
            "detection_mode": self.detection_mode,
            "micro_start_iso": self.micro_leak_start.isoformat() if self.micro_leak_start else None,
            "high_start_iso": self.high_leak_start.isoformat() if self.high_leak_start else None,
        }
