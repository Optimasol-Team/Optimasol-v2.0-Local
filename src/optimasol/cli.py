import argparse
import json
import os
import random
import signal
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from getpass import getpass
from pathlib import Path
from typing import Optional

from .paths import (
    BACKUPS_DIR,
    CONFIG_DIR,
    DATA_DIR,
    DEFAULT_DB_PATH,
    LOG_FILE,
    PID_FILE,
    PROJECT_ROOT,
    RUNTIME_ROOT,
    ensure_runtime_dirs,
)


def _resolve_db_path() -> Path:
    """Align with main.py logic to find the configured DB path."""
    candidate = DEFAULT_DB_PATH
    cfg_path = CONFIG_DIR / "path_to_db.json"
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            raw = json.load(f).get("path_to_db")
        if raw and isinstance(raw, str) and raw.strip() and "..." not in raw:
            db_path = Path(raw).expanduser()
            if not db_path.is_absolute():
                db_path = (RUNTIME_ROOT / raw).resolve()
            candidate = db_path
    except FileNotFoundError:
        pass
    except Exception:
        pass
    return candidate


def _read_pid() -> Optional[int]:
    try:
        return int(PID_FILE.read_text().strip())
    except Exception:
        return None


def _is_process_running(pid: Optional[int]) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _build_env_with_src() -> dict:
    """Ensure `src/` is on PYTHONPATH when running from the source tree."""
    env = os.environ.copy()
    src_dir = PROJECT_ROOT / "src"
    if src_dir.exists():
        src_path = str(src_dir)
        current = env.get("PYTHONPATH", "")
        paths = [p for p in current.split(os.pathsep) if p]
        if src_path not in paths:
            paths.insert(0, src_path)
            env["PYTHONPATH"] = os.pathsep.join(paths)
    return env


def cmd_start(_: argparse.Namespace) -> int:
    ensure_runtime_dirs()
    pid = _read_pid()
    if _is_process_running(pid):
        print(f"Le service tourne déjà (PID {pid}).")
        return 0

    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOG_FILE.touch(exist_ok=True)
    log_fh = None
    try:
        log_fh = open(LOG_FILE, "a", encoding="utf-8")
        process = subprocess.Popen(
            [sys.executable, "-m", "optimasol.main"],
            stdout=log_fh,
            stderr=log_fh,
            cwd=str(RUNTIME_ROOT),
            env=_build_env_with_src(),
        )
        PID_FILE.write_text(str(process.pid), encoding="utf-8")
        print(f"Service démarré en arrière-plan (PID {process.pid}). Logs -> {LOG_FILE}")
    except Exception as exc:
        print(f"Impossible de démarrer le service: {exc}")
        return 1
    finally:
        try:
            if log_fh:
                log_fh.close()
        except Exception:
            pass
    return 0


def cmd_stop(_: argparse.Namespace) -> int:
    pid = _read_pid()
    if not pid:
        print("Aucun PID trouvé, le service semble arrêté.")
        PID_FILE.unlink(missing_ok=True)
        return 0

    if not _is_process_running(pid):
        print("Processus introuvable, suppression du fichier PID.")
        PID_FILE.unlink(missing_ok=True)
        return 0

    print(f"Arrêt du service (PID {pid})...")
    try:
        os.kill(pid, signal.SIGTERM)
    except Exception as exc:
        print(f"Erreur lors de l'arrêt: {exc}")
        return 1

    for _ in range(30):
        if not _is_process_running(pid):
            PID_FILE.unlink(missing_ok=True)
            print("Service arrêté proprement.")
            return 0
        time.sleep(0.5)

    print("Arrêt impossible (processus toujours actif).")
    return 1


def cmd_restart(args: argparse.Namespace) -> int:
    stop_code = cmd_stop(args)
    start_code = cmd_start(args)
    return stop_code or start_code


def cmd_status(_: argparse.Namespace) -> int:
    pid = _read_pid()
    running = _is_process_running(pid)
    db_path = _resolve_db_path()
    db_state = "KO"
    clients_count = "?"
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT COUNT(*) FROM users")
        clients_count = cursor.fetchone()[0]
        db_state = "OK"
    except Exception as exc:
        db_state = f"KO ({exc})"
    finally:
        try:
            conn.close()
        except Exception:
            pass

    print(f"Processus : {'Actif' if running else 'Inactif'}{f' (PID {pid})' if pid else ''}")
    print(f"Base : {db_state} ({db_path})")
    print(f"Clients en base : {clients_count}")
    print(f"Logs : {LOG_FILE}")
    return 0 if running else 1


def cmd_logs(_: argparse.Namespace) -> int:
    ensure_runtime_dirs()
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOG_FILE.touch(exist_ok=True)
    print(f"Lecture en direct de {LOG_FILE} (Ctrl+C pour quitter)")
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            f.seek(0, os.SEEK_END)
            while True:
                line = f.readline()
                if not line:
                    time.sleep(0.5)
                    continue
                print(line, end="")
    except KeyboardInterrupt:
        print("\nArrêt du suivi des logs.")
    return 0


def cmd_update(_: argparse.Namespace) -> int:
    try:
        result = subprocess.run(
            ["git", "pull"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        if result.stdout:
            print(result.stdout.strip())
        if result.stderr:
            print(result.stderr.strip(), file=sys.stderr)
        return result.returncode
    except FileNotFoundError:
        print("Git n'est pas disponible sur cette machine.")
        return 1


def cmd_db_backup(_: argparse.Namespace) -> int:
    ensure_runtime_dirs()
    db_path = _resolve_db_path()
    if not db_path.exists():
        print(f"Aucune base trouvée à {db_path}")
        return 1

    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = BACKUPS_DIR / f"optimasol-{timestamp}.db"
    try:
        import shutil

        shutil.copy2(db_path, dest)
    except Exception as exc:
        print(f"Backup échoué: {exc}")
        return 1

    print(f"Backup créé: {dest}")
    return 0


def cmd_client_ls(_: argparse.Namespace) -> int:
    db_path = _resolve_db_path()
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT id, name, driver_id FROM users ORDER BY name").fetchall()
    except Exception as exc:
        print(f"Impossible de lire la base: {exc}")
        return 1
    finally:
        try:
            conn.close()
        except Exception:
            pass

    if not rows:
        print("Aucun client enregistré.")
        return 0

    print(f"{'ID':36} | {'Nom':20} | Driver | Statut")
    print("-" * 80)
    for row in rows:
        status = "configuré" if row["driver_id"] else "incomplet"
        print(f"{row['id']:36} | {row['name'][:20]:20} | {row['driver_id'] or '-':7} | {status}")
    return 0


def cmd_client_create(_: argparse.Namespace) -> int:
    db_path = _resolve_db_path()
    ensure_runtime_dirs()
    try:
        from .database import DBManager
    except Exception as exc:
        print(f"Chargement du gestionnaire BDD impossible: {exc}")
        return 1

    manager = DBManager(db_path)
    drivers = manager.get_available_drivers()
    if not drivers:
        print("Aucun driver disponible.")
        return 1

    print("=== Création d'un client ===")
    name = input("Nom : ").strip()
    email = input("Email : ").strip()
    password = getpass("Mot de passe : ")

    print("\nChoix du driver :")
    for idx, drv in enumerate(drivers, start=1):
        print(f"  {idx}) {drv['name']} ({drv['id']})")
    try:
        choice = int(input("Sélection : ").strip())
        driver_type_id = drivers[choice - 1]["id"]
    except Exception:
        print("Choix invalide.")
        return 1

    serial_number = input("Numéro de série du device : ").strip()

    try:
        new_id = manager.create_client_ui(
            name=name,
            email=email,
            password=password,
            driver_type_id=driver_type_id,
            serial_number=serial_number,
        )
        print(f"Client créé avec l'ID : {new_id}")
        return 0
    except Exception as exc:
        print(f"Erreur lors de la création : {exc}")
        return 1


def cmd_client_rm(args: argparse.Namespace) -> int:
    client_id = args.client_id
    confirmation = input(f"Confirmer la suppression du client {client_id} ? (yes/no) ").strip().lower()
    if confirmation not in {"y", "yes"}:
        print("Suppression annulée.")
        return 1

    db_path = _resolve_db_path()
    try:
        from .database import DBManager
    except Exception as exc:
        print(f"Chargement du gestionnaire BDD impossible: {exc}")
        return 1

    manager = DBManager(db_path)
    try:
        ok = manager.delete_client_ui(client_id)
        if ok:
            print("Client supprimé.")
            return 0
        print("Aucun client supprimé.")
    except Exception as exc:
        print(f"Suppression échouée: {exc}")
    return 1


def cmd_client_show(args: argparse.Namespace) -> int:
    db_path = _resolve_db_path()
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM users WHERE id = ?", (args.client_id,)).fetchone()
    except Exception as exc:
        print(f"Impossible de lire la base: {exc}")
        return 1
    finally:
        try:
            conn.close()
        except Exception:
            pass

    if not row:
        print("Client introuvable.")
        return 1

    data = {key: row[key] for key in row.keys()}
    print(json.dumps(data, indent=2, ensure_ascii=False))
    return 0


def _load_activation_keys() -> dict:
    ensure_runtime_dirs()
    path = DATA_DIR / "activation_keys.json"
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_activation_keys(payload: dict) -> None:
    path = DATA_DIR / "activation_keys.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def _generate_activation_key(existing: set[str]) -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    while True:
        token = "".join(random.choice(alphabet) for _ in range(4))
        key = f"OPT-{token}"
        if key not in existing:
            return key


def cmd_key_gen(args: argparse.Namespace) -> int:
    client_id = args.client_id
    db_path = _resolve_db_path()
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        exists = conn.execute("SELECT 1 FROM users WHERE id = ? LIMIT 1", (client_id,)).fetchone()
    except Exception as exc:
        print(f"Impossible de lire la base: {exc}")
        return 1
    finally:
        try:
            conn.close()
        except Exception:
            pass

    if not exists:
        print("Client introuvable.")
        return 1

    keys = _load_activation_keys()
    existing_keys = {entry["key"] for entry in keys.values()} if keys else set()
    new_key = _generate_activation_key(existing_keys)
    keys[client_id] = {"key": new_key, "generated_at": datetime.utcnow().isoformat() + "Z"}
    _save_activation_keys(keys)
    print(f"Clé générée pour {client_id} : {new_key}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="optimasol", description="Administration Optimasol")
    sub = parser.add_subparsers(dest="command")
    sub.required = True

    sub.add_parser("start", help="Démarre le service").set_defaults(func=cmd_start)
    sub.add_parser("stop", help="Arrête le service").set_defaults(func=cmd_stop)
    sub.add_parser("restart", help="Redémarre le service").set_defaults(func=cmd_restart)
    sub.add_parser("status", help="État du service et de la BDD").set_defaults(func=cmd_status)
    sub.add_parser("logs", help="Affiche les logs en direct").set_defaults(func=cmd_logs)
    sub.add_parser("update", help="Met à jour le dépôt (git pull)").set_defaults(func=cmd_update)

    db_parser = sub.add_parser("db", help="Opérations sur la base de données")
    db_sub = db_parser.add_subparsers(dest="db_command")
    db_sub.required = True
    db_sub.add_parser("backup", help="Crée un backup immédiat").set_defaults(func=cmd_db_backup)

    client_parser = sub.add_parser("client", help="Gestion des clients")
    client_sub = client_parser.add_subparsers(dest="client_command")
    client_sub.required = True
    client_sub.add_parser("ls", help="Liste des clients").set_defaults(func=cmd_client_ls)
    client_sub.add_parser("create", help="Assistant de création").set_defaults(func=cmd_client_create)
    rm = client_sub.add_parser("rm", help="Suppression d'un client")
    rm.add_argument("client_id")
    rm.set_defaults(func=cmd_client_rm)
    show = client_sub.add_parser("show", help="Affiche la configuration d'un client")
    show.add_argument("client_id")
    show.set_defaults(func=cmd_client_show)

    key_parser = sub.add_parser("key", help="Gestion des clés d'activation")
    key_sub = key_parser.add_subparsers(dest="key_command")
    key_sub.required = True
    key_gen = key_sub.add_parser("gen", help="Génère une clé pour un client")
    key_gen.add_argument("client_id")
    key_gen.set_defaults(func=cmd_key_gen)

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
