-- database/schema.sql

-- 1. Configuration du moteur SQLite
-- Active le mode WAL pour permettre la lecture (UI) et l'écriture (Service 24h) simultanées
PRAGMA journal_mode=WAL;
-- Active la vérification des clés étrangères (Foreign Keys)
PRAGMA foreign_keys = ON;


-- 2. Table UTILISATEURS / CLIENTS
-- Cette table centralise tout : config technique, driver, et accès UI.
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,          -- UUID généré ou ID unique
    
    -- Identification & UI
    name TEXT,                    -- Nom affiché (ex: "Maison Anas")
    email TEXT UNIQUE,            -- Email pour login (Unique pour éviter doublons)
    hash TEXT,                    -- Hash du mot de passe (Werkzeug)
    
    -- Configurations Métier (Stockées en JSON pour flexibilité)
    config_engine TEXT,           -- Paramètres du ballon/résistance (JSON)
    config_weather TEXT,          -- Paramètres géo/toiture (JSON)
    config_ui TEXT,               -- Préférences d'affichage (JSON)
    config_driver TEXT,           -- Paramètres de connexion driver (IP, Serial...) (JSON)
    
    -- Liens techniques
    driver_id TEXT,               -- ID du type de driver (ex: "smart_electromation_mqtt")
    weather_ref TEXT              -- ID du client "Leader" météo (ou lui-même)
);


-- 3. Tables de MESURES (Données chaudes / Historique)
-- Séparées pour la performance des graphiques.

-- Historique des températures mesurées par le driver
CREATE TABLE IF NOT EXISTS temperatures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id TEXT NOT NULL,
    temperature REAL,
    timestamp TEXT NOT NULL,      -- Format ISO8601 (YYYY-MM-DDTHH:MM:SS)
    FOREIGN KEY(client_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Historique de la production solaire mesurée par le driver
CREATE TABLE IF NOT EXISTS productions_measures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id TEXT NOT NULL,
    production REAL,
    timestamp TEXT NOT NULL,
    FOREIGN KEY(client_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Historique des décisions (Puissance envoyée) mesurées/confirmées par le driver
CREATE TABLE IF NOT EXISTS decisions_measures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id TEXT NOT NULL,
    decision REAL,                -- Valeur entre 0.0 et 1.0 (ou Watt selon config)
    timestamp TEXT NOT NULL,
    FOREIGN KEY(client_id) REFERENCES users(id) ON DELETE CASCADE
);


-- 4. Tables CALCULS & PRÉVISIONS (Intelligence)

-- Historique des prévisions météo utilisées (pour comparaison après coup)
CREATE TABLE IF NOT EXISTS forecasts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id TEXT NOT NULL,
    production REAL,              -- Production estimée
    timestamp TEXT NOT NULL,
    FOREIGN KEY(client_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Historique des ordres donnés par l'algorithme d'optimisation
CREATE TABLE IF NOT EXISTS decisions_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id TEXT NOT NULL,
    decision_report REAL,         -- La décision calculée (peut être stockée en JSON si complexe)
    timestamp TEXT NOT NULL,
    FOREIGN KEY(client_id) REFERENCES users(id) ON DELETE CASCADE
);


-- 5. INDEX (Optimisation des performances UI)
-- Accélère le chargement des graphiques "WHERE client_id = ? AND timestamp > ?"
CREATE INDEX IF NOT EXISTS idx_temp_time ON temperatures(client_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_prod_time ON productions_measures(client_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_dec_meas_time ON decisions_measures(client_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_forecast_time ON forecasts(client_id, timestamp);