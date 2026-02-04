# Shell Commands and CLI

This document describes the `optimasol` admin CLI (see `src/optimasol/cli.py`). It manages the service, database, and client provisioning.

**Service Lifecycle**
1. `optimasol start` - Starts the service in the background, writes the PID to `service.pid`, and appends logs to `service.log`.
2. `optimasol stop` - Sends `SIGTERM` to the service and removes the PID file.
3. `optimasol restart` - Stops then starts the service, useful after config changes.
4. `optimasol status` - Prints process status and basic DB connectivity checks.
5. `optimasol logs` - Prints recent logs. Use `-f` to follow or `-n` to change the number of lines.

**Maintenance**
1. `optimasol update` - Runs `git pull` in the project root and prints the result.
2. `optimasol db backup` - Copies the SQLite DB into `backups/` with a timestamp.

**Client Management**
1. `optimasol client ls` - Lists client IDs and drivers currently stored in the DB.
2. `optimasol client create <file>` - Creates a client from a JSON file.
3. `optimasol client rm <client_id>` - Deletes a client and its stored data.
4. `optimasol client show <client_id>` - Prints the JSON configuration stored in the DB.

The JSON file for `client create` must include `id`, `engine`, `weather`, and `driver` blocks. The driver payload uses a `type` (driver id, name, or numeric `DRIVER_TYPE_ID`) plus a `config` object. See `src/optimasol/drivers/README.md` for a concrete example.

**Provisioning**
1. `optimasol key gen <client_id>` - Generates a short activation key (ex: `OPT-ABCDE`) and stores it in the DB.

**Web UI**
1. `optimasol web` - Launches the web server with Uvicorn on port 8000.

**Other Entrypoints**
1. `optimasol-service` - Runs the service runner in the foreground (useful for containers).
2. `optimasol-web` - Launches the web server directly without the CLI wrapper.

**Shell Scripts**
Installer and uninstaller helpers live in `scripts/`. If you need to modify those workflows, start there.
