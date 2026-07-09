# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [5.0.0] - 2026-07-09
### Added
- **Multi-Stage Filtration Engine**: Refactored the core engine to support cascading filter stages. Exposes `smart_water_filter.add_filter_stage` and `smart_water_filter.remove_filter_stage` service actions.
- **Dynamic Entities**: Generated per-stage telemetry and controls (`sensor.{stage_id}_remaining_liters`, `sensor.{stage_id}_remaining_days`, `sensor.{stage_id}_health_score`, `binary_sensor.{stage_id}_replace_required`, `button.reset_{stage_id}`, `number.{stage_id}_capacity`, `number.{stage_id}_max_age`).
- **JSON Storage Migrations**: Added v4 to v5 storage migration converting the monolithic `"filter"` database namespace into the root-level list `"stages"` structure.
- **Translations with Placeholders**: Rewrote translation files supporting `{stage_name}` placeholders.

### Changed
- **Config Flow**: Stripped filter size and capacity inputs from initial configuration flow in favor of per-stage setup.
- **API Contracts**: Refactored `smart_water_filter.reset_filter` to require a `stage_id`.

## [4.3.1] - 2026-07-09
### Added
- **Production Baseline**: Initialized comprehensive documentation suite, HACS distribution constraints, and strict hardware/software integration specs.
- **Architectural Guardrails**: Locked in the evolution protocol requiring synchronized documentation updates for all subsequent commits.
- **Test Integrity**: Patched coordinator unit tests to ensure that mocked timestamps align and bypass date/hour rollovers cleanly.
