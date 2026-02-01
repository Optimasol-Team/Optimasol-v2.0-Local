from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from .config_loader import load_config_file
from .database import DBManager
from .default import BACKUPS_DIR, LOG_FILE, PID_FILE, PROJECT_ROOT, ensure_runtime_dirs
from .logging_setup import setup_logging
from .core import AllClients, Client
from .drivers import ALL_DRIVERS

logger = logging.getLogger(__name__)


# ---------- Helpers ----------

def _read_pid() -> int | None:
    if not PID_FILE.exists():
        return None
    try:
        return int(PID_FILE.read_text().strip())
    except Exception:
        return None


def _is_process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _resolve_db_path(config: dict) -> Path:
    path_cfg = config.get("path_to_db", {})
    raw = path_cfg.get("path_to_db") if isinstance(path_cfg, dict) else None
    if not raw:
        from .default import DEFAULT_DB_PATH
        return DEFAULT_DB_PATH
    path = Path(str(raw)).expanduser()
    if not path.is_absolute():
        path = (PROJECT_ROOT / path).resolve()
    return path


def _load_db_manager(config: dict) -> DBManager:
    path_db = _resolve_db_path(config)
    return DBManager(path_db)


def _ensure_activation_table(db: DBManager) -> None:
    """Ensure activation_keys exists without FK (allows pre-provisioned clients)."""
    create_sql = """
    CREATE TABLE IF NOT EXISTS activation_keys (
        activation_key TEXT PRIMARY KEY,
        client_id      INTEGER NOT NULL,
        status         TEXT DEFAULT 'issued',
        created_at     TEXT NOT NULL,
        expires_at     TEXT,
        used_at        TEXT
    );
    """
    db.execute_commit(create_sql, ())

    # If legacy table had FK, rebuild it without FK to allow keys before client exists.
    fk_rows = db.execute_query("PRAGMA foreign_key_list('activation_keys')")
    if fk_rows:
        db.execute_commit(
            """
            CREATE TABLE IF NOT EXISTS activation_keys_new (
                activation_key TEXT PRIMARY KEY,
                client_id      INTEGER NOT NULL,
                status         TEXT DEFAULT 'issued',
                created_at     TEXT NOT NULL,
                expires_at     TEXT,
                used_at        TEXT
            );
            """,
            (),
        )
        db.execute_commit(
            """
            INSERT OR IGNORE INTO activation_keys_new
            (activation_key, client_id, status, created_at, expires_at, used_at)
            SELECT activation_key, client_id, status, created_at, expires_at, used_at
            FROM activation_keys;
            """,
            (),
        )
        db.execute_commit("DROP TABLE activation_keys;", ())
        db.execute_commit("ALTER TABLE activation_keys_new RENAME TO activation_keys;", ())


def _short_key() -> str:
    import secrets
    import string

    alphabet = string.ascii_uppercase + string.digits
    return "OPT-" + "".join(secrets.choice(alphabet) for _ in range(5))


def _driver_from_payload(payload: Dict[str, Any]):
    driver_type = payload.get("type") or payload.get("id") or payload.get("name")
    if not driver_type:
        raise ValueError("driver.type manquant dans le fichier JSON")

    mapping = {}
    for drv in ALL_DRIVERS:
        try:
            definition = drv.get_driver_def()
            identifier = definition.get("id") or definition.get("name") or drv.__name__
        except Exception:
            identifier = drv.__name__
        mapping[identifier] = drv
        if hasattr(drv, "DRIVER_TYPE_ID"):
            mapping[str(getattr(drv, "DRIVER_TYPE_ID"))] = drv

    drv_cls = mapping.get(driver_type)
    if drv_cls is None:
        raise ValueError(f"Driver inconnu: {driver_type}")

    drv_conf = payload.get("config") or {}
    return drv_cls.dict_to_device(drv_conf)


def _build_client_from_json(raw: Dict[str, Any]) -> Client:
    try:
        from optimiser_engine import Client as EngineClient
        from weather_manager import Client as WeatherClient
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("optimiser_engine ou weather_manager manquant dans l'environnement") from exc

    client_id = int(raw["id"])
    engine_cfg = raw.get("engine") or {}
    weather_cfg = raw.get("weather") or {}
    driver_cfg = raw.get("driver") or {}

    engine = EngineClient.from_dict(engine_cfg)
    engine.client_id = client_id
    weather = WeatherClient.from_dict(weather_cfg)
    weather.client_id = client_id
    driver = _driver_from_payload(driver_cfg)

    return Client(client_id=client_id, client_engine=engine, client_weather=weather, driver=driver)


# ---------- Command implementations ----------

def cmd_start(args, config):
    ensure_runtime_dirs()
    pid = _read_pid()
    if pid and _is_process_alive(pid):
        print(f"Service déjà actif (pid={pid})")
        return

    log_fh = open(LOG_FILE, "a", encoding="utf-8")
    cmd = [sys.executable, "-m", "optimasol.service_runner"]
    proc = subprocess.Popen(cmd, stdout=log_fh, stderr=log_fh, cwd=PROJECT_ROOT)
    PID_FILE.write_text(str(proc.pid))
    logger.info("Service démarré (pid=%s)", proc.pid)
    print(f"Service démarré (pid={proc.pid})")


def cmd_stop(args, config):
    pid = _read_pid()
    if not pid:
        print("Service non démarré")
        return

    try:
        os.kill(pid, signal.SIGTERM)
        logger.info("Signal SIGTERM envoyé au service (pid=%s)", pid)
    except ProcessLookupError:
        print("Processus introuvable, suppression du pidfile")
    PID_FILE.unlink(missing_ok=True)
    print("Service arrêté")


def cmd_restart(args, config):
    cmd_stop(args, config)
    time.sleep(1)
    cmd_start(args, config)


def cmd_status(args, config):
    pid = _read_pid()
    alive = pid and _is_process_alive(pid)
    db = _load_db_manager(config)
    db_ok = True
    try:
        db.execute_query("SELECT 1")
    except Exception:
        db_ok = False
    print(f"Processus : {'Actif' if alive else 'Inactif'} (pid={pid or '-'})")
    print(f"Connexion BDD : {'OK' if db_ok else 'Échec'}")


def cmd_logs(args, config):
    path = LOG_FILE
    if not path.exists():
        print("Aucun log pour le moment.")
        return
    if args.follow:
        print(f"--- follow {path} ---")
        with path.open() as f:
            f.seek(0, os.SEEK_END)
            while True:
                line = f.readline()
                if not line:
                    time.sleep(0.5)
                    continue
                sys.stdout.write(line)
                sys.stdout.flush()
    else:
        with path.open() as f:
            lines = f.readlines()[-args.lines :]
        for l in lines:
            sys.stdout.write(l)


def cmd_update(args, config):
    res = subprocess.run(["git", "-C", str(PROJECT_ROOT), "pull"], capture_output=True, text=True)
    logger.info("Mise à jour git exécutée (rc=%s)", res.returncode)
    sys.stdout.write(res.stdout)
    sys.stderr.write(res.stderr)


def cmd_db_backup(args, config):
    ensure_runtime_dirs()
    path_db = _resolve_db_path(config)
    ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    dest = BACKUPS_DIR / f"backup-{ts}.db"
    shutil.copy2(path_db, dest)
    logger.info("Backup DB créé: %s", dest)
    print(f"Backup créé: {dest}")


def cmd_client_ls(args, config):
    db = _load_db_manager(config)
    all_clients = db.client_manager.get_all_clients()
    print("ID | Driver | Statut")
    for clt in all_clients.list_of_clients:
        driver_name = clt.driver.__class__.__name__
        print(f"{clt.client_id} | {driver_name} | OK")


def cmd_client_show(args, config):
    db = _load_db_manager(config)
    cid = int(args.client_id)
    rows = db.execute_query("SELECT id, config_engine, config_weather, driver_id, config_driver FROM users_main WHERE id = ?", (cid,))
    if not rows:
        print("Client introuvable")
        return
    row = rows[0]
    payload = {
        "id": row[0],
        "engine": json.loads(row[1]) if row[1] else {},
        "weather": json.loads(row[2]) if row[2] else {},
        "driver_id": row[3],
        "driver_config": json.loads(row[4]) if row[4] else {},
    }
    print(json.dumps(payload, indent=2))


def cmd_client_rm(args, config):
    db = _load_db_manager(config)
    cid = int(args.client_id)
    db.execute_commit("DELETE FROM users_main WHERE id = ?", (cid,))
    logger.info("Client %s supprimé", cid)
    print(f"Client {cid} supprimé (données associées en cascade)")


def cmd_client_create(args, config):
    db = _load_db_manager(config)
    file_path = Path(args.file)
    if not file_path.exists():
        print(f"Fichier introuvable: {file_path}")
        return
    try:
        raw = json.loads(file_path.read_text())
    except Exception as exc:  # noqa: BLE001
        print(f"JSON invalide: {exc}")
        return

    try:
        new_client = _build_client_from_json(raw)
    except Exception as exc:  # noqa: BLE001
        logger.error("Échec création client depuis %s: %s", file_path, exc, exc_info=True)
        print(f"Erreur: {exc}")
        return

    all_clients = db.client_manager.get_all_clients()
    try:
        all_clients.add(new_client)
    except Exception as exc:  # noqa: BLE001
        print(f"Impossible d'ajouter le client: {exc}")
        return
    db.client_manager.store_all_clients(all_clients)
    logger.info("Client %s ajouté via CLI", new_client.client_id)
    print(f"Client {new_client.client_id} ajouté")


def cmd_key_gen(args, config):
    db = _load_db_manager(config)
    _ensure_activation_table(db)
    cid = int(args.client_id)
    key = _short_key()
    ts = datetime.utcnow().isoformat()
    db.execute_commit(
        "INSERT OR REPLACE INTO activation_keys (activation_key, client_id, status, created_at) VALUES (?, ?, 'issued', ?)",
        (key, cid, ts),
    )
    logger.info("Clé générée pour client %s: %s", cid, key)
    print(key)


# ---------- Argument parser ----------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="optimasol", description="CLI administrateur Optimasol")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("start")
    sub.add_parser("stop")
    sub.add_parser("restart")
    sub.add_parser("status")

    p_logs = sub.add_parser("logs")
    p_logs.add_argument("-f", "--follow", action="store_true", help="Suivi en direct (tail -f)")
    p_logs.add_argument("-n", "--lines", type=int, default=50, help="Nombre de lignes à afficher")

    sub.add_parser("update")

    p_db = sub.add_parser("db")
    db_sub = p_db.add_subparsers(dest="db_cmd", required=True)
    db_sub.add_parser("backup")

    p_client = sub.add_parser("client")
    csub = p_client.add_subparsers(dest="client_cmd", required=True)
    csub.add_parser("ls")

    p_create = csub.add_parser("create")
    p_create.add_argument("file", help="Fichier JSON décrivant le client")

    p_rm = csub.add_parser("rm")
    p_rm.add_argument("client_id")

    p_show = csub.add_parser("show")
    p_show.add_argument("client_id")

    p_key = sub.add_parser("key")
    ksub = p_key.add_subparsers(dest="key_cmd", required=True)
    p_key_gen = ksub.add_parser("gen")
    p_key_gen.add_argument("client_id")

    return parser


def main(argv: list[str] | None = None) -> None:
    setup_logging()
    config = load_config_file()

    parser = build_parser()
    args = parser.parse_args(argv)

    dispatch = {
        "start": cmd_start,
        "stop": cmd_stop,
        "restart": cmd_restart,
        "status": cmd_status,
        "logs": cmd_logs,
        "update": cmd_update,
        "db": lambda a, c: cmd_db_backup(a, c) if a.db_cmd == "backup" else None,
        "client": {
            "ls": cmd_client_ls,
            "create": cmd_client_create,
            "rm": cmd_client_rm,
            "show": cmd_client_show,
        },
        "key": {"gen": cmd_key_gen},
    }

    if args.command == "client":
        cmd = dispatch["client"][args.client_cmd]
        cmd(args, config)
    elif args.command == "key":
        cmd = dispatch["key"][args.key_cmd]
        cmd(args, config)
    elif args.command == "db":
        cmd_db_backup(args, config)
    else:
        cmd = dispatch[args.command]
        cmd(args, config)


if __name__ == "__main__":  # pragma: no cover
    main()
