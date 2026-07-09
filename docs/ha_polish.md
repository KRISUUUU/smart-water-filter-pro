# Home Assistant Platform Registry & Polish

The Smart Water Filter PRO integration implements a highly structured, standard-compliant entity hierarchy to integrate hardware signals, mathematical estimates, and operational switches cleanly into Home Assistant Core.

---

## 1. Exhaustive Platform Entities Registry

All entity attributes (device classes, state classes, units, translations) conform strictly to modern Home Assistant standards.

### A. Sensors (`sensor`)
Exposes telemetry, predictions, and diagnostic states.

| Entity Key | Friendly Name | Device Class | State Class | Unit | Options / Value Mapping |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `water_today_liters` | Today's Water Volume | `water` | `total` | `L` | Direct daily accumulator |
| `water_current_flow` | Current Flow Rate | - | `measurement` | `L/min` | EMA filtered flow velocity |
| `water_average_flow` | Average Flow Rate | - | - | `L/min` | Simple average over usage cycle |
| `active_time_minutes` | Active Flow Duration | `duration` | `total_increasing` | `min` | Cumulative time in flow state |
| `last_flow_time` | Last Flow Time | `timestamp` | - | - | ISO timestamp of last active flow |
| `filter_capacity` | Filter Capacity | `water` | - | `L` | Total rated volume limit |
| `filter_used` | Filter Volume Used | `water` | - | `L` | Consumed liters since replacement |
| `filter_remaining` | Filter Volume Left | `water` | - | `L` | Remaining capacity liters |
| `filter_percentage` | Filter Capacity Left | - | - | `%` | Linear percentage remaining |
| `filter_max_age` | Filter Lifespan Limit | - | - | `d` | Max rated cartridge age in days |
| `filter_age_days` | Filter Cartridge Age | - | - | `d` | Elapsed calendar days since install |
| `filter_flow_degradation`| Flow Rate Degradation | - | - | `%` | Flow velocity drop against baseline |
| `filter_clogging_status` | Clogging Status | - | - | - | `normal`, `warning`, `restricted` |
| `filter_health_score` | Overall Health Score | - | - | `%` | Hybrid weighted metric (Volume, Age, Flow) |
| `filter_health` | Filter Health Rating | - | - | - | `excellent`, `good`, `fair`, `replace_soon`, `replace_now` |
| `water_usage_trend` | Water Usage Trend | - | - | - | `stable`, `increasing`, `decreasing` |
| `estimated_days` | Estimated Days Left | - | - | `d` | Predictor output (days remaining) |
| `confidence` | Prediction Confidence | - | - | `%` | Predictor statistical stability rating |

### B. Binary Sensors (`binary_sensor`)
Exposes Boolean status warnings. All use `device_class: problem`.

- **`water_leak_alarm`**: Switches `ON` when a leak is active. 
  - *Attributes*: `severity` (`normal`, `micro`, `high`, `critical`), `events_total` (total alarm event log counter).
- **`filter_replace`**: Switches `ON` when `filter_health_status` falls into `replace_soon` or `replace_now`.
  - *Attributes*: `health_score` (%), `remaining_liters` (L), `estimated_days` (d).
- **`sensor_fault`**: Switches `ON` when the telemetry flow sensor heartbeat drops offline or acts erratically.
  - *Attributes*: `time_since_last_pulse_seconds`.

### C. Buttons (`button`)
Exposes service tasks that trigger immediate operations.

- **`reset_filter`**: Resets the volumetric and aging counters, archiving the current cartridge usage into the historical log under the reason chosen in the `replacement_reason` select entity.
- **`clear_alarm`**: Manually clears a latched leak alarm and resets severity to `normal`.
- **`smart_water_filter_export_backup`**: Compiles integration storage database parameters and exports a JSON backup file to the local path.

### D. Numbers (`number`)
Exposes numeric variables that can be modified directly in the UI.

- **`filter_capacity`**: Adjusts the maximum target capacity of the filter cartridge in liters.
  - *Bounds*: Min `100.0 L`, Max `20000.0 L`, Step `50.0 L`.
- **`filter_max_age`**: Adjusts the calendar age replacement target.
  - *Bounds*: Min `30 d`, Max `1095 d` (3 years), Step `1.0 d`.
- **`pulses_per_liter`**: Calibrates the flow meter's pulse coefficient.
  - *Bounds*: Min `10.0`, Max `2000.0`, Step `0.1` pulses/L.

### E. Selects (`select`)
Exposes operational profile selection dropdowns.

- **`replacement_reason`**: Defines the categorization reason for the next filter reset.
  - *Options*: `routine` (default), `clogged`, `taste`, `time`.
- **`leak_detection_mode`**: Selects the active sensitivity profile of the Leak Engine state machine.
  - *Options*: `standard`, `kitchen_ro`, `away`, `disabled`.

---

## 2. Unique ID Derivation Schema

To ensure entity identifiers remain unique and stable across software updates, registry reloads, and network address changes, the integration uses the Home Assistant config entry unique ID (generated on initial set up) combined with the platform entity description key:

\[ UniqueID = \text{EntryID} + \text{"\_"} + \text{EntityKey} \]

For example, for a config entry ID `f8a329d9120e` and key `water_leak_alarm`, the unique ID is:
`f8a329d9120e_water_leak_alarm`

---

## 3. Device Registry Bindings

All platform entities bind to a single device registry node. This binds the entity cards under a unified header inside the Home Assistant Settings menu.

```python
self._attr_device_info = DeviceInfo(
    identifiers={(DOMAIN, coordinator.entry.entry_id)},
    name="Smart Water Filter",
    manufacturer="Antigravity PRO",
    model="Filter Engine v4",
    sw_version="4.3.1",
)
```

---

## 4. Service Definitions (`services.yaml`)

The integration exports the following service calls:

### `smart_water_filter.reset_filter`
Resets the volumetric counter and archive replacement history.
- **Fields**:
  - `capacity` (Optional): The new capacity limit in Liters. Bounds: 100 to 20000.
  - `reason` (Optional): Replacement reason (`routine`, `taste`, `clogged`, `time`). Default is `manual`.

### `smart_water_filter.clear_alarm`
Manually clears the active leak alarm state.

### `smart_water_filter.start_calibration`
Puts the integration into calibration mode. Accumulates raw sensor pulse counts.

### `smart_water_filter.finish_calibration`
Concludes calibration, calculates pulses per liter based on the user-reported volume output, and updates the state.
- **Fields**:
  - `actual_volume` (Required): The actual volume of water collected during calibration. Bounds: 0.1 to 100.0 L.

### `smart_water_filter.set_leak_mode`
Directly shifts the leak engine profile.
- **Fields**:
  - `mode` (Required): Active profile name (`standard`, `kitchen_ro`, `away`, `disabled`).

### `smart_water_filter.export_history`
Exports replacement and consumption events to the Home Assistant storage path.
