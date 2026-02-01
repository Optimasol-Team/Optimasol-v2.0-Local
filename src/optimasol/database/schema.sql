-- schema.sql (SQLite)
PRAGMA foreign_keys = ON;



-- ========== Drivers ==========
CREATE TABLE IF NOT EXISTS Drivers (
    driver_id   INTEGER PRIMARY KEY,
    nom_driver  TEXT
);

-- ========== users_main ==========
CREATE TABLE IF NOT EXISTS users_main (
    id             INTEGER PRIMARY KEY,
    weather_ref    INTEGER,   -- référence vers le "chef" météo (un autre client)
    config_engine  TEXT,   -- YAML (texte)
    config_weather TEXT,   -- YAML (texte)
    driver_id      INTEGER,
    config_driver  TEXT,   -- YAML (texte)
    Auto_correction INTEGER DEFAULT 0, -- Booléen (0/1) indiquant si la correction automatique est active

    FOREIGN KEY (weather_ref) REFERENCES users_main(id)
        ON UPDATE CASCADE
        ON DELETE SET NULL,

    FOREIGN KEY (driver_id) REFERENCES Drivers(driver_id)
        ON UPDATE CASCADE
        ON DELETE SET NULL
);

-- ========== Decisions ==========
CREATE TABLE IF NOT EXISTS Decisions (
    id        INTEGER NOT NULL,
    timestamp TEXT NOT NULL,   -- date (texte)
    decision  REAL,            -- PUISSANCE APPLIQUÉE (FLOAT)

    PRIMARY KEY (id, timestamp),
    FOREIGN KEY (id) REFERENCES users_main(id)
        ON UPDATE CASCADE
        ON DELETE CASCADE
);

-- ========== Productions ==========
CREATE TABLE IF NOT EXISTS Productions (
    id         INTEGER NOT NULL,
    timestamp  TEXT NOT NULL,  -- date/heure (UTC) (texte)
    production REAL,           -- production prévue

    PRIMARY KEY (id, timestamp),
    FOREIGN KEY (id) REFERENCES users_main(id)
        ON UPDATE CASCADE
        ON DELETE CASCADE
);

-- ========== temperatures ==========
CREATE TABLE IF NOT EXISTS temperatures (
    id          INTEGER NOT NULL,
    temperature REAL,          -- température mesurée
    timestamp   TEXT NOT NULL, -- date/heure (UTC) (texte)

    PRIMARY KEY (id, timestamp),
    FOREIGN KEY (id) REFERENCES users_main(id)
        ON UPDATE CASCADE
        ON DELETE CASCADE
);

-- ========== decisions_measurements ==========
CREATE TABLE IF NOT EXISTS decisions_measurements (
    id        INTEGER NOT NULL,
    decision  REAL,            -- décision mesurée
    timestamp TEXT NOT NULL,   -- date/heure (UTC) (texte)

    PRIMARY KEY (id, timestamp),
    FOREIGN KEY (id) REFERENCES users_main(id)
        ON UPDATE CASCADE
        ON DELETE CASCADE
);

-- ========== productions_measurements ==========
CREATE TABLE IF NOT EXISTS productions_measurements (
    id         INTEGER NOT NULL,
    production REAL,           -- production PV mesurée
    timestamp  TEXT NOT NULL,  -- date/heure (UTC) (texte)

    PRIMARY KEY (id, timestamp),
    FOREIGN KEY (id) REFERENCES users_main(id)
        ON UPDATE CASCADE
        ON DELETE CASCADE
);

-- ========== activation_keys ==========
CREATE TABLE IF NOT EXISTS activation_keys (
    activation_key TEXT PRIMARY KEY,
    client_id      INTEGER NOT NULL,
    status         TEXT DEFAULT 'issued',
    created_at     TEXT NOT NULL,
    expires_at     TEXT,
    used_at        TEXT
);

-- ========== users_auth (GUI accounts) ==========
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

-- ========== ui_sessions ==========
CREATE TABLE IF NOT EXISTS ui_sessions (
    token      TEXT PRIMARY KEY,
    user_id    INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,

    FOREIGN KEY (user_id) REFERENCES users_auth(id)
        ON UPDATE CASCADE
        ON DELETE CASCADE
);
