# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [5.0.0] - 2026-07-10
### Fixed
- **Sensor Timestamp Bug**: Converted `last_flow_time` from an ISO string to a proper native, timezone-aware Python `datetime` object in `coordinator.py` to prevent HA Timestamp sensor from showing as unavailable.
- **Leak Alarm Latching & Zero Flow**: Forced leak engine analysis update on zero flow and ensured immediate drop to zero flow clears pending continuous-flow timers (`micro_leak_start`, `high_leak_start`) in `leak_engine.py`.
- **Calibration Settings**: Configured 1L calibration defaults and lowered pulse delta validation threshold to `1.0` in `config_flow.py`.
- **Custom Stage Form**: Aligned `add_stage_custom` schema to combine inputs using float coercion.

### Changed
- **Stage Reset Options Flow**: Removed `SmartWaterStageButton` entity from `button.py` and moved filter resets to options flow step `reset_stage` in `config_flow.py` with dynamic translations.
- **Hardware Rebranding**: Rebranded "PRO Hardware Tier" references to "ESP32 Ultra-Flow Sentinel Node" across source code and markdown documentation.

## [5.0.1] - 2026-07-09
### Fixed
- **Direct Liters Flow Processing**: Fixed a critical bug in `coordinator.py` where `SOURCE_TYPE_LITERS` flow rate values (e.g. from ESPHome) were treated as cumulative pulse deltas. Now sets the flow rate directly bypassing the flow engine's cumulative logic.
- **Immediate Zero Flow Override**: Enforced immediate resetting of `current_flow_rate` and `flow_engine.current_flow_rate` to `0.0` when the direct liters sensor state drops to `0.0` or less, completely bypassing the EMA filter to prevent hanging and ghost flow rates.

## [5.0.0] - 2026-07-09
### Added
- **Multi-Stage Filtration Engine**: Refactored the core engine to support cascading filter stages. Exposes `smart_water_filter.add_filter_stage` and `smart_water_filter.remove_filter_stage` service actions.
- **Dynamic Entities**: Generated per-stage telemetry and controls (`sensor.{stage_id}_remaining_liters`, `sensor.{stage_id}_remaining_days`, `sensor.{stage_id}_health_score`, `binary_sensor.{stage_id}_replace_required`, `button.reset_{stage_id}`, `number.{stage_id}_capacity`, `number.{stage_id}_max_age`).
- **JSON Storage Migrations**: Added v4 to v5 storage migration converting the monolithic `"filter"` database namespace into the root-level list `"stages"` structure.
- **Translations with Placeholders**: Rewrote translation files supporting `{stage_name}` placeholders.
- **Unified Options Flow**: Created a dynamic multi-step options flow handler in `config_flow.py` supporting sensor setup, adding filter presets or custom stages, removing stages, and editing stage capacities/lifespans.

### Changed
- **Config Flow**: Stripped filter size and capacity inputs from initial configuration flow in favor of per-stage setup.
- **API Contracts**: Refactored `smart_water_filter.reset_filter` to require a `stage_id`.
- **Legacy UI Cleanup**: Removed legacy `select.py` and deleted control select entities. Set defaults directly from the options flow to simplify dashboard registry.

## [4.3.1] - 2026-07-09
### Added
- **Production Baseline**: Initialized comprehensive documentation suite, HACS distribution constraints, and strict hardware/software integration specs.
- **Architectural Guardrails**: Locked in the evolution protocol requiring synchronized documentation updates for all subsequent commits.
- **Test Integrity**: Patched coordinator unit tests to ensure that mocked timestamps align and bypass date/hour rollovers cleanly.
