<p align="center">
  <img src="docs/images/banner.png" alt="Smart Water Filter PRO Banner" width="100%">
</p>


[![Status: Beta | v4.3.1](https://img.shields.io/badge/Status-Beta%20%7C%20v4.3.1-blue.svg)](https://github.com/custom-components/smart_water_filter)
[![Platform: ESPHome & Home Assistant Core](https://img.shields.io/badge/Platform-ESPHome%20%26%20Home%20Assistant%20Core-orange.svg)](https://esphome.io)
[![Architecture: Local-First Monorepo](https://img.shields.io/badge/Architecture-Local--First%20Monorepo-green.svg)](docs/architecture.md)


# Smart Water Filter PRO (v4.3.1)

Smart Water Filter PRO is a production-grade, local-first, event-driven Home Assistant integration designed to monitor and forecast the health, degradation, capacity, and leak parameters of home water filtration systems.

---

## Co (What)
Smart Water Filter PRO is a complete hardware-software monorepo solution. It interfaces directly with Hall-effect flow sensors (such as the YF-S201) connected to an ESP32 microcontroller, pulling real-time pulse data into Home Assistant. Using hybrid mathematical forecasting (EMA and SMA models) and a multi-profile Leak Engine state machine, it provides:
- Exact remaining volume and remaining cartridge lifespan calculations.
- Clogging indicators based on hydrodynamic flow velocity degradation.
- Four distinct leak detection sensitivity profiles (Standard, Away, Kitchen/RO, Disabled) with persistent alarm states.

## Jak (How)
1. **ESPHome Hardware Level**: The ESP32 captures flow sensor turbine rotations using a debounced hardware `pulse_counter` register. It runs a local Riemann sum totalizer to aggregate water consumption directly on the microcontroller CPU register, saving states to NVRAM every 5 minutes to survive network disconnections and reboot cycles.
2. **Home Assistant Integration**: The integration receives updates over the native ESPHome Local Push TCP API. The custom component hooks into Home Assistant Core using `async_track_state_change_event` for zero-polling latency.
3. **Intelligence Layer**: The custom component executes Exponential Moving Average (EMA) and 7-day Simple Moving Average (SMA) models to predict depletion dates and calculate prediction confidence ratings.

## Po co (Why)
- **Zero Cloud Latency**: Alarms trigger instantly when thresholds are met, safeguarding homes from catastrophic pipe bursts.
- **Precision Filter Life Tracking**: Eliminates arbitrary time-based replacement schedules, replacing filters only when their volumetric capacity is exhausted or when physical clogging restricts flow.
- **Data Sovereignty**: Keep all plumbing telemetry inside your local network, isolated from external cloud servers.

---

## Monorepo Project Structure

```text
.
├── .gitignore               # Testing, Python cache, and secrets exclusion rules
├── AGENTS.md                # Authoritative API contract & prompt context for AI agents
├── CHANGELOG.md             # Semantic release records
├── ESP32.md                 # Complete, build-ready ESPHome YAML configuration
├── README.md                # Main landing page and repository map
├── hacs.json                # HACS distribution manifest
├── custom_components/
│   └── smart_water_filter/  # Core Home Assistant integration code
│       ├── __init__.py      # Setup logic and service registers
│       ├── coordinator.py   # State tracking and event handlers
│       ├── filter_engine.py # Hydrodynamic degradation & hybrid health math
│       ├── leak_engine.py   # Leak detection FSM & modes
│       ├── predictor.py     # Volumetric & chronological forecasting
│       ├── statistics.py    # SMA/EMA data processing
│       ├── sensor.py        # Numerical entity platform registry
│       ├── binary_sensor.py # Boolean status entity platform registry
│       ├── button.py        # Reset & clearance button platform registry
│       ├── number.py        # Calibration & config slider platform registry
│       ├── select.py        # Mode dropdown platform registry
│       └── services.yaml    # Native HA service schemas
├── docs/
│   ├── architecture.md      # Event pipeline, async safety, and migration flowcharts
│   ├── ha_polish.md         # Full entity list, unique ID mapping, and HA device bindings
│   ├── hardware_esphome.md  # ESP32 pinout diagram, pull-up wiring, and debounce specs
│   └── intelligence_engines.md # Formal mathematical models & Leak state-machine details
├── examples/                # ESPHome configuration boilerplate YAML files
└── tests/                   # Full pytest verification suite
```

---

## Technical Documentation

Refer to the production-grade documentation files inside `docs/` for deep implementation details:

- [**Ecosystem Architecture & Storage Security** (docs/architecture.md)](docs/architecture.md): Covers event handling, `Store` file operations, and the v1-to-v4 schema migrations.
- [**Intelligence Engines & State Machines** (docs/intelligence_engines.md)](docs/intelligence_engines.md): Detail mathematical equations, confidence factors, and state transition thresholds for leak detection.
- [**Home Assistant Registry & Entity Polish** (docs/ha_polish.md)](docs/ha_polish.md): Explains entity properties, deterministic `unique_id` formulas, and service parameters.
- [**Hardware Specification & ESPHome Config** (docs/hardware_esphome.md)](docs/hardware_esphome.md): Diagram of ESP32 wiring, YF-S201 connections, pull-ups, and microcontroller calculations.

---

### ⚠️ CRITICAL CONFIGURATION NOTE: Measurement Mode Selection

During the initial configuration setup flow, you will be prompted to select the **Measurement Mode** (`source_type`):

1. **Liters Mode (`liters`) [RECOMMENDED FOR THIS MONOREPO]:**
   Select this if your source sensor is already computing cumulative water volume (like the native `sensor.water_total_volume` provided in our `ESP32.md` configuration). This bypasses Python-side processing and maps the data 1:1 with hardware-precision Riemann sums.
   
2. **Pulses Mode (`pulses`):**
   Select this **ONLY** if your ESPHome configuration passes a raw, un-calculated pulse counter stream directly to Home Assistant. In this mode, the integration will divide incoming state changes by your specified *Calibration Factor* (e.g., 450.0).

> **Deployment Warning:** Choosing `pulses` while targeting a sensor that already outputs calculated volume (Liters) will result in a **450x under-reporting error** in your analytics and statistics engines. Ensure your hardware tier output aligns with your software ingestion rules.

## HACS Installation Walk-through

1. Open your **Home Assistant** frontend.
2. Select **HACS** (Home Assistant Community Store) in the sidebar.
3. Click the three vertical dots in the top-right corner and select **Custom repositories**.
4. Paste the URL of this repository into the **Repository** input field.
5. In the **Category** dropdown, select **Integration**.
6. Click **Add** and verify "Smart Water Filter PRO" appears in the repository list.
7. Click the newly added card, then click **Download** in the bottom right.
8. **Restart Home Assistant** to load the custom component files.
9. Go to **Settings > Devices & Services > Add Integration**.
10. Search for **Smart Water Filter PRO** and follow the step-by-step setup configuration.

---

> **CRITICAL REPO GUARDRAIL**: EVERY subsequent codebase refinement, feature addition, bug mitigation, or hardware refactor MUST execute an atomic entry tracking the modification within CHANGELOG.md and immediately update or append the corresponding documentation file inside `docs/`. Any code commit pushed without synchronized documentation updates constitutes a critical deployment breaking failure.
