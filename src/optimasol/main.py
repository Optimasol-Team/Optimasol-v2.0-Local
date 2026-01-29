import json
import logging
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

import pandas as pd

from .core.client_model import Client
from .database import DBManager
from .paths import CONFIG_DIR, LOG_FILE, RUNTIME_ROOT, ensure_runtime_dirs
from weather_manager.evaluation import ForecastEvaluator


# Dossiers et constantes de configuration
WEATHER_CONFIG = CONFIG_DIR / "update_weather.json"
DB_SYNC_CONFIG = CONFIG_DIR / "update_with_db.json"
EFFICIENCY_CONFIG_PRIMARY = CONFIG_DIR / "chack_efficiency_pannels.json"
EFFICIENCY_CONFIG_FALLBACK = CONFIG_DIR / "check_efficiency_pannels.json"
DB_PATH_CONFIG = CONFIG_DIR / "path_to_db.json"

logger = logging.getLogger("optimasol.main")


class _LoggerWriter:
    """Redirects stdout/stderr to the logging system."""

    def __init__(self, log_function: Callable[[str], None]):
        self.log_function = log_function
        self._buffer = ""
        self.encoding = "utf-8"

    def write(self, message: str) -> None:
        if not message:
            return
        self._buffer += message
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            line = line.rstrip("\r")
            if line:
                self.log_function(line)

    def flush(self) -> None:
        if self._buffer:
            line = self._buffer.rstrip("\r\n")
            if line:
                self.log_function(line)
            self._buffer = ""

    def isatty(self) -> bool:
        return False

    def writable(self) -> bool:
        return True

    def writelines(self, lines) -> None:
        for line in lines:
            self.write(line)


def _configure_logging() -> logging.Logger:
    if getattr(_configure_logging, "_configured", False):
        return logger

    ensure_runtime_dirs()
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(threadName)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler(sys.__stdout__)
    console_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    logging.captureWarnings(True)

    sys.stdout = _LoggerWriter(root_logger.info)
    sys.stderr = _LoggerWriter(root_logger.error)

    def _handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            root_logger.info("Interruption clavier détectée, arrêt demandé.")
            return
        root_logger.error(
            "Exception non gérée",
            exc_info=(exc_type, exc_value, exc_traceback),
        )

    def _handle_thread_exception(args):
        if issubclass(args.exc_type, KeyboardInterrupt):
            return
        root_logger.error(
            "Exception non gérée dans le thread %s",
            args.thread.name,
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    sys.excepthook = _handle_exception
    threading.excepthook = _handle_thread_exception

    _configure_logging._configured = True
    logger.info("Journalisation initialisée (fichier=%s).", LOG_FILE)
    return logger


def _load_config_value(path: Path, key: str, default: float) -> float:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        value = data.get(key, default)
        if isinstance(value, (int, float)) and value > 0:
            return float(value)
    except Exception as exc:
        logger.warning("[Config] Lecture impossible pour %s: %s", path.name, exc)
    return float(default)


def _load_interval_seconds(path: Path, key: str, default: float, unit_seconds: float) -> float:
    return _load_config_value(path, key, default) * unit_seconds


def _load_db_path() -> Optional[Path]:
    try:
        with open(DB_PATH_CONFIG, "r", encoding="utf-8") as f:
            raw = json.load(f).get("path_to_db")
        if not raw or not isinstance(raw, str) or raw.strip() == "" or "..." in raw:
            return None
        db_path = Path(raw).expanduser()
        if not db_path.is_absolute():
            db_path = (RUNTIME_ROOT / raw).resolve()
        return db_path
    except Exception as exc:
        logger.warning(
            "[Config] Impossible de charger le chemin BDD (%s), utilisation du chemin par defaut.",
            exc,
        )
        return None


def _spawn_periodic_task(
    name: str,
    interval_seconds: float,
    stopper: threading.Event,
    func: Callable[[], None],
) -> threading.Thread:
    def _runner():
        while not stopper.is_set():
            start = time.monotonic()
            try:
                func()
            except Exception as exc:
                logger.exception("[%s] Erreur: %s", name, exc)
            elapsed = time.monotonic() - start
            wait_time = max(interval_seconds - elapsed, 0)
            stopper.wait(wait_time)

    thread = threading.Thread(target=_runner, name=name, daemon=True)
    thread.start()
    return thread


def _start_drivers(all_clients):
    for client in all_clients.list_of_clients:
        try:
            client.driver.start()
        except Exception as exc:
            logger.exception(
                "[Startup] Echec demarrage driver pour client %s: %s",
                client.client_id,
                exc,
            )


def _nearest_forecast_point(df: pd.DataFrame) -> Optional[tuple[datetime, float]]:
    if df is None or df.empty or "production" not in df.columns or "Datetime" not in df.columns:
        return None
    try:
        timestamps = pd.to_datetime(df["Datetime"], utc=True)
    except Exception:
        return None

    working_df = df.copy()
    working_df["_dt"] = timestamps
    ref_time = pd.Timestamp.now(tz=timezone.utc)
    working_df["_diff"] = (working_df["_dt"] - ref_time).abs()
    nearest_idx = working_df["_diff"].idxmin()
    nearest_row = working_df.loc[nearest_idx]
    return nearest_row["_dt"].to_pydatetime(), float(nearest_row["production"])


def _push_latest_forecasts(all_clients, db_manager: DBManager):
    for client in all_clients.list_of_clients:
        point = _nearest_forecast_point(getattr(client, "production_forecast", None))
        if point is None:
            continue
        ts, production = point
        try:
            db_manager.report_production_forecast(client.client_id, production, ts)
        except Exception as exc:
            logger.exception(
                "[Meteo] Echec enregistrement forecast pour %s: %s",
                client.client_id,
                exc,
            )


def _process_clients(all_clients):
    for client in all_clients.list_of_clients:
        try:
            client.process()
        except Exception as exc:
            logger.exception("[Process] Echec pour le client %s: %s", client.client_id, exc)


def _sync_db(all_clients, db_manager: DBManager):
    try:
        db_manager.update_db_service(all_clients)
    except Exception as exc:
        logger.exception("[BDD] Sync echec: %s", exc)


def _refresh_weather(all_clients, db_manager: DBManager):
    try:
        all_clients.update_weather()
        _push_latest_forecasts(all_clients, db_manager)
    except Exception as exc:
        logger.exception("[Meteo] Mise a jour echec: %s", exc)


def _prepare_df_from_db(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["Datetime", "production"])
    prepared = df.rename(columns={"timestamp": "Datetime"})
    if "Datetime" not in prepared.columns or "production" not in prepared.columns:
        return pd.DataFrame(columns=["Datetime", "production"])
    prepared = prepared[["Datetime", "production"]].copy()
    prepared["Datetime"] = pd.to_datetime(prepared["Datetime"], utc=True)
    return prepared


def _get_installation(client) -> Optional[object]:
    weather_obj = getattr(client, "client_weather", None)
    if weather_obj is None:
        return None
    return getattr(weather_obj, "installation", getattr(weather_obj, "installation_PV", None))


def _update_efficiency(all_clients, db_manager: DBManager):
    for client in all_clients.list_of_clients:
        df_measured = _prepare_df_from_db(db_manager.get_productions_measured(client.client_id))
        df_forecasts = _prepare_df_from_db(db_manager.get_productions_forecasts(client.client_id))
        if df_measured.empty or df_forecasts.empty:
            continue
        try:
            evaluator = ForecastEvaluator(df_forecasts, df_measured)
            coefficient = evaluator.correction_coefficient()
        except Exception as exc:
            logger.exception("[Rendement] Evaluation impossible pour %s: %s", client.client_id, exc)
            continue
        if coefficient <= 0:
            continue

        installation = _get_installation(client)
        if installation is None or installation.rendement_global is None:
            continue

        new_rendement = installation.rendement_global * coefficient
        new_rendement = max(min(new_rendement, 1.0), 1e-6)
        try:
            installation.rendement_global = new_rendement
            db_manager.update_table_client_ui(client)
        except Exception as exc:
            logger.exception("[Rendement] Mise a jour impossible pour %s: %s", client.client_id, exc)


def main():
    _configure_logging()
    logger.info("Demarrage du service Optimasol.")

    db_path = _load_db_path()
    db_manager = DBManager(db_path)
    logger.info("BDD initialisee (path=%s)", db_manager.path)
    all_clients = db_manager.get_all_clients_engine()
    logger.info("Clients charges: %s", len(all_clients.list_of_clients))

    _start_drivers(all_clients)
    logger.info("Drivers demarres.")

    # Initialisation des premieres donnees meteo pour debloquer le process()
    _refresh_weather(all_clients, db_manager)
    logger.info("Premiere mise a jour meteo effectuee.")

    # Chargement des frequences
    weather_interval = _load_interval_seconds(WEATHER_CONFIG, "frequency", 1, 3600)
    db_sync_interval = _load_interval_seconds(DB_SYNC_CONFIG, "frequency", 2, 60)
    efficiency_file = EFFICIENCY_CONFIG_PRIMARY if EFFICIENCY_CONFIG_PRIMARY.exists() else EFFICIENCY_CONFIG_FALLBACK
    efficiency_interval = _load_interval_seconds(efficiency_file, "frequency", 7, 24 * 3600)
    process_interval = max(float(Client.STEP_MINUTES) * 60, 1.0)

    stopper = threading.Event()
    threads: list[threading.Thread] = []
    try:
        threads = [
            _spawn_periodic_task("ProcessClients", process_interval, stopper, lambda: _process_clients(all_clients)),
            _spawn_periodic_task("WeatherUpdater", weather_interval, stopper, lambda: _refresh_weather(all_clients, db_manager)),
            _spawn_periodic_task("DBSync", db_sync_interval, stopper, lambda: _sync_db(all_clients, db_manager)),
            _spawn_periodic_task("EfficiencyUpdater", efficiency_interval, stopper, lambda: _update_efficiency(all_clients, db_manager)),
        ]
        logger.info(
            "Taches periodiques lancees (process=%.1fs, meteo=%.1fs, bdd=%.1fs, rendement=%.1fs).",
            process_interval,
            weather_interval,
            db_sync_interval,
            efficiency_interval,
        )
        while not stopper.is_set():
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Interruption clavier recue, fermeture en cours.")
    except Exception as exc:
        logger.exception("Erreur critique dans main(): %s", exc)
    finally:
        stopper.set()
        for thread in threads:
            try:
                thread.join(timeout=5)
            except Exception as join_exc:
                logger.exception("Erreur lors de l'arret du thread %s: %s", thread.name, join_exc)
        logger.info("Service arrete proprement.")


if __name__ == "__main__":
    main()
