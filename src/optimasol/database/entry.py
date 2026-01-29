import sqlite3
import pandas as pd
import json
import uuid
from pathlib import Path
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

from ..paths import DEFAULT_DB_PATH, ensure_runtime_dirs

# Imports du projet
from ..core import AllClients
from ..core.client_model import Client
# Import des drivers pour la Factory
from ..drivers import ALL_DRIVERS
# Imports des modules métier (Engine et Weather)
# On utilise des imports relatifs (..) car optimiser_engine est au même niveau que database
from optimiser_engine import Client as Clt_engine
from weather_manager import Client as Clt_weather

class DBManager:
    def __init__(self, path_db: Path = None):
        if path_db is None:
            # Par défaut : dossier data/ à la racine du projet
            self._path = DEFAULT_DB_PATH
        else:
            self._path = path_db
            
        # Création du dossier si inexistant
        ensure_runtime_dirs()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialisation du schéma
        self._init_db()

    @property
    def path(self):
        return self._path

    @path.setter
    def path(self, valeur: Path):
        if not isinstance(valeur, Path):
            raise TypeError("Il faut indiquer le path sous forme de PATH")
        self._path = valeur

    def _get_conn(self):
        # check_same_thread=False est VITAL pour le service 24h + UI
        return sqlite3.connect(self._path, check_same_thread=False)

    def _init_db(self):
        """Lit et exécute le fichier schema.sql"""
        schema_path = Path(__file__).parent / "schema.sql"
        if not schema_path.exists():
            print("⚠️ Pas de schema.sql trouvé. Assure-toi que la DB est initialisée.")
            return

        conn = self._get_conn()
        try:
            with open(schema_path, 'r', encoding='utf-8') as f:
                conn.executescript(f.read())
            conn.commit()
        except Exception as e:
            print(f"Erreur Init DB: {e}")
        finally:
            conn.close()

    # =========================================================================
    #  FACTORY DRIVERS
    # =========================================================================
    
    def _get_driver_class(self, driver_id_str: str):
        """Retrouve la classe du driver à partir de son ID string"""
        for driver_cls in ALL_DRIVERS:
            # On vérifie l'ID défini dans la méthode statique get_driver_def()
            if driver_cls.get_driver_def()["id"] == driver_id_str:
                return driver_cls
        raise ValueError(f"Driver inconnu : {driver_id_str}")

    def _instantiate_driver(self, driver_id_str: str, config_dict: dict):
        """Reconstruit un driver depuis sa config (dict) stockée en BDD"""
        driver_cls = self._get_driver_class(driver_id_str)
        # On utilise la méthode de classe dict_to_device du driver
        return driver_cls.dict_to_device(config_dict)

    def get_available_drivers(self) -> list:
        """Pour l'UI : liste des drivers disponibles"""
        available = []
        for d in ALL_DRIVERS:
            available.append(d.get_driver_def())
        return available

    # =========================================================================
    #  CHARGEMENT (Load State) -> Dict vers Objets
    # =========================================================================

    def get_all_clients_engine(self) -> AllClients:
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        manager = AllClients()
        
        try:
            rows = conn.execute("SELECT * FROM users").fetchall()
            for row in rows:
                try:
                    # 1. Récupération des dictionnaires (JSON -> Dict)
                    # On gère le cas où le champ est vide (None)
                    dict_engine = json.loads(row['config_engine']) if row['config_engine'] else {}
                    dict_weather = json.loads(row['config_weather']) if row['config_weather'] else {}
                    dict_driver = json.loads(row['config_driver']) if row['config_driver'] else {}
                    
                    # 2. Conversion Dict -> Objet (via from_dict)
                    obj_engine = Clt_engine.from_dict(dict_engine)
                    obj_weather = Clt_weather.from_dict(dict_weather)
                    
                    # 3. Driver : ID + Dict -> Objet
                    driver_id = row['driver_id']
                    obj_driver = self._instantiate_driver(driver_id, dict_driver)
                    
                    # 4. Création du Client complet
                    client = Client(
                        client_id=row['id'],
                        client_engine=obj_engine,
                        client_weather=obj_weather,
                        driver=obj_driver
                    )
                    
                    manager.add(client)
                    
                except Exception as e:
                    print(f"❌ Erreur chargement client {row['id']}: {e}")
                    
        finally:
            conn.close()
            
        return manager

    # =========================================================================
    #  SAUVEGARDE UI (Update Config) -> Objets vers Dict
    # =========================================================================

    def update_table_client_ui(self, client_obj) -> None:
        """Sauvegarde la configuration complète d'un client."""
        conn = self._get_conn()
        try:
            # 1. Conversion Objet -> Dict (via to_dict) -> JSON
            json_engine = json.dumps(client_obj.client_engine.to_dict())
            json_weather = json.dumps(client_obj.client_weather.to_dict())
            json_driver = json.dumps(client_obj.driver.device_to_dict())
            
            # 2. Mise à jour SQL
            conn.execute("""
                UPDATE users SET 
                    config_engine=?, config_weather=?, config_driver=?, 
                    weather_ref=?, driver_id=?
                WHERE id=?
            """, (json_engine, json_weather, json_driver, 
                  client_obj.client_weather.weather_ref, 
                  client_obj.driver.get_driver_def()['id'], 
                  client_obj.client_id))
            conn.commit()
            print(f"✅ Client {client_obj.client_id} sauvegardé.")
        finally:
            conn.close()

    # =========================================================================
    #  CRÉATION (Create) -> Objets par défaut -> Dict
    # =========================================================================

    def create_client_ui(self, name: str, email: str, password: str, driver_type_id: str, serial_number: str) -> str:
        """
        Crée un nouveau client. 
        Instancie des objets par défaut pour générer des JSONs valides.
        """
        new_id = str(uuid.uuid4())
        hashed_pw = generate_password_hash(password)
        
        # A. Création des objets par défaut
        
        # 1. Driver (nécessite le serial number)
        driver_cls = self._get_driver_class(driver_type_id)
        default_driver = driver_cls(serial_number=serial_number) 
        
        # 2. Engine (Moteur par défaut)
        default_engine = Clt_engine() 
        
        # 3. Weather (Météo par défaut)
        default_weather = Clt_weather()

        # B. Conversion en JSON (C'est ta logique : Objet -> Dict -> JSON)
        json_driver = json.dumps(default_driver.device_to_dict())
        json_engine = json.dumps(default_engine.to_dict())
        json_weather = json.dumps(default_weather.to_dict())

        # C. Insertion BDD
        conn = self._get_conn()
        try:
            conn.execute("""
                INSERT INTO users (id, name, email, hash, driver_id, config_engine, config_weather, config_driver, config_ui)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, '{}')
            """, (new_id, name, email, hashed_pw, driver_type_id, json_engine, json_weather, json_driver))
            conn.commit()
            return new_id
        finally:
            conn.close()

    def delete_client_ui(self, client_id: str) -> bool:
        conn = self._get_conn()
        try:
            conn.execute("DELETE FROM users WHERE id = ?", (client_id,))
            conn.commit()
            return True
        finally:
            conn.close()

    # =========================================================================
    #  RUNTIME (Service 24h) -> Snapshot Mesures
    # =========================================================================

    def update_db_service(self, all_clients: AllClients) -> None:
        conn = self._get_conn()
        try:
            for client in all_clients.list_of_clients:
                if client.is_ready:
                    # Enregistrement des mesures si elles existent
                    if client.last_temperature is not None:
                        conn.execute(
                            "INSERT INTO temperatures (client_id, temperature, timestamp) VALUES (?, ?, ?)",
                            (client.client_id, client.last_temperature, client.last_temperature_time.isoformat())
                        )
                    if client.last_production is not None:
                        conn.execute(
                            "INSERT INTO productions_measures (client_id, production, timestamp) VALUES (?, ?, ?)",
                            (client.client_id, client.last_production, client.last_production_time.isoformat())
                        )
            conn.commit()
        finally:
            conn.close()

    # Helpers pour les rapports unitaires
    def report_decision_computed(self, client_id, decision, timestamp):
        self._insert_measure("decisions_history", client_id, decision, timestamp, "decision_report")

    def report_decision_measured(self, client_id, decision_measure, timestamp):
        self._insert_measure("decisions_measures", client_id, decision_measure, timestamp, "decision")

    def report_temperature(self, client_id, temperature, timestamp):
        self._insert_measure("temperatures", client_id, temperature, timestamp, "temperature")
        
    def report_production_measured(self, client_id, production, timestamp):
        self._insert_measure("productions_measures", client_id, production, timestamp, "production")

    def report_production_forecast(self, client_id, production_cast, timestamp):
        self._insert_measure("forecasts", client_id, production_cast, timestamp, "production")

    def _insert_measure(self, table, client_id, value, timestamp, col_name="value"):
        conn = self._get_conn()
        try:
            ts_str = timestamp.isoformat() if hasattr(timestamp, 'isoformat') else str(timestamp)
            conn.execute(f"INSERT INTO {table} (client_id, {col_name}, timestamp) VALUES (?, ?, ?)", 
                         (client_id, value, ts_str))
            conn.commit()
        finally:
            conn.close()

    # =========================================================================
    #  GETTERS (Pandas pour l'UI)
    # =========================================================================
    
    def _get_df(self, query, params):
        conn = self._get_conn()
        try:
            df = pd.read_sql_query(query, conn, params=params)
            if not df.empty and 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
            return df
        finally:
            conn.close()

    def get_temperatures(self, client_id, begin=None, end=None):
        return self._build_query("temperatures", "temperature", client_id, begin, end)
        
    def get_decisions_measured(self, client_id, begin=None, end=None):
        return self._build_query("decisions_measures", "decision", client_id, begin, end)

    def get_decisions_computed(self, client_id, begin=None, end=None):
        return self._build_query("decisions_history", "decision_report", client_id, begin, end)

    def get_productions_measured(self, client_id, begin=None, end=None):
        return self._build_query("productions_measures", "production", client_id, begin, end)

    def get_productions_forecasts(self, client_id, begin=None, end=None):
        return self._build_query("forecasts", "production", client_id, begin, end)

    def _build_query(self, table, col_target, client_id, begin, end):
        query = f"SELECT timestamp, {col_target} FROM {table} WHERE client_id = ?"
        params = [client_id]
        if begin:
            query += " AND timestamp >= ?"
            params.append(begin)
        if end:
            query += " AND timestamp <= ?"
            params.append(end)
        query += " ORDER BY timestamp ASC"
        return self._get_df(query, params)

    # =========================================================================
    #  UI MANAGEMENT (Login & Summary)
    # =========================================================================

    def check_login(self, email: str, password_candidate: str):
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute("SELECT id, hash FROM users WHERE email = ?", (email,)).fetchone()
            if row and check_password_hash(row['hash'], password_candidate):
                return row['id']
            return None
        finally:
            conn.close()

    def get_clients_summary(self) -> list:
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute("SELECT id, name, email, driver_id FROM users").fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()
