#!/usr/bin/env python3
"""
Mini serveur HTTP pour l'UI Optimasol.
- Endpoints JSON : authentification, création via clé, lecture/écriture configs, métriques et historiques.
- Sert aussi les assets statiques du dossier web/.

Lancez-le depuis la racine du projet avec le Python du venv :
    ./venv/bin/python web/server.py
"""

from __future__ import annotations

import json
import os
import secrets
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlparse

ROOT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT_DIR.parent
SRC_DIR = PROJECT_ROOT / "src"

# Assure que "src/" est dans PYTHONPATH pour importer le package optimasol
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from optimasol.cli import _resolve_db_path
from optimasol.database import DBManager
from optimasol.drivers import ALL_DRIVERS
from optimasol.paths import DATA_DIR, DEFAULT_DB_PATH, LOG_FILE, PID_FILE, RUNTIME_ROOT
from optimiser_engine import Client as EngineClient
from weather_manager import Client as WeatherClient, Installation_PV, Panneau, Position
from werkzeug.security import check_password_hash, generate_password_hash


# --------- Helpers de fichiers ---------
def _load_activation_keys() -> dict:
    path = DATA_DIR / "activation_keys.json"
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def _save_activation_keys(payload: dict) -> None:
    path = DATA_DIR / "activation_keys.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)


def _now_iso() -> str:
    return datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()


# --------- Objet State partagé ---------
class ApiState:
    """Regroupe les ressources partagées (DB, sessions, lock)."""

    def __init__(self) -> None:
        self.db_path = _resolve_db_path() if callable(_resolve_db_path) else DEFAULT_DB_PATH
        self.db = DBManager(self.db_path)
        self.sessions: dict[str, dict[str, Any]] = {}
        self.lock = threading.Lock()

    # --- Sessions ---
    def new_session(self, client_id: str, email: str) -> str:
        token = secrets.token_urlsafe(32)
        self.sessions[token] = {
            "client_id": client_id,
            "email": email,
            "created_at": time.time(),
        }
        return token

    def get_session(self, auth_header: str | None) -> Optional[dict]:
        if not auth_header or not auth_header.startswith("Bearer "):
            return None
        token = auth_header.split(" ", 1)[1].strip()
        return self.sessions.get(token)

    # --- DB helpers ---
    def _fetch_user_row(self, *, email: str | None = None, client_id: str | None = None) -> Optional[dict]:
        query = "SELECT * FROM users WHERE "
        params: list[Any] = []
        if email:
            query += "email = ?"
            params.append(email)
        elif client_id:
            query += "id = ?"
            params.append(client_id)
        else:
            return None

        with self.lock:
            conn = self.db._get_conn()
            conn.row_factory = lambda c, r: {c.description[i][0]: r[i] for i in range(len(r))}
            try:
                row = conn.execute(query, params).fetchone()
            finally:
                conn.close()
        return row

    def _latest_value(self, table: str, column: str, client_id: str) -> Optional[dict]:
        sql = f"SELECT {column}, timestamp FROM {table} WHERE client_id = ? ORDER BY timestamp DESC LIMIT 1"
        with self.lock:
            conn = self.db._get_conn()
            try:
                row = conn.execute(sql, (client_id,)).fetchone()
            finally:
                conn.close()
        if not row:
            return None
        return {"value": row[0], "timestamp": row[1]}

    def _history(self, table: str, column: str, client_id: str, hours: int) -> list[dict[str, Any]]:
        begin_ts = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
        sql = f"""
            SELECT {column}, timestamp FROM {table}
            WHERE client_id = ? AND timestamp >= ?
            ORDER BY timestamp ASC
        """
        with self.lock:
            conn = self.db._get_conn()
            try:
                rows = conn.execute(sql, (client_id, begin_ts)).fetchall()
            finally:
                conn.close()
        return [{"value": r[0], "timestamp": r[1]} for r in rows]

    # --- Conversion des configs ---
    def _ensure_weather_payload(self, raw: dict | None) -> dict:
        payload = raw or {}
        pos = payload.get("position") or {}
        install = payload.get("installation") or {}
        panneaux = install.get("liste_panneaux") or []

        if not pos:
            pos = {"latitude": 50.62925, "longitude": 3.057256, "altitude": 25}
        if not panneaux:
            panneaux = [
                {
                    "azimuth": 180.0,
                    "tilt": 25.0,
                    "surface_panneau": install.get("surface_panneau") or 2.0,
                    "puissance_nominale": install.get("puissance_nominale") or 800.0,
                }
            ]
        install_payload = {
            "rendement_global": install.get("rendement_global"),
            "liste_panneaux": panneaux,
        }
        return {"position": pos, "installation": install_payload}

    def _build_weather_obj(self, payload: dict) -> WeatherClient:
        p = self._ensure_weather_payload(payload)
        return WeatherClient.from_dict(p)

    def _build_engine_obj(self, payload: dict | None) -> EngineClient:
        return EngineClient.from_dict(payload or {})

    def _build_driver_obj(self, payload: dict | None):
        data = payload or {}
        driver_id = data.get("id") or "smart_electromation_mqtt"
        cfg = data.get("config") or {}
        cls = next((d for d in ALL_DRIVERS if d.get_driver_def()["id"] == driver_id), None)
        if cls is None:
            raise ValueError("Driver inconnu")
        return cls.dict_to_device(cfg), driver_id

    def _save_user(
        self,
        client_id: str,
        name: str,
        email: str,
        password: str | None,
        engine_payload: dict,
        weather_payload: dict,
        driver_payload: dict,
    ) -> None:
        engine = self._build_engine_obj(engine_payload)
        weather = self._build_weather_obj(weather_payload)
        driver, driver_id = self._build_driver_obj(driver_payload)

        json_engine = json.dumps(engine.to_dict())
        json_weather = json.dumps(weather.to_dict())
        json_driver = json.dumps(driver.device_to_dict())
        hashed_pw = generate_password_hash(password) if password else None

        with self.lock:
            conn = self.db._get_conn()
            try:
                existing = conn.execute("SELECT id FROM users WHERE id = ?", (client_id,)).fetchone()
                if existing:
                    conn.execute(
                        """
                        UPDATE users
                        SET name = ?, email = ?, config_engine = ?, config_weather = ?, config_driver = ?, driver_id = ?, weather_ref = ?
                        {pw_clause}
                        WHERE id = ?
                        """.replace(
                            "{pw_clause}", ", hash = ?" if hashed_pw else ""
                        ),
                        (
                            name,
                            email,
                            json_engine,
                            json_weather,
                            json_driver,
                            driver_id,
                            client_id,
                            hashed_pw,
                            client_id,
                        )
                        if hashed_pw
                        else (
                            name,
                            email,
                            json_engine,
                            json_weather,
                            json_driver,
                            driver_id,
                            client_id,
                            client_id,
                        ),
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO users (id, name, email, hash, driver_id, config_engine, config_weather, config_driver, config_ui, weather_ref)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, '{}', ?)
                        """,
                        (
                            client_id,
                            name,
                            email,
                            hashed_pw or generate_password_hash(secrets.token_urlsafe(12)),
                            driver_id,
                            json_engine,
                            json_weather,
                            json_driver,
                            client_id,
                        ),
                    )
                conn.commit()
            finally:
                conn.close()


STATE = ApiState()


# --------- HTTP Handler ---------
class ApiHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT_DIR), **kwargs)

    # Utilities
    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw)
        except Exception:
            return {}

    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def _require_auth(self) -> Optional[dict]:
        session = STATE.get_session(self.headers.get("Authorization"))
        if session:
            return session
        self._send_json({"error": "unauthorized"}, status=401)
        return None

    def log_message(self, format: str, *args) -> None:
        # Console concise
        sys.stderr.write("%s\n" % (format % args))

    # Routes
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, OPTIONS")
        self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/auth/login":
            return self._handle_login()
        if parsed.path == "/api/auth/register":
            return self._handle_register()
        if parsed.path == "/api/client/config":
            return self._handle_update_config()
        self.send_error(404, "Not found")

    def do_PUT(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/client/config":
            return self._handle_update_config()
        self.send_error(404, "Not found")

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/client/config":
            return self._handle_get_config()
        if parsed.path == "/api/client/overview":
            return self._handle_overview()
        if parsed.path == "/api/client/history":
            return self._handle_history()
        if parsed.path == "/api/meta/drivers":
            return self._handle_drivers()
        if parsed.path == "/api/service/status":
            return self._handle_service_status()
        return super().do_GET()

    # --- Handlers métier ---
    def _handle_login(self):
        payload = self._read_json()
        email = (payload.get("email") or "").strip().lower()
        password = payload.get("password") or ""
        if not email or not password:
            return self._send_json({"error": "Email et mot de passe requis"}, status=400)

        client_id = STATE.db.check_login(email, password)
        if not client_id:
            return self._send_json({"error": "Identifiants invalides"}, status=401)
        row = STATE._fetch_user_row(client_id=client_id)
        token = STATE.new_session(client_id, email)
        return self._send_json(
            {
                "token": token,
                "client_id": client_id,
                "email": email,
                "name": row.get("name") if row else None,
            }
        )

    def _handle_register(self):
        payload = self._read_json()
        key = (payload.get("activation_key") or "").strip().upper()
        name = (payload.get("name") or "").strip()
        email = (payload.get("email") or "").strip().lower()
        password = payload.get("password") or ""
        engine = payload.get("engine") or {}
        weather = payload.get("weather") or {}
        driver = payload.get("driver") or {}

        if not (key and name and email and password):
            return self._send_json({"error": "Champs requis manquants"}, status=400)

        keys = _load_activation_keys()
        matched_client_id = None
        matched_entry = None
        for cid, entry in keys.items():
            if entry.get("key") == key:
                matched_client_id = cid
                matched_entry = entry
                break
        if not matched_client_id:
            return self._send_json({"error": "Clé invalide ou expirée"}, status=403)

        try:
            STATE._save_user(
                client_id=matched_client_id,
                name=name,
                email=email,
                password=password,
                engine_payload=engine,
                weather_payload=weather,
                driver_payload=driver,
            )
        except Exception as exc:
            return self._send_json({"error": f"Echec création: {exc}"}, status=400)

        matched_entry["used_at"] = _now_iso()
        matched_entry["used_by"] = email
        keys[matched_client_id] = matched_entry
        _save_activation_keys(keys)

        token = STATE.new_session(matched_client_id, email)
        return self._send_json({"token": token, "client_id": matched_client_id, "email": email, "name": name})

    def _handle_get_config(self):
        session = self._require_auth()
        if not session:
            return
        row = STATE._fetch_user_row(client_id=session["client_id"])
        if not row:
            return self._send_json({"error": "Client introuvable"}, status=404)
        engine_cfg = json.loads(row.get("config_engine") or "{}")
        weather_cfg = json.loads(row.get("config_weather") or "{}")
        driver_cfg = {"id": row.get("driver_id"), "config": json.loads(row.get("config_driver") or "{}")}
        return self._send_json(
            {
                "client_id": row.get("id"),
                "name": row.get("name"),
                "email": row.get("email"),
                "engine": engine_cfg,
                "weather": weather_cfg,
                "driver": driver_cfg,
            }
        )

    def _handle_update_config(self):
        session = self._require_auth()
        if not session:
            return
        payload = self._read_json()
        name = (payload.get("name") or "").strip()
        email = (payload.get("email") or "").strip().lower()
        password = payload.get("password") or None
        engine = payload.get("engine") or {}
        weather = payload.get("weather") or {}
        driver = payload.get("driver") or {}

        if not name or not email:
            return self._send_json({"error": "Nom et email requis"}, status=400)

        try:
            STATE._save_user(
                client_id=session["client_id"],
                name=name,
                email=email,
                password=password,
                engine_payload=engine,
                weather_payload=weather,
                driver_payload=driver,
            )
        except Exception as exc:
            return self._send_json({"error": f"Mise à jour impossible: {exc}"}, status=400)
        return self._send_json({"ok": True})

    def _handle_overview(self):
        session = self._require_auth()
        if not session:
            return
        cid = session["client_id"]
        row = STATE._fetch_user_row(client_id=cid)
        if not row:
            return self._send_json({"error": "Client introuvable"}, status=404)

        latest_temp = STATE._latest_value("temperatures", "temperature", cid)
        latest_prod = STATE._latest_value("productions_measures", "production", cid)
        latest_dec = STATE._latest_value("decisions_history", "decision_report", cid)

        payload = {
            "client": {
                "id": row.get("id"),
                "name": row.get("name"),
                "email": row.get("email"),
                "driver_id": row.get("driver_id"),
            },
            "location": (json.loads(row.get("config_weather") or "{}") or {}).get("position"),
            "pv": (json.loads(row.get("config_weather") or "{}") or {}).get("installation"),
            "engine": json.loads(row.get("config_engine") or "{}"),
            "live": {
                "temperature": latest_temp,
                "production": latest_prod,
                "decision": latest_dec,
            },
        }
        return self._send_json(payload)

    def _handle_history(self):
        session = self._require_auth()
        if not session:
            return
        qs = parse_qs(urlparse(self.path).query)
        metric = (qs.get("metric") or ["temperature"])[0]
        hours = int((qs.get("hours") or [48])[0])

        mapping = {
            "temperature": ("temperatures", "temperature"),
            "production": ("productions_measures", "production"),
            "forecast": ("forecasts", "production"),
            "decision": ("decisions_history", "decision_report"),
        }
        if metric not in mapping:
            return self._send_json({"error": "Metric inconnue"}, status=400)
        table, column = mapping[metric]
        data = STATE._history(table, column, session["client_id"], hours)
        return self._send_json({"metric": metric, "hours": hours, "series": data})

    def _handle_drivers(self):
        drivers = [d.get_driver_def() for d in ALL_DRIVERS]
        return self._send_json({"drivers": drivers})

    def _handle_service_status(self):
        pid = None
        running = False
        if PID_FILE.exists():
            try:
                pid = int(PID_FILE.read_text().strip())
                os.kill(pid, 0)
                running = True
            except Exception:
                running = False
        payload = {
            "running": running,
            "pid": pid,
            "db_path": str(STATE.db.path),
            "runtime_root": str(RUNTIME_ROOT),
            "log_file": str(LOG_FILE),
        }
        return self._send_json(payload)


def run(server_class=ThreadingHTTPServer, handler_class=ApiHandler):
    addr = ("0.0.0.0", 8000)
    httpd = server_class(addr, handler_class)
    print(f"[UI] Serveur démarré sur http://{addr[0]}:{addr[1]} (dossier {ROOT_DIR})")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nArrêt demandé, au revoir.")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    run()
