"""Event logger for tracking filter replacements, leaks, and calibrations."""
from datetime import datetime
from typing import List, Dict, Any
from .const import MAX_EVENTS

class EventLogger:
    """Stores and manages history of system events."""

    def __init__(self, events: List[Dict[str, Any]] = None) -> None:
        self.events = events or []

    def log_event(self, event_type: str, message: str, details: Dict[str, Any] = None) -> None:
        """Add a new event log entry."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "type": event_type,
            "message": message,
            "details": details or {},
        }
        self.events.append(entry)
        
        # Keep only up to MAX_EVENTS entries
        if len(self.events) > MAX_EVENTS:
            self.events = self.events[-MAX_EVENTS:]

    def to_list(self) -> List[Dict[str, Any]]:
        """Return raw event list."""
        return self.events
