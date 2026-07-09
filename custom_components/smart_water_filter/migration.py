"""Storage migrations for Smart Water Filter."""
from typing import Any

async def async_migrate_storage(old_version: int, old_minor_version: int, data: dict[str, Any]) -> dict[str, Any]:
    """Migrate storage data to the current version (v5) using a step-by-step migration chain."""
    migrated_data = data.copy()

    # Step 1: Migrate v1 to v2
    if old_version == 1:
        migrated_data = migrate_v1_to_v2(migrated_data)
        old_version = 2

    # Step 2: Migrate v2 to v3
    if old_version == 2:
        migrated_data = migrate_v2_to_v3(migrated_data)
        old_version = 3

    # Step 3: Migrate v3 to v4
    if old_version == 3:
        migrated_data = migrate_v3_to_v4(migrated_data)
        old_version = 4

    # Step 4: Migrate v4 to v5
    if old_version == 4:
        migrated_data = migrate_v4_to_v5(migrated_data)
        old_version = 5

    return migrated_data

def migrate_v1_to_v2(data: dict[str, Any]) -> dict[str, Any]:
    """Migrate from v1 to v2 schema."""
    migrated = data.copy()
    total = float(migrated.get("total", 0.0))
    migrated["lifetime_total_liters"] = total
    migrated["filter_used_liters"] = 0.0
    migrated["filter_capacity_liters"] = 3000.0
    migrated["filter_installed_date"] = None
    migrated["filter_history"] = []
    migrated["daily_history"] = []
    migrated["hourly_profile"] = {}
    migrated["leak_alarm_active"] = False
    migrated["leak_severity"] = "normal"
    migrated["leak_counter"] = 0
    if "total" in migrated:
        del migrated["total"]
    return migrated

def migrate_v2_to_v3(data: dict[str, Any]) -> dict[str, Any]:
    """Migrate from v2 to v3 schema."""
    migrated = data.copy()
    
    capacity = float(migrated.get("filter_capacity_liters", 3000.0))
    used = float(migrated.get("filter_used_liters", 0.0))
    installed = migrated.get("filter_installed_date")
    history = migrated.get("filter_history", [])
    
    daily = migrated.get("daily_history", [])
    hourly = migrated.get("hourly_profile", {})
    
    leak_active = migrated.get("leak_alarm_active", False)
    leak_sev = migrated.get("leak_severity", "normal")
    leak_cnt = migrated.get("leak_counter", 0)
    
    lifetime = float(migrated.get("lifetime_total_liters", 0.0))
    today = float(migrated.get("today_used_liters", 0.0))
    active = float(migrated.get("active_time_seconds", 0.0))
    last_date = migrated.get("last_date_str")
    last_h = migrated.get("last_hour")
    hourly_acc = float(migrated.get("hourly_accumulator", 0.0))
    
    return {
        "filter": {
            "capacity": capacity,
            "used": used,
            "installed_date": installed,
            "max_age_days": 365.0,
            "baseline_flow_rate": 0.0,
            "recent_max_flow_rate": 0.0,
            "history": history
        },
        "statistics": {
            "daily": daily,
            "hourly": hourly
        },
        "calibration": {
            "pulses_per_liter": 450.0
        },
        "events": [],
        "leak": {
            "alarm_active": leak_active,
            "severity": leak_sev,
            "events_total": leak_cnt,
            "detection_mode": "standard"
        },
        "totals": {
            "lifetime_liters": lifetime,
            "today_liters": today,
            "active_time": active,
            "last_date_str": last_date,
            "last_hour": last_h,
            "hourly_accumulator": hourly_acc,
            "last_flow_time": None
        }
    }

def migrate_v3_to_v4(data: dict[str, Any]) -> dict[str, Any]:
    """Migrate from v3 to v4 schema."""
    migrated = data.copy()
    
    # Ensure totals exists and has filtered_flow_rate
    totals = migrated.setdefault("totals", {})
    if "filtered_flow_rate" not in totals:
        totals["filtered_flow_rate"] = 0.0
        
    # Ensure leak exists and has starts
    leak = migrated.setdefault("leak", {})
    if "micro_start_iso" not in leak:
        leak["micro_start_iso"] = None
    if "high_start_iso" not in leak:
        leak["high_start_iso"] = None
        
    return migrated

def migrate_v4_to_v5(data: dict[str, Any]) -> dict[str, Any]:
    """Migrate from v4 to v5 schema."""
    migrated = data.copy()
    old_filter = migrated.pop("filter", {})
    stages = []
    if old_filter:
        stages.append({
            "id": "main_filter",
            "name": "Main Filter",
            "type": "custom",
            "capacity_liters": float(old_filter.get("capacity", 3000.0)),
            "max_age_days": int(old_filter.get("max_age_days", 365)) if old_filter.get("max_age_days") is not None else 365,
            "used_liters": float(old_filter.get("used", 0.0)),
            "installed_date": old_filter.get("installed_date"),
            "baseline_flow_rate": float(old_filter.get("baseline_flow_rate", 0.0)),
            "recent_max_flow_rate": float(old_filter.get("recent_max_flow_rate", 0.0)),
            "history": old_filter.get("history", [])
        })
    migrated["stages"] = stages
    return migrated
