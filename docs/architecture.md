# Architecture: Asynchronous Data Pipeline & Storage

The Smart Water Filter PRO integration (v4.3.1) is engineered for high-frequency telemetry processing, mathematical degradation forecasting, and real-time anomaly detection inside Home Assistant Core. It operates on a local-first, zero-polling design.

---

## 1. Asynchronous, Event-Driven Data Pipeline

### Local Push Ingestion
Rather than polling the hardware node, the integration subscribes directly to state changes of the configured source entities (e.g., `sensor.water_flow_rate` or `sensor.water_pulses` exposed by ESPHome). 

The flow sensor on the ESP32 pushes state updates to Home Assistant via the native ESPHome API over a persistent TCP socket. Within Home Assistant, the `WaterFilterCoordinator` (inheriting from `DataUpdateCoordinator`) hooks directly into the Home Assistant state machine.

```
+------------------+                   +----------------------+                   +------------------------+
|   ESP32 Node     |  TCP Local Push   |    Home Assistant    |  Event Listener   | WaterFilterCoordinator |
|  (ESPHome API)   | ----------------> |    State Engine      | ----------------> |  (State Change Hook)   |
+------------------+                   +----------------------+                   +------------------------+
```

### Event-Driven Execution
Upon loading, the coordinator executes `async_setup` and invokes `async_track_state_change_event` from `homeassistant.helpers.event`. This registers a callback in the core event loop:

- **Callback Hook**: `coordinator._async_on_state_change`
- **Zero-Polling Latency**: The integration does not run a timer to fetch data. The coordinator's callback is executed *instantly* by the Home Assistant event loop when a state change event for the source sensor is fired.
- **Thread Safety**: All state parsing, delta calculations, and state machine transitions are written as non-blocking async-friendly code executing in the main event thread, with CPU-heavy or storage operations offloaded appropriately.

---

## 2. Storage Engine & Transaction Safety

Persistence of total water volume, statistical histories, calibration coefficients, and leak engine tracking states across restarts is managed by the `homeassistant.helpers.storage.Store` class.

### Thread Isolation & Non-Blocking I/O
The Home Assistant core event loop must never be blocked by synchronous disk reads/writes. To enforce this:
1. **Asynchronous Load**: At startup, `self.store.async_load()` is called to retrieve the persisted state. This returns a coroutine that loads and parses the JSON file in an executor thread, keeping the event loop fully responsive.
2. **Asynchronous Save**: When states change (such as hourly usage summaries or daily rollovers), `self.store.async_save(data)` is dispatched. This schedules a thread-safe write to disk in a separate thread.
3. **Atomic Writes**: The `Store` class writes to a temporary file (`.storage/smart_water_filter.tmp`) and then atomically renames it to the target file. This prevents file corruption in the event of sudden power failures or server crashes.

---

## 3. Schema Migration Matrix (v1 to v4)

As the integration evolved, the persistent storage JSON structure was upgraded. The `migration.py` module defines a step-by-step migration chain executed automatically inside `async_migrate_storage` during startup:

```
[ v1 Schema ] 
      |
      v  (migrate_v1_to_v2)
[ v2 Schema ] 
      |
      v  (migrate_v2_to_v3)
[ v3 Schema ] 
      |
      v  (migrate_v3_to_v4)
[ v4 Schema ] (Current Production Target)
```

### Precise Migration Details

| Source Version | Target Version | Migration Function | Action Taken & Fields Mapped |
| :--- | :--- | :--- | :--- |
| **v1** | **v2** | `migrate_v1_to_v2` | - Renames legacy flat field `"total"` to `"lifetime_total_liters"`. <br>- Initializes new tracking variables: `"filter_used_liters"` (0.0), `"filter_capacity_liters"` (3000.0), `"filter_installed_date"` (None). <br>- Appends history structures: `"filter_history"`, `"daily_history"`, `"hourly_profile"`. <br>- Appends baseline leak variables: `"leak_alarm_active"` (False), `"leak_severity"` ("normal"), `"leak_counter"` (0). |
| **v2** | **v3** | `migrate_v2_to_v3` | - Restructures flat database into a deeply nested schema with isolated domains: <br>&nbsp;&nbsp;* `"filter"`: Lifespan configuration and max age (365.0 days). <br>&nbsp;&nbsp;* `"statistics"`: Holds rolling history and hourly profiles. <br>&nbsp;&nbsp;* `"calibration"`: Houses pulses-per-liter factor (default 450.0). <br>&nbsp;&nbsp;* `"leak"`: Separates alarm, severity, and event counters, adding `"detection_mode"`. <br>&nbsp;&nbsp;* `"totals"`: Aggregates runtime statistics. |
| **v3** | **v4** | `migrate_v3_to_v4` | - Adds `"filtered_flow_rate"` (0.0) into the `"totals"` namespace. <br>- Inserts continuous leak start timestamps `"micro_start_iso"` (None) and `"high_start_iso"` (None) into the `"leak"` database to ensure that active continuous-leak timers survive Home Assistant reboots and configuration reloads. |

---

## 4. Resource Usage & Execution Guardrails
- **Debounced Writes**: State saving is throttled or run at logical boundaries (such as midnight, hourly, or when a leak state changes) to protect flash storage (SD cards, SSDs) from write amplification wear.
- **I/O Offloading**: All JSON serialization and file operations are managed by Home Assistant's helper threads, preventing CPU latency spikes.
