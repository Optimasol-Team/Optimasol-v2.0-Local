"""Default configuration values for the Optimasol application.

This module centralizes every configuration parameter that can be provided
externally to :func:`optimasol.main.main`.  Use :func:`get_default_config`
to obtain a fresh copy before applying user-supplied overrides.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

# Project location helpers (kept lightweight to avoid extra imports elsewhere).
PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent if PACKAGE_ROOT.parent.name != "src" else PACKAGE_ROOT.parent.parent

# Runtime paths (no config-file dependency).
RUNTIME_ROOT = PROJECT_ROOT if (PROJECT_ROOT / "pyproject.toml").exists() else Path.home() / ".optimasol"
DATA_DIR = RUNTIME_ROOT / "data"
LOG_FILE = RUNTIME_ROOT / "service.log"
PID_FILE = RUNTIME_ROOT / "service.pid"
BACKUPS_DIR = RUNTIME_ROOT / "backups"
DEFAULT_DB_PATH = DATA_DIR / "optimasol.db"


def ensure_runtime_dirs() -> None:
    """Create expected runtime directories."""
    for path in [RUNTIME_ROOT, DATA_DIR, BACKUPS_DIR, LOG_FILE.parent]:
        path.mkdir(parents=True, exist_ok=True)


# Base defaults derived from the former JSON files in the removed ``config`` directory.
DEFAULT_CONFIG = {
    "update_with_db": {"frequency": 2},
    "update_weather": {"frequency": 1},
    "chack_efficiency_pannels": {"frequency": 7},
    "min_distance": {"minimal_distance": 15},
    "optimizer_config": {"horizon": 24, "step_minutes": 15},
    "mqtt_config": {"host": "localhost", "port": 1883, "username": None, "password": None},
    "path_to_db": {
        "path_to_db": str(
            PROJECT_ROOT
            / "tests"
            / "test_db.db"
        )
    },
}


def get_default_config() -> dict:
    """Return a deep copy of the default configuration mapping."""
    return deepcopy(DEFAULT_CONFIG)


def resolve_config(config: dict) -> dict:
    """Validate and normalize external configuration.

    The function enforces the global fallback rule:
    if ``config`` is falsy or any access/conversion fails, the full default
    configuration is returned.

    Args:
        config: Configuration mapping provided by the caller.

    Returns:
        dict: A normalized configuration mapping.
    """
    base = get_default_config()
    if not config:
        return base

    try:
        freq_sync_db = float(config["update_with_db"]["frequency"])
        freq_weather = float(config["update_weather"]["frequency"])
        freq_efficiency = float(config["chack_efficiency_pannels"]["frequency"])
        minimal_distance = float(config["min_distance"]["minimal_distance"])

        horizon = int(config["optimizer_config"]["horizon"])
        step_minutes = int(config["optimizer_config"]["step_minutes"])

        mqtt_host = str(config["mqtt_config"]["host"])
        mqtt_port = int(config["mqtt_config"]["port"])
        mqtt_username = config["mqtt_config"].get("username")
        mqtt_password = config["mqtt_config"].get("password")

        path_db_raw = str(config["path_to_db"]["path_to_db"])
    except Exception:
        return base

    base["update_with_db"]["frequency"] = freq_sync_db
    base["update_weather"]["frequency"] = freq_weather
    base["chack_efficiency_pannels"]["frequency"] = freq_efficiency
    base["min_distance"]["minimal_distance"] = minimal_distance
    base["optimizer_config"]["horizon"] = horizon
    base["optimizer_config"]["step_minutes"] = step_minutes
    base["mqtt_config"]["host"] = mqtt_host
    base["mqtt_config"]["port"] = mqtt_port
    base["mqtt_config"]["username"] = mqtt_username
    base["mqtt_config"]["password"] = mqtt_password
    base["path_to_db"]["path_to_db"] = path_db_raw
    return base
