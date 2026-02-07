from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import smtplib
from collections import deque
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, validator

from optimasol.database import DBManager
from optimasol.default import DEFAULT_DB_PATH, LOG_FILE, PID_FILE, PROJECT_ROOT
from optimasol.logging_setup import setup_logging
from optimasol.config_loader import load_config_file
from optimasol.core import AllClients


setup_logging()
app = FastAPI(title="Optimasol GUI API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Allow it during development first; once it’s stable, you can tighten it to your domain.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


WEB_ROOT = PROJECT_ROOT / "web"
STATIC_DIR = WEB_ROOT / "static"
TEMPLATE_INDEX = WEB_ROOT / "templates" / "index.html"


# -------- Helpers ----------

def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _static_version() -> str:
    paths = [
        STATIC_DIR / "app.js",
        STATIC_DIR / "style.css",
        TEMPLATE_INDEX,
    ]
    mtimes = []
    for path in paths:
        try:
            if path.exists():
                mtimes.append(int(path.stat().st_mtime))
        except Exception:
            continue
    if not mtimes:
        return "0"
    return str(max(mtimes))


def _hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return f"{salt}${digest.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        salt, hexd = stored.split("$", 1)
    except ValueError:
        return False
    test = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return hmac.compare_digest(test.hex(), hexd)


def _config() -> dict:
    return load_config_file()


def _resolve_db_path(cfg: dict) -> Path:
    path_cfg = cfg.get("path_to_db", {})
    raw = path_cfg.get("path_to_db") if isinstance(path_cfg, dict) else None
    if not raw:
        return DEFAULT_DB_PATH
    path = Path(str(raw)).expanduser()
    if not path.is_absolute():
        path = (PROJECT_ROOT / path).resolve()
    return path


def _db():
    cfg = _config()
    return DBManager(_resolve_db_path(cfg))


def _ensure_activation_table(db: DBManager):
    db.execute_commit(
        """
        CREATE TABLE IF NOT EXISTS activation_keys (
            activation_key TEXT PRIMARY KEY,
            client_id      INTEGER,
            status         TEXT DEFAULT 'issued',
            created_at     TEXT NOT NULL,
            expires_at     TEXT,
            used_at        TEXT
        );
        """,
        (),
    )

    fk_rows = db.execute_query("PRAGMA foreign_key_list('activation_keys')")
    cols = db.execute_query("PRAGMA table_info('activation_keys')")
    client_notnull = False
    for col in cols:
        if col[1] == "client_id":
            client_notnull = bool(col[3])
            break

    if fk_rows or client_notnull:
        db.execute_commit(
            """
            CREATE TABLE IF NOT EXISTS activation_keys_new (
                activation_key TEXT PRIMARY KEY,
                client_id      INTEGER,
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


def _ensure_users_tables(db: DBManager):
    _ensure_activation_table(db)
    db.execute_commit(
        """
        CREATE TABLE IF NOT EXISTS users_auth (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            email          TEXT UNIQUE NOT NULL,
            name           TEXT NOT NULL,
            password_hash  TEXT NOT NULL,
            client_id      INTEGER NOT NULL,
            preferences    TEXT,
            created_at     TEXT NOT NULL,
            FOREIGN KEY (client_id) REFERENCES users_main(id)
                ON UPDATE CASCADE
                ON DELETE CASCADE
        );
        """,
        (),
    )
    db.execute_commit(
        """
        CREATE TABLE IF NOT EXISTS ui_sessions (
            token      TEXT PRIMARY KEY,
            user_id    INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users_auth(id)
                ON UPDATE CASCADE
                ON DELETE CASCADE
        );
        """,
        (),
    )
    db.execute_commit(
        """
        CREATE TABLE IF NOT EXISTS signup_pending (
            token           TEXT PRIMARY KEY,
            activation_key  TEXT NOT NULL,
            client_id       INTEGER,
            email           TEXT NOT NULL,
            name            TEXT NOT NULL,
            admin_identifier TEXT,
            password_hash   TEXT NOT NULL,
            created_at      TEXT NOT NULL,
            expires_at      TEXT NOT NULL
        );
        """,
        (),
    )

    cols = db.execute_query("PRAGMA table_info('signup_pending')")
    client_notnull = False
    for col in cols:
        if col[1] == "client_id":
            client_notnull = bool(col[3])
            break
    if client_notnull:
        db.execute_commit(
            """
            CREATE TABLE IF NOT EXISTS signup_pending_new (
                token           TEXT PRIMARY KEY,
                activation_key  TEXT NOT NULL,
                client_id       INTEGER,
                email           TEXT NOT NULL,
                name            TEXT NOT NULL,
                admin_identifier TEXT,
                password_hash   TEXT NOT NULL,
                created_at      TEXT NOT NULL,
                expires_at      TEXT NOT NULL
            );
            """,
            (),
        )
        db.execute_commit(
            """
            INSERT OR IGNORE INTO signup_pending_new
            (token, activation_key, client_id, email, name, admin_identifier, password_hash, created_at, expires_at)
            SELECT token, activation_key, client_id, email, name, admin_identifier, password_hash, created_at, expires_at
            FROM signup_pending;
            """,
            (),
        )
        db.execute_commit("DROP TABLE signup_pending;", ())
        db.execute_commit("ALTER TABLE signup_pending_new RENAME TO signup_pending;", ())

    db.execute_commit(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_signup_pending_activation
        ON signup_pending (activation_key);
        """,
        (),
    )


def _next_client_id(db: DBManager) -> int:
    rows = db.execute_query("SELECT id FROM users_main ORDER BY id")
    next_id = 1
    for (cid,) in rows:
        try:
            cid_int = int(cid)
        except Exception:
            continue
        if cid_int == next_id:
            next_id += 1
        elif cid_int > next_id:
            break
    return next_id


def _extract_serial(driver_obj) -> str | None:
    try:
        data = driver_obj.device_to_dict()
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    serial = data.get("serial_number")
    return str(serial) if serial else None


def _ensure_unique_serial(db: DBManager, serial: str | None, exclude_client_id: int | None = None) -> None:
    if not serial:
        return
    rows = db.execute_query("SELECT id, config_driver FROM users_main")
    for row in rows:
        cid, cfg = row[0], row[1]
        if exclude_client_id is not None and int(cid) == int(exclude_client_id):
            continue
        try:
            data = json.loads(cfg) if cfg else {}
        except Exception:
            data = {}
        if isinstance(data, dict) and data.get("serial_number") == serial:
            raise HTTPException(409, f"Numéro de série déjà utilisé par le client {cid}")


def _cleanup_pending(db: DBManager):
    now = datetime.now(timezone.utc).isoformat()
    db.execute_commit("DELETE FROM signup_pending WHERE expires_at < ?", (now,))


def _new_session(db: DBManager, user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    exp = now + timedelta(hours=12)
    db.execute_commit(
        "INSERT OR REPLACE INTO ui_sessions (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
        (token, user_id, now.isoformat(), exp.isoformat()),
    )
    return token


def _get_token(req: Request) -> str:
    raw = (req.headers.get("Authorization") or "").strip()
    if not raw:
        return ""
    if raw.lower().startswith("bearer "):
        return raw[7:].strip()
    return raw

def _require_session(req: Request, db: DBManager):
    token = _get_token(req)
    if not token:
        raise HTTPException(401, "Missing token")

    rows = db.execute_query(
        "SELECT user_id, expires_at FROM ui_sessions WHERE token = ?", (token,)
    )
    if not rows:
        raise HTTPException(401, "Invalid session")

    user_id, expires_at = rows[0]
    if datetime.fromisoformat(expires_at) < datetime.now(timezone.utc):
        # 过期顺手清理掉
        db.execute_commit("DELETE FROM ui_sessions WHERE token = ?", (token,))
        raise HTTPException(401, "Session expired")

    return user_id



def _load_client_template() -> dict:
    template_path = PROJECT_ROOT / "client_sample_shell.json"
    if template_path.exists():
        try:
            return json.loads(template_path.read_text())
        except Exception:
            pass
    return {
        "id": 0,
        "engine": {
            "client_id": 0,
            "water_heater": {
                "volume": 200,
                "power": 2400,
                "insulation_coeff": 0.8,
                "temp_cold_water": 15,
            },
            "prices": {"mode": "BASE", "base_price": 0.18, "resell_price": 0.06},
            "features": {"gradation": True, "mode": "cost"},
            "constraints": {"min_temp": 45, "forbidden_slots": [], "background_noise": 250.0},
            "planning": [],
        },
        "weather": {
            "client_id": 0,
            "position": {"latitude": 0.0, "longitude": 0.0, "altitude": 0},
            "installation": {
                "rendement_global": 0.18,
                "liste_panneaux": [
                    {"azimuth": 180, "tilt": 30, "surface_panneau": 1.8, "puissance_nominale": 350}
                ],
            },
        },
        "driver": {"type": "", "config": {}},
    }


def _deep_merge(base: dict, updates: dict) -> dict:
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            base[key] = _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def _price_mode(value: Any) -> str:
    mode = str(value or "").strip().upper()
    if mode == "BASE":
        return "BASE"
    if mode in {"HPHC", "HP/HC", "HC/HP", "HP-HC", "HC-HP"}:
        return "HPHC"
    return "BASE"


def _to_float(value: Any, default: float) -> float:
    if value is None:
        return default
    if isinstance(value, str):
        value = value.strip().replace(",", ".")
    try:
        return float(value)
    except Exception:
        return default


def _normalize_prices(prices: Any, defaults: Optional[Dict[str, Any]] = None) -> Dict[str, float | str]:
    source = prices if isinstance(prices, dict) else {}
    base_defaults = defaults if isinstance(defaults, dict) else {}

    mode = _price_mode(source.get("mode", base_defaults.get("mode")))
    normalized: Dict[str, float | str] = {
        "mode": mode,
        "resell_price": _to_float(source.get("resell_price"), _to_float(base_defaults.get("resell_price"), 0.06)),
    }

    if mode == "HPHC":
        normalized["hp_price"] = _to_float(source.get("hp_price"), _to_float(base_defaults.get("hp_price"), 0.22))
        normalized["hc_price"] = _to_float(source.get("hc_price"), _to_float(base_defaults.get("hc_price"), 0.14))
    else:
        normalized["base_price"] = _to_float(source.get("base_price"), _to_float(base_defaults.get("base_price"), 0.18))
    return normalized


def _build_client_from_assistant(client_id: int, assistant: dict) -> dict:
    template = deepcopy(_load_client_template())
    template["id"] = client_id
    if isinstance(template.get("engine"), dict):
        template["engine"]["client_id"] = client_id
    if isinstance(template.get("weather"), dict):
        template["weather"]["client_id"] = client_id

    engine = assistant.get("engine") or {}
    weather = assistant.get("weather") or {}
    driver = assistant.get("driver") or {}

    if isinstance(engine, dict):
        default_prices = deepcopy(template["engine"].get("prices", {}))
        template["engine"] = _deep_merge(template["engine"], engine)
        template["engine"]["prices"] = _normalize_prices(template["engine"].get("prices"), default_prices)
    if isinstance(weather, dict):
        template["weather"] = _deep_merge(template["weather"], weather)
    if isinstance(driver, dict) and driver:
        template["driver"] = driver

    return template


def _normalize_driver_defs(drivers: List[type]) -> List[dict]:
    normalized = []
    for drv in drivers:
        try:
            definition = drv.get_driver_def()
        except Exception:
            continue
        icon_path = definition.get("icon_path")
        icon_data = None
        if icon_path:
            try:
                path = Path(icon_path)
                if path.exists():
                    mime = "image/png"
                    data = base64.b64encode(path.read_bytes()).decode("ascii")
                    icon_data = f"data:{mime};base64,{data}"
            except Exception:
                icon_data = None
        definition["icon_data"] = icon_data
        normalized.append(definition)
    return normalized


def _smtp_cfg() -> dict:
    cfg = _config()
    return cfg.get("smtp_config", {}) if isinstance(cfg, dict) else {}


def _send_welcome_email(to_email: str, name: str, config: dict) -> None:
    if not config or not config.get("enabled"):
        return

    host = config.get("host")
    port = int(config.get("port") or 0)
    username = config.get("username")
    password = config.get("password")
    from_email = config.get("from_email") or username
    use_tls = bool(config.get("use_tls", True))
    guide_path = config.get("welcome_pdf") or ""
    subject = config.get("welcome_subject") or "Bienvenue chez Optimasol"
    body = config.get("welcome_body") or f"Bonjour {name},\n\nBienvenue chez Optimasol."

    if not (host and port and username and password and from_email):
        return

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_email
    msg.set_content(body)

    if guide_path:
        path = Path(guide_path)
        if not path.is_absolute():
            path = (PROJECT_ROOT / path).resolve()
        if path.exists():
            data = path.read_bytes()
            msg.add_attachment(
                data,
                maintype="application",
                subtype="pdf",
                filename=path.name,
            )

    with smtplib.SMTP(host, port, timeout=20) as server:
        if use_tls:
            server.starttls()
        server.login(username, password)
        server.send_message(msg)


def _last_df_value(df, column: str) -> Optional[dict]:
    try:
        if df is None or df.empty:
            return None
        row = df.tail(1).iloc[0]
        ts = row.name.isoformat() if hasattr(row, "name") else None
        return {"value": row[column], "timestamp": ts}
    except Exception:
        return None


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        raw = value.strip()
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _read_service_pid() -> Optional[int]:
    try:
        if not PID_FILE.exists():
            return None
        return int(PID_FILE.read_text().strip())
    except Exception:
        return None


def _is_process_alive(pid: Optional[int]) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _last_df_timestamp(df) -> Optional[datetime]:
    try:
        if df is None or df.empty:
            return None
        ts = df.tail(1).index[-1]
        if isinstance(ts, datetime):
            if ts.tzinfo is None:
                return ts.replace(tzinfo=timezone.utc)
            return ts
        return _parse_dt(str(ts))
    except Exception:
        return None


def _parse_log_ts(line: str) -> Optional[datetime]:
    try:
        # Format attendu: "YYYY-MM-DD HH:MM:SS | ..."
        stamp = line[:19]
        dt = datetime.strptime(stamp, "%Y-%m-%d %H:%M:%S")
        return dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _tail_lines(path: Path, limit: int = 4000) -> List[str]:
    try:
        if not path.exists():
            return []
        with path.open("r", encoding="utf-8", errors="ignore") as fh:
            return list(deque(fh, maxlen=limit))
    except Exception:
        return []


def _driver_state_from_logs(serial: Optional[str]) -> Dict[str, Optional[str]]:
    if not serial:
        return {"state": None, "event_at": None}

    log_paths = [
        LOG_FILE,
        Path(str(LOG_FILE) + ".1"),
        Path(str(LOG_FILE) + ".2"),
    ]
    all_lines: List[str] = []
    for path in log_paths:
        all_lines.extend(_tail_lines(path, limit=2500))

    for line in reversed(all_lines):
        if serial not in line:
            continue

        line_l = line.lower()
        ts = _parse_log_ts(line)
        ts_iso = ts.isoformat() if ts else None

        # "Activé" = connexion broker réussie + écoute active (subscribe OK).
        if "subscription to" in line_l and "successful" in line_l:
            return {"state": "activated", "event_at": ts_iso}
        if "successfully connected to mqtt broker" in line_l:
            return {"state": "activated", "event_at": ts_iso}

        # "Échec" = déconnexion ou échec de connexion broker.
        if "disconnected from mqtt broker" in line_l:
            return {"state": "failed", "event_at": ts_iso}
        if "connection failed with return code" in line_l:
            return {"state": "failed", "event_at": ts_iso}
        if "initial connection failed" in line_l:
            return {"state": "failed", "event_at": ts_iso}

    return {"state": None, "event_at": None}


# -------- Pydantic Models ----------


class SignupPayload(BaseModel):
    activation_key: str
    email: EmailStr
    name: str
    password: str
    client: Dict[str, Any]

    @validator("name")
    def name_not_empty(cls, v):
        if not v.strip():
            raise ValueError("name required")
        return v.strip()

    @validator("password")
    def strong_password(cls, v):
        if len(v) < 8:
            raise ValueError("password must be at least 8 chars")
        return v


class LoginPayload(BaseModel):
    email: EmailStr
    password: str


class ClientUpdatePayload(BaseModel):
    client: Dict[str, Any]


class SignupStartPayload(BaseModel):
    activation_key: str
    email: EmailStr
    name: str
    password: str
    password_confirm: str

    @validator("name")
    def start_name_not_empty(cls, v):
        if not v.strip():
            raise ValueError("name required")
        return v.strip()

    @validator("password")
    def start_strong_password(cls, v):
        if len(v) < 8:
            raise ValueError("password must be at least 8 chars")
        return v

    @validator("password_confirm")
    def passwords_match(cls, v, values):
        if "password" in values and v != values["password"]:
            raise ValueError("passwords do not match")
        return v


class SignupCompletePayload(BaseModel):
    signup_token: str
    mode: str
    assistant: Optional[Dict[str, Any]] = None
    client_json: Optional[Dict[str, Any]] = None


class PasswordChangePayload(BaseModel):
    current_password: str
    new_password: str
    new_password_confirm: str

    @validator("new_password")
    def new_password_strength(cls, v):
        if len(v) < 8:
            raise ValueError("password must be at least 8 chars")
        return v

    @validator("new_password_confirm")
    def new_passwords_match(cls, v, values):
        if "new_password" in values and v != values["new_password"]:
            raise ValueError("passwords do not match")
        return v


# -------- Routes ----------


@app.get("/", response_class=HTMLResponse)
def index():
    if not TEMPLATE_INDEX.exists():
        raise HTTPException(404, "Template introuvable")
    html = TEMPLATE_INDEX.read_text(encoding="utf-8")
    html = html.replace("__STATIC_VERSION__", _static_version())
    response = HTMLResponse(html)
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/api/drivers")
def drivers():
    from optimasol.drivers import ALL_DRIVERS
    return {"drivers": _normalize_driver_defs(ALL_DRIVERS)}


@app.post("/api/signup/start")
def signup_start(payload: SignupStartPayload):
    db = _db()
    _ensure_users_tables(db)
    _cleanup_pending(db)

    # Ensure activation key exists and is available
    row = db.execute_query(
        "SELECT client_id, status, expires_at FROM activation_keys WHERE activation_key = ?",
        (payload.activation_key,),
    )
    if not row:
        raise HTTPException(400, "Clé invalide")
    client_id, status, expires_at = row[0]
    if status != "issued":
        raise HTTPException(400, "Clé déjà utilisée ou expirée")
    if expires_at:
        try:
            if datetime.fromisoformat(expires_at) < datetime.now(timezone.utc):
                raise HTTPException(400, "Clé expirée")
        except ValueError:
            pass

    # Email uniqueness
    existing = db.execute_query("SELECT 1 FROM users_auth WHERE email = ?", (payload.email,))
    if existing:
        raise HTTPException(400, "Email déjà utilisé")

    # Pending reservation
    pending = db.execute_query(
        "SELECT email FROM signup_pending WHERE activation_key = ?",
        (payload.activation_key,),
    )
    if pending and pending[0][0] != payload.email:
        raise HTTPException(409, "Inscription déjà en cours pour cette clé")
    if pending and pending[0][0] == payload.email:
        db.execute_commit("DELETE FROM signup_pending WHERE activation_key = ?", (payload.activation_key,))

    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    exp = now + timedelta(hours=24)
    password_hash = _hash_password(payload.password)
    db.execute_commit(
        """
        INSERT INTO signup_pending
        (token, activation_key, client_id, email, name, admin_identifier, password_hash, created_at, expires_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            token,
            payload.activation_key,
            client_id,
            payload.email,
            payload.name,
            None,
            password_hash,
            now.isoformat(),
            exp.isoformat(),
        ),
    )
    return {"signup_token": token, "client_id": client_id}


@app.get("/api/signup/pending")
def signup_pending(token: str):
    if not token:
        raise HTTPException(400, "Token manquant")
    db = _db()
    _ensure_users_tables(db)
    _cleanup_pending(db)

    rows = db.execute_query(
        "SELECT email, name, expires_at FROM signup_pending WHERE token = ?",
        (token,),
    )
    if not rows:
        return {"valid": False}
    email, name, expires_at = rows[0]
    try:
        if datetime.fromisoformat(expires_at) < datetime.now(timezone.utc):
            db.execute_commit("DELETE FROM signup_pending WHERE token = ?", (token,))
            return {"valid": False}
    except ValueError:
        pass
    return {"valid": True, "email": email, "name": name, "expires_at": expires_at}


@app.post("/api/signup/complete")
def signup_complete(payload: SignupCompletePayload):
    db = _db()
    _ensure_users_tables(db)
    _cleanup_pending(db)

    rows = db.execute_query(
        """
        SELECT activation_key, client_id, email, name, admin_identifier, password_hash, expires_at
        FROM signup_pending WHERE token = ?
        """,
        (payload.signup_token,),
    )
    if not rows:
        raise HTTPException(400, "Inscription introuvable ou expirée")
    activation_key, client_id, email, name, admin_identifier, password_hash, expires_at = rows[0]
    if client_id is None:
        client_id = _next_client_id(db)
    if datetime.fromisoformat(expires_at) < datetime.now(timezone.utc):
        db.execute_commit("DELETE FROM signup_pending WHERE token = ?", (payload.signup_token,))
        raise HTTPException(400, "Inscription expirée")

    key_row = db.execute_query(
        "SELECT status, expires_at FROM activation_keys WHERE activation_key = ?",
        (activation_key,),
    )
    if not key_row:
        raise HTTPException(400, "Clé invalide")
    if key_row[0][0] != "issued":
        existing = db.execute_query("SELECT 1 FROM users_auth WHERE client_id = ?", (client_id,))
        if existing:
            raise HTTPException(409, "Compte déjà créé. Connectez-vous.")
        raise HTTPException(400, "Clé déjà utilisée ou expirée")
    key_expires = key_row[0][1]
    if key_expires:
        try:
            if datetime.fromisoformat(key_expires) < datetime.now(timezone.utc):
                raise HTTPException(400, "Clé expirée")
        except ValueError:
            pass

    if payload.mode not in {"assistant", "json"}:
        raise HTTPException(400, "Mode invalide")

    if payload.mode == "json":
        if not payload.client_json:
            raise HTTPException(400, "client_json manquant")
        client_payload = payload.client_json
    else:
        assistant = payload.assistant or {}
        client_payload = _build_client_from_assistant(client_id, assistant)

    try:
        client_payload["id"] = client_id
        if isinstance(client_payload.get("engine"), dict):
            client_payload["engine"]["client_id"] = client_id
        if isinstance(client_payload.get("weather"), dict):
            client_payload["weather"]["client_id"] = client_id
    except Exception:
        pass

    try:
        from optimasol.cli import _build_client_from_json
        new_client = _build_client_from_json(client_payload, start_driver=False)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, f"Client invalide: {exc}") from exc

    all_clients = db.client_manager.get_all_clients(start_driver=False)
    try:
        _ensure_unique_serial(db, _extract_serial(new_client.driver))
        all_clients.add(new_client)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, f"Ajout client impossible: {exc}") from exc
    db.client_manager.store_all_clients(all_clients)

    preferences = json.dumps({"admin_identifier": admin_identifier} if admin_identifier else {})
    try:
        db.execute_commit(
            "INSERT INTO users_auth (email, name, password_hash, client_id, preferences, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (email, name, password_hash, client_id, preferences, _now_iso()),
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, f"Création utilisateur impossible: {exc}") from exc

    user_rows = db.execute_query("SELECT id FROM users_auth WHERE email = ?", (email,))
    if not user_rows:
        raise HTTPException(400, "Utilisateur introuvable après création")
    user_id = user_rows[0][0]
    token = _new_session(db, user_id)

    db.execute_commit(
        "UPDATE activation_keys SET status='used', used_at=?, client_id=COALESCE(client_id, ?) WHERE activation_key=?",
        (_now_iso(), client_id, activation_key),
    )

    db.execute_commit("DELETE FROM signup_pending WHERE token = ?", (payload.signup_token,))

    try:
        _send_welcome_email(email, name, _smtp_cfg())
    except Exception:
        pass

    return {"token": token, "client_id": client_id}


@app.post("/api/signup")
def signup(payload: SignupPayload):
    db = _db()
    _ensure_users_tables(db)

    # 1) Activation key check
    row = db.execute_query(
        "SELECT client_id, status FROM activation_keys WHERE activation_key = ?", (payload.activation_key,)
    )
    if not row:
        raise HTTPException(400, "Clé invalide")
    client_id, status = row[0]
    if status != "issued":
        raise HTTPException(400, "Clé déjà utilisée ou expirée")

    # 2) Build client objects
    if client_id is None:
        client_id = _next_client_id(db)

    client_payload = deepcopy(payload.client)
    client_payload["id"] = client_id
    if isinstance(client_payload.get("engine"), dict):
        client_payload["engine"]["client_id"] = client_id
    if isinstance(client_payload.get("weather"), dict):
        client_payload["weather"]["client_id"] = client_id

    try:
        from optimasol.cli import _build_client_from_json  # reuse logic
        new_client = _build_client_from_json(client_payload, start_driver=False)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, f"Client invalide: {exc}") from exc

    # 3) Persist client
    all_clients = db.client_manager.get_all_clients(start_driver=False)
    try:
        _ensure_unique_serial(db, _extract_serial(new_client.driver))
        all_clients.add(new_client)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, f"Ajout client impossible: {exc}") from exc
    db.client_manager.store_all_clients(all_clients)

    # 4) Mark key used
    db.execute_commit(
        "UPDATE activation_keys SET status='used', used_at=?, client_id=COALESCE(client_id, ?) WHERE activation_key=?",
        (_now_iso(), client_id, payload.activation_key),
    )

    # 5) Create auth user
    password_hash = _hash_password(payload.password)
    db.execute_commit(
        "INSERT INTO users_auth (email, name, password_hash, client_id, preferences, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (payload.email, payload.name, password_hash, client_id, json.dumps({}), _now_iso()),
    )
    user_rows = db.execute_query("SELECT id FROM users_auth WHERE email = ?", (payload.email,))
    if not user_rows:
        raise HTTPException(400, "Utilisateur introuvable après création")
    user_id = user_rows[0][0]
    token = _new_session(db, user_id)
    return {"token": token, "client_id": client_id}


@app.post("/api/login")
def login(payload: LoginPayload):
    db = _db()
    _ensure_users_tables(db)
    row = db.execute_query(
        "SELECT id, password_hash FROM users_auth WHERE email = ?", (payload.email,)
    )
    if not row:
        raise HTTPException(401, "Identifiants invalides")
    user_id, pwd_hash = row[0]
    if not _verify_password(payload.password, pwd_hash):
        raise HTTPException(401, "Identifiants invalides")
    token = _new_session(db, user_id)
    return {"token": token}

@app.post("/api/logout")
def logout(req: Request):
    db = _db()
    _ensure_users_tables(db)

    token = _get_token(req)
    if token:
        db.execute_commit("DELETE FROM ui_sessions WHERE token = ?", (token,))

    return {"status": "ok"}


@app.get("/api/me")
def me(req: Request):
    db = _db()
    user_id = _require_session(req, db)
    row = db.execute_query(
        "SELECT email, name, client_id, preferences FROM users_auth WHERE id = ?", (user_id,)
    )[0]
    return {
        "email": row[0],
        "name": row[1],
        "client_id": row[2],
        "preferences": json.loads(row[3]) if row[3] else {},
    }


@app.get("/api/client")
def get_client(req: Request):
    db = _db()
    user_id = _require_session(req, db)
    client_id = db.execute_query("SELECT client_id FROM users_auth WHERE id=?", (user_id,))[0][0]
    all_clients = db.client_manager.get_all_clients(start_driver=False)
    client = all_clients.which_client_by_id(client_id)
    if client is None:
        raise HTTPException(404, "Client manquant")
    return {
        "client_id": client.client_id,
        "engine": client.client_engine.to_dict(),
        "weather": client.client_weather.to_dict(),
        "driver": client.driver.device_to_dict(),
    }


@app.post("/api/client")
def update_client(req: Request, payload: ClientUpdatePayload):
    db = _db()
    user_id = _require_session(req, db)
    client_id = db.execute_query("SELECT client_id FROM users_auth WHERE id=?", (user_id,))[0][0]

    try:
        from optimasol.cli import _build_client_from_json  # reuse logic
        candidate = _build_client_from_json({**payload.client, "id": client_id}, start_driver=False)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, f"Client invalide: {exc}") from exc

    all_clients = db.client_manager.get_all_clients(start_driver=False)
    _ensure_unique_serial(db, _extract_serial(candidate.driver), exclude_client_id=client_id)
    found = False
    new_list = []
    for c in all_clients.list_of_clients:
        if c.client_id == client_id:
            new_list.append(candidate)
            found = True
        else:
            new_list.append(c)
    if not found:
        new_list.append(candidate)
    all_clients.list_of_clients = new_list
    all_clients.clients_with_leaders = [(c, all_clients._closest_leader(c) or c) for c in new_list]
    all_clients.leaders = list({pair[1] for pair in all_clients.clients_with_leaders})

    db.client_manager.store_all_clients(all_clients)
    return {"status": "ok"}


@app.get("/api/home/status")
def home_status(req: Request):
    db = _db()
    user_id = _require_session(req, db)
    client_id = db.execute_query("SELECT client_id FROM users_auth WHERE id=?", (user_id,))[0][0]

    now_utc = datetime.now(timezone.utc)
    pid = _read_service_pid()
    process_running = _is_process_alive(pid)

    serial = None
    try:
        cfg_row = db.execute_query("SELECT config_driver FROM users_main WHERE id = ?", (client_id,))
        if cfg_row:
            cfg_driver = json.loads(cfg_row[0][0]) if cfg_row[0][0] else {}
            if isinstance(cfg_driver, dict):
                serial = cfg_driver.get("serial_number")
    except Exception:
        serial = None

    broker_event = _driver_state_from_logs(str(serial) if serial else None)

    # Dernier message routeur reçu (information affichée uniquement, pas utilisée pour le statut).
    temp_ts = None
    prod_ts = None
    power_ts = None
    try:
        temp_row = db.execute_query("SELECT MAX(timestamp) FROM temperatures WHERE id = ?", (client_id,))
        prod_row = db.execute_query("SELECT MAX(timestamp) FROM productions_measurements WHERE id = ?", (client_id,))
        power_row = db.execute_query("SELECT MAX(timestamp) FROM decisions_measurements WHERE id = ?", (client_id,))

        if temp_row and temp_row[0][0]:
            temp_ts = _parse_dt(str(temp_row[0][0]))
        if prod_row and prod_row[0][0]:
            prod_ts = _parse_dt(str(prod_row[0][0]))
        if power_row and power_row[0][0]:
            power_ts = _parse_dt(str(power_row[0][0]))
    except Exception:
        pass

    timestamps = [ts for ts in [temp_ts, prod_ts, power_ts] if ts is not None]
    last_router_message = max(timestamps) if timestamps else None

    if not process_running:
        driver_state = "process_disabled"
        broker_connected = None
    elif broker_event.get("state") == "activated":
        driver_state = "activated"
        broker_connected = True
    else:
        driver_state = "failed"
        broker_connected = False

    return {
        "process": {
            "running": process_running,
            "pid": pid,
            "checked_at": now_utc.isoformat(),
        },
        "driver": {
            "state": driver_state,
            "broker_connected": broker_connected,
            "serial_number": serial,
            "last_message_at": last_router_message.isoformat() if last_router_message else None,
            "last_broker_event_at": broker_event.get("event_at"),
            "last_temperature_at": temp_ts.isoformat() if temp_ts else None,
            "last_production_at": prod_ts.isoformat() if prod_ts else None,
            "last_power_at": power_ts.isoformat() if power_ts else None,
        },
    }


@app.get("/api/home/forecast/today")
def home_forecast_today(req: Request):
    db = _db()
    user_id = _require_session(req, db)
    client_id = db.execute_query("SELECT client_id FROM users_auth WHERE id=?", (user_id,))[0][0]

    now_local = datetime.now().astimezone()
    tz_local = now_local.tzinfo or timezone.utc
    start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    end_local = start_local + timedelta(days=1)
    start_utc = start_local.astimezone(timezone.utc)
    end_utc = end_local.astimezone(timezone.utc)

    rows = db.execute_query(
        """
        SELECT timestamp, production
        FROM Productions
        WHERE id = ? AND timestamp >= ? AND timestamp < ?
        ORDER BY timestamp ASC
        """,
        (client_id, start_utc.isoformat(), end_utc.isoformat()),
    )

    points = []
    last_forecast_point = None
    for ts_raw, production_raw in rows:
        ts = _parse_dt(str(ts_raw))
        if ts is None:
            continue
        ts_utc = ts.astimezone(timezone.utc)
        try:
            production = float(production_raw)
        except Exception:
            continue
        points.append({"timestamp": ts_utc.isoformat(), "production": production})
        last_forecast_point = ts_utc

    return {
        "date_local": str(start_local.date()),
        "timezone": str(tz_local),
        "start_utc": start_utc.isoformat(),
        "end_utc": end_utc.isoformat(),
        "points": points,
        "last_forecast_point_at": last_forecast_point.isoformat() if last_forecast_point else None,
        "refreshed_at": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/history")
def history(req: Request):
    db = _db()
    user_id = _require_session(req, db)
    client_id = db.execute_query("SELECT client_id FROM users_auth WHERE id=?", (user_id,))[0][0]
    temps = db.getter.get_temperatures(client_id, 200).to_dict(orient="records")
    prod_meas = db.getter.get_production_measured(client_id, 200).to_dict(orient="records")
    decisions = db.getter.get_decisions(client_id, 200).to_dict(orient="records")
    prod_forecast = db.getter.get_production_forecast(client_id, 200).to_dict(orient="records")
    return {
        "temperatures": temps,
        "production_measured": prod_meas,
        "decisions": decisions,
        "production_forecast": prod_forecast,
    }


@app.get("/api/history/temperature")
def history_temperature(req: Request, start: str | None = None, end: str | None = None, limit: int | None = 500):
    db = _db()
    user_id = _require_session(req, db)
    client_id = db.execute_query("SELECT client_id FROM users_auth WHERE id=?", (user_id,))[0][0]
    df = db.getter.get_temperatures(client_id, limit)
    start_dt = _parse_dt(start)
    end_dt = _parse_dt(end)
    if start_dt:
        df = df[df.index >= start_dt]
    if end_dt:
        df = df[df.index <= end_dt]
    items = []
    for ts, row in df.iterrows():
        items.append({"timestamp": ts.isoformat(), "temperature": row["temperature"]})
    return {"temperatures": items}


@app.get("/api/summary")
def summary(req: Request):
    db = _db()
    user_id = _require_session(req, db)
    client_id = db.execute_query("SELECT client_id FROM users_auth WHERE id=?", (user_id,))[0][0]
    temp_df = db.getter.get_temperatures(client_id, 1)
    prod_df = db.getter.get_production_measured(client_id, 1)
    forecast_df = db.getter.get_production_forecast(client_id, 1)
    decision_df = db.getter.get_decisions(client_id, 1)
    return {
        "temperature": _last_df_value(temp_df, "temperature"),
        "production_measured": _last_df_value(prod_df, "production"),
        "production_forecast": _last_df_value(forecast_df, "production"),
        "decision": _last_df_value(decision_df, "decision"),
    }


@app.post("/api/password/change")
def password_change(req: Request, payload: PasswordChangePayload):
    db = _db()
    user_id = _require_session(req, db)
    row = db.execute_query(
        "SELECT password_hash FROM users_auth WHERE id = ?", (user_id,)
    )
    if not row:
        raise HTTPException(404, "Utilisateur introuvable")
    pwd_hash = row[0][0]
    if not _verify_password(payload.current_password, pwd_hash):
        raise HTTPException(401, "Mot de passe actuel invalide")
    new_hash = _hash_password(payload.new_password)
    db.execute_commit(
        "UPDATE users_auth SET password_hash = ? WHERE id = ?",
        (new_hash, user_id),
    )
    return {"status": "ok"}


# -------- Static files ----------

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
