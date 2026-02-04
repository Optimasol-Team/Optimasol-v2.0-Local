# Drivers

Drivers are the interface between Optimasol and physical devices (routers, meters, sensors). They are responsible for device communication, telemetry ingestion, and applying optimization decisions.

**Responsibilities**
- Establish device communication in `start` and keep it running.
- Emit telemetry by calling the registered callbacks: `on_receive_temperature`, `on_receive_production`, `on_receive_power`.
- Apply optimization decisions in `send_decision` (units and interpretation are driver-specific).
- Provide UI metadata and configuration schema via `get_driver_def`.
- Serialize and restore configuration with `device_to_dict` and `dict_to_device`.

**Where Drivers Live**
- `src/optimasol/drivers/base_driver.py` defines the abstract contract.
- Each driver lives in its own package under `src/optimasol/drivers/<driver_name>/`.
- `src/optimasol/drivers/__init__.py` registers drivers in `ALL_DRIVERS`.

**Adding a New Driver**
1. Create a new package folder (for example `src/optimasol/drivers/my_driver/`).
2. Implement a class that inherits `BaseDriver` and set a unique `DRIVER_TYPE_ID`.
3. Implement the required methods: `get_driver_def`, `start`, `send_decision`, `device_to_dict`, and `dict_to_device`.
4. Define the UI form fields in `get_driver_def()["form_schema"]`. The keys in this schema are passed as `**kwargs` to `__init__`.
5. Import and add the driver class to `ALL_DRIVERS` in `src/optimasol/drivers/__init__.py` so the CLI and UI can resolve it.
6. If the driver ships assets (icons, templates), include them in `pyproject.toml` under `[tool.setuptools.package-data]` so they are packaged.

**Driver Config Payload (CLI)**
`optimasol client create <file>` expects a JSON payload with `id`, `engine`, `weather`, and `driver` blocks. The driver block accepts `type` (driver id, name, or numeric `DRIVER_TYPE_ID`) plus a `config` object that maps to `__init__`.

```json
{
  "id": 123,
  "engine": { "...": "..." },
  "weather": { "...": "..." },
  "driver": {
    "type": "smart_electromation_mqtt",
    "config": {
      "serial_number": "PVROUTER001"
    }
  }
}
```

**Implementation Tips**
1. Keep `device_to_dict` minimal and stable, because it is stored in the DB.
2. Make `dict_to_device` the inverse of `device_to_dict`.
3. Validate configuration in `__init__` and fail fast if required fields are missing.
