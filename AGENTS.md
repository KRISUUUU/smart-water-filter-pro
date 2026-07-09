# AI Agent Knowledge Base & API Contract

This document contains the authoritative developer and integration rules for external AI Agents or automated scripts interfacing with the Smart Water Filter PRO integration.

---

## 1. API Contract Specifications

External entities can query telemetries and execute actions using Home Assistant's native WebSocket and REST API layers.

### A. WebSocket Subscription (State Telemetries)
To subscribe to real-time telemetry changes, connect to the Home Assistant WebSocket endpoint (`/api/websocket`) and authenticate. Once authorized, send the event subscription frame:

```json
{
  "id": 1,
  "type": "subscribe_events",
  "event_type": "state_changed"
}
```

External clients must filter state events using the following specific entity IDs:
- **`sensor.water_flow_rate`**: Stream flow speed (L/min).
- **`sensor.total_volume`**: Cumulative total liters consumed since initialization.
- **`binary_sensor.water_leak_alarm`**: Moisture problem leak notification state (`ON` / `OFF`).
- **`sensor.{stage_id}_health_score`**: Hydrodynamic health score percentage (0-100%) for a specific stage.
- **`sensor.{stage_id}_remaining_liters`**: Volume remaining in liters for a specific stage.
- **`sensor.{stage_id}_remaining_days`**: Estimated days remaining for a specific stage.
- **`binary_sensor.{stage_id}_replace_required`**: Alert status (`ON` / `OFF`) for a specific stage.

### B. REST API Service Execution
To interact with integration services programmatically, execute POST requests against the Home Assistant REST endpoint. Headers must contain a valid `Authorization: Bearer <LONG_LIVED_ACCESS_TOKEN>` token.

#### Add Filter Stage Lifecycle (`smart_water_filter.add_filter_stage`)
Injects a new filtration stage dynamically into the cascade.
- **Endpoint**: `POST /api/services/smart_water_filter/add_filter_stage`
- **Payload**:
```json
{
  "name": "Sediment Filter",
  "type": "sediment",
  "capacity": 3000,
  "max_age_days": 365
}
```

#### Remove Filter Stage Lifecycle (`smart_water_filter.remove_filter_stage`)
Removes a filtration stage by ID.
- **Endpoint**: `POST /api/services/smart_water_filter/remove_filter_stage`
- **Payload**:
```json
{
  "stage_id": "sediment_filter"
}
```

#### Reset Filter Life Lifecycle (`smart_water_filter.reset_filter`)
Resets usage values when a cartridge is replaced for a specific stage.
- **Endpoint**: `POST /api/services/smart_water_filter/reset_filter`
- **Payload**:
```json
{
  "stage_id": "main_filter",
  "capacity": 5000,
  "reason": "taste"
}
```

#### Set Active Leak Detection Mode (`smart_water_filter.set_leak_mode`)
Switches sensitivity profiles.
- **Endpoint**: `POST /api/services/smart_water_filter/set_leak_mode`
- **Payload**:
```json
{
  "mode": "away"
}
```

#### Clear Latched Leak Alarm (`smart_water_filter.clear_alarm`)
Clears active latched leak triggers.
- **Endpoint**: `POST /api/services/smart_water_filter/clear_alarm`
- **Payload**: `{}`

---

## 2. LLM System Prompt Ingestion Component

Subsequent LLM agents and system developers interacting with this integration's telemetry must ingest the following system instruction block directly into their context window:

```text
[SYSTEM INSTRUCTION: SMART WATER FILTER PRO TELEMETRY INTEGRATION]
You are interacting with the Smart Water Filter PRO (v5.0.0).
To prevent faulty diagnostic warnings and false logic assumptions, you must enforce the following zero-hallucination parsing constraints:

1. NEVER CONFUSE `stage_percentage` WITH `stage_health_score` FOR A GIVEN STAGE.
   - `stage_percentage` is a linear volumetric metric:
     Stage Percentage = (Volume Remaining / Total Capacity) * 100%
   - `stage_health_score` is a non-linear hybrid metric that factors in elapsed calendar age, volumetric depletion, AND physical hydrodynamic flow degradation calculated via active usage flow rate drop (EMA) for that specific stage.
   
2. PREMATURE MEMBRANE FAILURE VS. NORMAL WEAR:
   - If a stage's attributes or state indicate high degradation or clogging status is warning/restricted while `stage_percentage` is high (e.g. > 70%), this indicates a premature membrane failure, heavy sediment spike, or pipe blockage.
   - Do NOT report this as a normal end-of-life replacement event. Diagnose it specifically as a hardware clogging anomaly for that stage.
   
3. LEAK ALARM LATCHING RULES:
   - Leak alarms are latched. Once a leak severity moves to 'micro', 'high', or 'critical', the alarm entity state remains active even if flow stops (0.0 L/min).
   - If you detect an active leak alarm with 0.0 L/min flow rate, do NOT report it as an active water leak. Inform the user that a leak event occurred and requires a manual clear service execution.
```

---

## 3. Testing Execution Layer

To verify code refactors do not introduce regressions into the mathematical predictors (EMA/SMA), calibration formulas, or the Leak Engine FSM, execute the testing suite using `pytest`.

Ensure your current python environment contains `pytest` and `pytest-cov`, and set your `PYTHONPATH` to include the `custom_components/` directory:

```bash
# Set PYTHONPATH and execute all core engine tests in verbose mode
PYTHONPATH=custom_components pytest tests/ -v

# Run the complete test suite and output test coverage results
PYTHONPATH=custom_components pytest tests/ --cov=custom_components.smart_water_filter --cov-report=term-missing
```

---

> **CRITICAL REPO GUARDRAIL**: EVERY subsequent codebase refinement, feature addition, bug mitigation, or hardware refactor MUST execute an atomic entry tracking the modification within CHANGELOG.md and immediately update or append the corresponding documentation file inside `docs/`. Any code commit pushed without synchronized documentation updates constitutes a critical deployment breaking failure.
