# Service Flow Overview

This document describes the high-level flow of the Optimasol service as implemented in `src/optimasol/main.py` and `src/optimasol/tasks.py`.

**Startup Sequence**
1. Load and normalize configuration via `src/optimasol/config_loader.py` (defaults in `src/optimasol/default.py`). The default config file is `config.json` at the project root.
2. Resolve the database path from `config["path_to_db"]["path_to_db"]`. If the path is missing or invalid, the service falls back to a local `fallback_optimasol.db`.
3. Instantiate the `DBManager` and load the full `AllClients` collection from the database.
4. Apply runtime configuration to the core modules (optimizer horizon/step, minimum distance rules, MQTT settings).
5. Start every client driver with `client.driver.start()` so devices begin emitting telemetry.
6. Compute the scheduling intervals (process step, weather refresh, DB sync, efficiency correction) and enter the main loop.

**Periodic Tasks**
1. Optimization step (`client.process`) runs every `optimizer_config.step_minutes`.
2. Weather + production updates run every `update_weather.frequency` hours.
3. DB sync runs every `update_with_db.frequency` minutes.
4. Efficiency correction runs every `chack_efficiency_pannels.frequency` days.

**Task Details**
1. Optimization step
The service iterates over `all_clients.list_of_clients` and calls `client.process()` to compute the next decision for each client.
2. Weather update
`all_clients.update_forecasts()` pulls fresh forecasts. Then each client receives an updated PV production curve. The closest forecast point to the current UTC time is stored in the DB via `report_production_forecast`.
3. DB sync
`reports_data` writes the latest temperature, power, and production measurements to the database. Then `db_manager.update_db_service(all_clients)` persists any configuration changes back to SQL.
4. Efficiency correction
For clients with auto-correction enabled, the service compares measured vs forecast production, computes a correction coefficient, and updates `client.client_weather.installation.rendement_global`.

**Data Flow Notes**
1. Drivers push telemetry through callbacks (`on_receive_temperature`, `on_receive_production`, `on_receive_power`) which update each client state.
2. The DB reporter reads the latest in-memory values and persists them during the sync task.

If you need to dive into implementation details, start with `src/optimasol/main.py` and `src/optimasol/tasks.py`.
