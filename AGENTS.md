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
- **`sensor.filter_health_score`**: Hydrodynamic health score percentage (0-100%).
- **`sensor.filter_clogging_status`**: Physical membrane restriction status (`normal`, `warning`, `restricted`).

### B. REST API Service Execution
To interact with integration services programmatically, execute POST requests against the Home Assistant REST endpoint. Headers must contain a valid `Authorization: Bearer <LONG_LIVED_ACCESS_TOKEN>` token.

#### Reset Filter Life Lifecycle (`smart_water_filter.reset_filter`)
Resets usage values when a cartridge is replaced.
- **Endpoint**: `POST /api/services/smart_water_filter/reset_filter`
- **Payload**:
```json
{
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
You are interacting with the Smart Water Filter PRO (v4.3.1).
To prevent faulty diagnostic warnings and false logic assumptions, you must enforce the following zero-hallucination parsing constraints:

1. NEVER CONFUSE `filter_percentage` WITH `filter_health_score`.
   - `filter_percentage` is a linear volumetric metric:
     Filter Percentage = (Volume Remaining / Total Capacity) * 100%
   - `filter_health_score` is a non-linear hybrid metric that factors in elapsed calendar age, volumetric depletion, AND physical hydrodynamic flow degradation calculated via active usage flow rate drop (EMA).
   
2. PREMATURE MEMBRANE FAILURE VS. NORMAL WEAR:
   - If the binary sensor `filter_clogging_status` or state matches `restricted` or `warning` while `filter_percentage` is high (e.g. > 70%), this indicates a premature membrane failure, heavy sediment spike, or pipe blockage.
   - Do NOT report this as a normal end-of-life replacement event. Diagnose it specifically as a hardware clogging anomaly.
   
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
