# Optimasol

Optimasol is a 24/7 service and admin toolkit that manages photovoltaic (PV) routing for client installations. It coordinates device drivers, weather forecasts, and an optimization engine to compute decisions, collect telemetry, and keep client configuration in sync with the database.

The project ships as:
- A long-running service used in production.
- An admin CLI for service control, provisioning, and DB maintenance.
- A lightweight web UI entrypoint for provisioning.

**Key Dependencies (GitHub)**
- [pandas](https://github.com/pandas-dev/pandas) - Time-series data handling for forecasts and measurements.
- [paho-mqtt](https://github.com/eclipse/paho.mqtt.python) - MQTT client used by device drivers.
- [Werkzeug](https://github.com/pallets/werkzeug) - WSGI utilities used by the web server.
- [Optimiser Engine v2](https://github.com/Optimasol-Team/Optimiser_Engine-v2.0) - Core optimization logic.
- [Optimasol Weather](https://github.com/Optimasol-Team/Optimasol-Weather) - Forecast ingestion and PV production modeling.

**Where To Look Next**
- `docs/script_description.md` - End-to-end service flow, startup sequence, and periodic tasks.
- `docs/commandes_shell.md` - CLI commands, service management, backups, and web UI entrypoint.
- `src/optimasol/drivers/README.md` - Driver contract and how to add or modify drivers.

If you need to adjust runtime settings, start with `config.json`.
