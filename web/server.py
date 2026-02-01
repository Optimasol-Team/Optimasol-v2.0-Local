from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel, EmailStr, validator

from optimasol.database import DBManager
from optimasol.default import PROJECT_ROOT
from optimasol.logging_setup import setup_logging
from optimasol.config_loader import load_config_file
from optimasol.core import AllClients

setup_logging()
app = FastAPI(title="Optimasol GUI API")

WEB_ROOT = PROJECT_ROOT / "web"
STATIC_DIR = WEB_ROOT / "static"
TEMPLATE_INDEX = WEB_ROOT / "templates" / "index.html"


# -------- Helpers ----------

def _now_iso():
    return datetime.now(timezone.utc).isoformat()


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


def _db():
    cfg = load_config_file()
    return DBManager(Path(cfg["path_to_db"]["path_to_db"]))


def _ensure_activation_table(db: DBManager):
    db.execute_commit(
        """
        CREATE TABLE IF NOT EXISTS activation_keys (
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


def _new_session(db: DBManager, user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    exp = now + timedelta(hours=12)
    db.execute_commit(
        "INSERT OR REPLACE INTO ui_sessions (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
        (token, user_id, now.isoformat(), exp.isoformat()),
    )
    return token


def _require_session(req: Request, db: DBManager):
    token = req.headers.get("Authorization")
    if not token:
        raise HTTPException(401, "Missing token")
    rows = db.execute_query(
        "SELECT user_id, expires_at FROM ui_sessions WHERE token = ?", (token.strip(),)
    )
    if not rows:
        raise HTTPException(401, "Invalid session")
    user_id, expires_at = rows[0]
    if datetime.fromisoformat(expires_at) < datetime.now(timezone.utc):
        raise HTTPException(401, "Session expired")
    return user_id


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


# -------- Routes ----------


@app.get("/", response_class=HTMLResponse)
def index():
    return FileResponse(TEMPLATE_INDEX)


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
    try:
        from optimasol.cli import _build_client_from_json  # reuse logic
        new_client = _build_client_from_json(payload.client)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, f"Client invalide: {exc}") from exc

    # 3) Persist client
    all_clients = db.client_manager.get_all_clients()
    try:
        all_clients.add(new_client)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, f"Ajout client impossible: {exc}") from exc
    db.client_manager.store_all_clients(all_clients)

    # 4) Mark key used
    db.execute_commit(
        "UPDATE activation_keys SET status='used', used_at=? WHERE activation_key=?",
        (_now_iso(), payload.activation_key),
    )

    # 5) Create auth user
    password_hash = _hash_password(payload.password)
    db.execute_commit(
        "INSERT INTO users_auth (email, name, password_hash, client_id, preferences, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (payload.email, payload.name, password_hash, client_id, json.dumps({}), _now_iso()),
    )
    user_id = db.execute_query("SELECT last_insert_rowid()")[0][0]
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
    all_clients = db.client_manager.get_all_clients()
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
        candidate = _build_client_from_json({**payload.client, "id": client_id})
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, f"Client invalide: {exc}") from exc

    all_clients = db.client_manager.get_all_clients()
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


# -------- Static files ----------

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
