from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
import logging

from .core import AllClients
from .default import DEFAULT_DB_PATH, PROJECT_ROOT, ensure_runtime_dirs, resolve_config
from .logging_setup import setup_logging

# Emplacement de secours si la base configurée n'est pas accessible.
FALLBACK_DB_PATH = PROJECT_ROOT / "fallback_optimasol.db"


def _coerce_db_path(raw_path: str) -> Path:
    """Transforme un chemin éventuellement relatif en chemin absolu."""
    candidate = Path(raw_path).expanduser()
    if not candidate.is_absolute():
        candidate = (PROJECT_ROOT / raw_path).resolve()
    return candidate


def _resolve_db_path(config: dict) -> Path:
    """Choisit le chemin de BDD à partir du contexte courant ou du défaut."""
    ensure_runtime_dirs()
    path_cfg = config.get("path_to_db", {})
    raw_path = path_cfg.get("path_to_db") if isinstance(path_cfg, dict) else None
    if not raw_path:
        return DEFAULT_DB_PATH
    try:
        return _coerce_db_path(str(raw_path))
    except Exception:
        return DEFAULT_DB_PATH


def _build_db_manager(path_db: Path):
    """Instancie DBManager avec repli automatique sur la BDD de secours."""
    from .database import DBManager

    try:
        return DBManager(path_db), path_db
    except Exception:
        fallback = FALLBACK_DB_PATH
        fallback.parent.mkdir(parents=True, exist_ok=True)
        return DBManager(fallback), fallback


def _apply_runtime_config(config: dict):
    """Propagate configuration to dependent modules that expect static values."""
    from .core import Client
    from .drivers import SmartEMDriver

    optimizer_cfg = config["optimizer_config"]
    Client.CONFIG_OPTIMISATION = optimizer_cfg
    Client.HORIZON_HOURS = int(optimizer_cfg["horizon"])
    Client.STEP_MINUTES = int(optimizer_cfg["step_minutes"])

    AllClients.MINIMAL_DISTANCE = float(config["min_distance"]["minimal_distance"])

    SmartEMDriver.CONFIG_MQTT = {
        "host": config["mqtt_config"]["host"],
        "port": int(config["mqtt_config"]["port"]),
    }


def main(config: dict) -> None:
    """Entry point. Expects a configuration dictionary already loaded from JSON."""
    setup_logging()
    resolved_config = resolve_config(config)
    logger = logging.getLogger(__name__)
    logger.info("Configuration chargée et normalisée")

    from .core import AllClients, Client
    from .tasks import correct_efficiency, reports_data, update_weather

    _apply_runtime_config(resolved_config)

    path_db = _resolve_db_path(resolved_config)
    db_manager, path_db = _build_db_manager(path_db)
    logger.info("Base de données initialisée à %s", path_db)

    all_clients = db_manager.client_manager.get_all_clients()
    logger.info("Clients chargés: %d", len(all_clients.list_of_clients))

    for client in all_clients.list_of_clients:
        client.driver.start()
    logger.info("Drivers lancés pour tous les clients")

    freq_weather_s = resolved_config["update_weather"]["frequency"] * 3600
    freq_sync_db_s = resolved_config["update_with_db"]["frequency"] * 60
    freq_eff_s = resolved_config["chack_efficiency_pannels"]["frequency"] * 24 * 3600
    step_process_s = Client.STEP_MINUTES * 60

    now = datetime.now(timezone.utc)
    next_process = now
    next_weather = now
    next_sync_db = now
    next_efficiency = now

    logger.info("Boucle principale démarrée (tâches périodiques)")
    while True:
        now = datetime.now(timezone.utc)

        if now >= next_process:
            for client in all_clients.list_of_clients:
                client.process()
            next_process = now + timedelta(seconds=step_process_s)
            logger.info("Traitement optimisation effectué pour tous les clients")

        if now >= next_weather:
            update_weather(all_clients, db_manager)
            next_weather = now + timedelta(seconds=freq_weather_s)
            logger.info("Mise à jour météo déclenchée")

        if now >= next_sync_db:
            reports_data(all_clients, db_manager)
            db_manager.update_db_service(all_clients)
            next_sync_db = now + timedelta(seconds=freq_sync_db_s)
            logger.info("Synchronisation BDD terminée")

        if now >= next_efficiency:
            correct_efficiency(all_clients, db_manager)
            next_efficiency = now + timedelta(seconds=freq_eff_s)
            logger.info("Correction de rendement effectuée")

        time.sleep(1)
