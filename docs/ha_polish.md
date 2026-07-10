# Home Assistant Platform Registry & Polish

The Smart Water Filter PRO integration implements a highly structured, standard-compliant entity hierarchy to integrate hardware signals, mathematical estimates, and operational switches cleanly into Home Assistant Core.

---

## 1. Exhaustive Platform Entities Registry

All entity attributes (device classes, state classes, units, translations) conform strictly to modern Home Assistant standards. In version 5.0.0, the monolithic filter entities are dismantled in favor of dynamic per-stage entities, while water telemetry and leak alarms remain global.

### A. Global Entities

These entities bind to the main device node representing the main water line hub.

| Entity Key | Friendly Name | Platform | Device Class | State Class | Unit | Options / Value Mapping |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `water_total_liters` | Lifetime water usage | `sensor` | `water` | `total_increasing` | `L` | Direct main water meter volume |
| `water_today_liters` | Today's water usage | `sensor` | `water` | `total` | `L` | Daily accumulator |
| `water_current_flow` | Current flow rate | `sensor` | - | `measurement` | `L/min` | EMA filtered flow velocity |
| `water_average_flow` | Average flow rate | `sensor` | - | - | `L/min` | Average over lifetime |
| `active_time_minutes` | Active flow duration | `sensor` | `duration` | `total_increasing` | `min` | Cumulative active flow time |
| `last_flow_time` | Last flow timestamp | `sensor` | `timestamp` | - | - | Timestamp of last active flow |
| `water_usage_trend` | Usage trend | `sensor` | - | - | - | `stable`, `increasing`, `decreasing` |
| `water_leak_alarm` | Water leak alarm | `binary_sensor`| `problem` | - | - | Latching leak alert |
| `sensor_fault` | Flow sensor fault | `binary_sensor`| `problem` | - | - | Pulse rate offline/warning indicator |
| `clear_alarm` | Dismiss leak alarm | `button` | - | - | - | Dismisses active latched leak alarm |
| `smart_water_filter_export_backup` | Export pretty backup | `button` | - | - | - | Compiles and writes JSON backup file |
| `pulses_per_liter` | Sensor calibration factor | `number` | - | - | - | Modifies flow meter pulse coefficient |

### B. Dynamic Stage-Specific Entities

These entities are dynamically generated per registered filtration stage. Their friendly names are constructed using translation placeholders: `{stage_name} <metric>`.

| Entity Key / Suffix | Friendly Name Schema | Platform | Device Class | Unit | Options / Value Mapping |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `{stage_id}_remaining_liters`| `{stage_name} water remaining` | `sensor` | `water` | `L` | Liters remaining in this cartridge |
| `{stage_id}_remaining_days` | `{stage_name} estimated days left`| `sensor` | - | `d` | Forecast days left based on EMA usage |
| `{stage_id}_health_score` | `{stage_name} overall health` | `sensor` | - | `%` | Hybrid score (Volume, Age, Peak flow) |
| `{stage_id}_replace_required`| `{stage_name} replacement alert` | `binary_sensor`| `problem` | - | `ON` when health status is replace soon/now |
| `reset_{stage_id}` | `Reset {stage_name}` | `button` | - | - | Resets usage, logs replacement details |
| `{stage_id}_capacity` | `{stage_name} capacity limit` | `number` | - | `L` | Modifies stage capacity (100L - 20000L) |
| `{stage_id}_max_age` | `{stage_name} lifespan limit` | `number` | - | `d` | Modifies stage max lifespan (30d - 1095d) |

---

## 2. Unique ID Derivation Schema

To ensure entity identifiers remain unique and stable across software updates, registry reloads, and network address changes, the integration uses the Home Assistant config entry unique ID (generated on initial set up) combined with the stage ID and the platform entity description key:

- **Global Entities**:
  \[ UniqueID = \text{EntryID} + \text{"\_"} + \text{EntityKey} \]
  *Example*: `f8a329d9120e_water_leak_alarm`

- **Dynamic Stage Entities**:
  \[ UniqueID = \text{EntryID} + \text{"\_"} + \text{StageID} + \text{"\_"} + \text{MetricKey} \]
  *Example*: `f8a329d9120e_main_filter_remaining_liters`

---

## 3. Device Registry Bindings

All platform entities bind to a single device registry node. This binds the entity cards under a unified header inside the Home Assistant Settings menu.

```python
self._attr_device_info = DeviceInfo(
    identifiers={(DOMAIN, coordinator.entry.entry_id)},
    name="Smart Water Filter PRO",
    manufacturer="KRISUUUU",
    model="ESP32 Ultra-Flow Sentinel Node",
    sw_version="5.0.0",
)
```

---

## 4. Action / Service Definitions (`services.yaml`)

The integration exports the following service actions:

### `smart_water_filter.add_filter_stage`
Injects a new filtration stage dynamically into the cascade. Generates a slugified ID and reloads configuration entries to dynamically build entities.
- **Fields**:
  - `name` (Required): A friendly name for the stage (e.g. "Sediment Filter").
  - `type` (Required): Preset type (`carbon`, `capillary`, `sediment`, `custom`).
  - `capacity` (Optional): Volume capacity in liters. Default is 3000.0.
  - `max_age_days` (Optional): Lifespan limit in calendar days. Default is 365.0.

### `smart_water_filter.remove_filter_stage`
Removes an active filtration stage from the cascade by ID, clean up entities, and reloads.
- **Fields**:
  - `stage_id` (Required): The slugified ID of the stage to remove (e.g. `sediment_filter`).

### `smart_water_filter.reset_filter`
Resets the volumetric counter and archives replacement history for a specific stage.
- **Fields**:
  - `stage_id` (Required): The slugified ID of the stage to reset.
  - `capacity` (Optional): Override capacity in Liters.
  - `reason` (Optional): Replacement reason (`routine`, `taste`, `clogged`, `time`). Default is `manual`.

### `smart_water_filter.clear_alarm`
Manually clears the active leak alarm state.

### `smart_water_filter.start_calibration`
Puts the integration into calibration mode. Accumulates raw sensor pulse counts.

### `smart_water_filter.finish_calibration`
Concludes calibration, calculates pulses per liter based on the user-reported volume output, and updates the state.
- **Fields**:
  - `actual_volume` (Required): The actual volume of water collected during calibration.

### `smart_water_filter.set_leak_mode`
Directly shifts the leak engine profile.
- **Fields**:
  - `mode` (Required): Active profile name (`standard`, `kitchen_ro`, `away`, `disabled`).

### `smart_water_filter.export_history`
Exports replacement and consumption events to the Home Assistant storage path.

---

## 5. Options Flow Configuration Menu

All configuration management has been unified into a professional Options Flow wizard inside the Home Assistant device configuration settings. The options flow supports the following steps:

1. **Main Selection (`init`)**: Allows selection of which action to perform:
   - Configure Flow & Leak Settings
   - Add New Filter Stage
   - Remove Filter Stage
   - View/Edit Filter Stages
2. **Sensor & Leak Settings (`sensor_leak_settings`)**: Configure global flow meter and leak engine parameters:
   - `source_sensor`: Select water flow sensor.
   - `source_type`: Pulse-based or direct Liter-based measurement mode.
   - `pulses_per_liter`: Modifies calibration factor.
   - `leak_detection_mode`: Active leak detection profile (Standard, Kitchen RO, Away, Disabled).
   - `replacement_reason`: Set default reason when a filter is replaced.
3. **Add Stage (`add_stage` & `add_stage_custom`)**: Configure new filtration stages:
   - Presets: Carbon (4000L, 365 days), Capillary (5000L, 365 days), Sediment (3000L, 180 days).
   - Custom: Allows manual name, capacity (Liters), and max age (Days).
4. **Remove Stage (`remove_stage`)**: Safely removes a filtration stage by selecting from a list of currently active stages.
5. **Edit Stage (`edit_stage` & `edit_stage_details`)**: Modify the capacity or maximum age parameters of any active filtration stage.

