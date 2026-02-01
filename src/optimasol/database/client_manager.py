import json

from ..core import AllClients
from ..core.client_model import Client
from optimiser_engine import Client as EngineClient
from weather_manager import Client as WeatherClient

class ClientManager:
    def __init__(self, db_manager):
        """
        BUT : 
        Gérer la persistance des configurations clients.

        ARGUMENTS :
        - db_manager : Une instance de la classe DBManager (passée par entry.py). 
          Cela permet d'appeler db_manager.execute_query().

        ÉTAPES :
        1. Stocker self.db_manager = db_manager.
        """
        self.db_manager = db_manager

    def get_all_clients(self) -> AllClients:
        """
        BUT : 
        Reconstruire l'objet complexe AllClients à partir des tables relationnelles SQL.
        C'est le "chargement" de l'état initial du système au démarrage.

        RETOUR :
        - un objet de type AllClients (défini dans core).

        ÉTAPES :
        1. Exécuter une requête SELECT sur la table 'users_main' via self.db_manager.execute_query.
           Récupérer id, configs, weather_ref, driver_id.
        2. Pour chaque ligne (chaque client) :
             a. Parser les configs (JSON text) en dictionnaires Python.
             b. Si driver_id est présent, faire une requête SELECT sur la table 'Drivers' pour avoir le nom.
             c. Instancier les objets métier (Client_eng, Client_wea, Driver).
             d. Créer l'objet Client global.
        3. Gérer les dépendances météo (si un client dépend d'un autre pour la météo).
        4. Assembler le tout dans un objet AllClients.
        5. Retourner cet objet.
        """
        rows = self.db_manager.execute_query(
            "SELECT id, weather_ref, config_engine, config_weather, driver_id, config_driver FROM users_main"
        )

        # Aucun client enregistré
        if not rows:
            return AllClients()

        try:
            from ..drivers import ALL_DRIVERS
        except ImportError as exc:
            raise ImportError("Impossible de charger les drivers (fichier de configuration manquant ?)") from exc

        # On récupère le mapping driver_id -> nom_driver depuis la table Drivers
        driver_rows = self.db_manager.execute_query("SELECT driver_id, nom_driver FROM Drivers")
        driver_names = {rid: name for rid, name in driver_rows}

        # Préparation des mappings pour retrouver la classe driver à partir de l'ID ou du nom
        driver_by_id = {drv.DRIVER_TYPE_ID: drv for drv in ALL_DRIVERS if hasattr(drv, "DRIVER_TYPE_ID")}
        driver_by_name = {}
        for drv in ALL_DRIVERS:
            try:
                defn = drv.get_driver_def()
                drv_name = defn.get("id") or defn.get("name") or drv.__name__
            except Exception:
                drv_name = drv.__name__
            driver_by_name[drv_name] = drv

        clients = {}
        weather_refs = {}

        for row in rows:
            client_id, weather_ref, cfg_engine, cfg_weather, driver_id, cfg_driver = row

            # Engine
            engine_payload = json.loads(cfg_engine) if cfg_engine else {}
            client_engine = EngineClient.from_dict(engine_payload)
            client_engine.client_id = client_id

            # Weather
            weather_data = json.loads(cfg_weather) if cfg_weather else {}
            client_weather = WeatherClient.from_dict(weather_data)
            client_weather.client_id = client_id

            # Driver
            if driver_id is None:
                raise ValueError(f"Driver manquant pour le client {client_id}")

            driver_name = driver_names.get(driver_id)
            driver_cls = driver_by_id.get(driver_id)
            if driver_cls is None and driver_name is not None:
                driver_cls = driver_by_name.get(driver_name)
            if driver_cls is None:
                raise ValueError(f"Driver inconnu pour l'ID {driver_id} (nom='{driver_name}')")

            driver_conf = json.loads(cfg_driver) if cfg_driver else {}
            driver_obj = driver_cls.dict_to_device(driver_conf)

            client_obj = Client(
                client_id=client_id,
                client_engine=client_engine,
                client_weather=client_weather,
                driver=driver_obj,
            )

            clients[client_id] = client_obj
            weather_refs[client_id] = weather_ref

        # Reconstruction de AllClients sans recalculer les leaders par distance
        all_clients = AllClients()
        all_clients.list_of_clients = [clients[key] for key in sorted(clients.keys())]

        clients_with_leaders = []
        leaders = []
        seen_leaders = set()

        for client_id in sorted(clients.keys()):
            client_obj = clients[client_id]
            leader_id = weather_refs.get(client_id)
            if leader_id is None:
                leader_id = client_id  # Le client est son propre leader météo

            leader_obj = clients.get(leader_id, client_obj)
            clients_with_leaders.append((client_obj, leader_obj))

            if leader_obj.client_id not in seen_leaders:
                leaders.append(leader_obj)
                seen_leaders.add(leader_obj.client_id)

        all_clients.clients_with_leaders = clients_with_leaders
        all_clients.leaders = leaders

        return all_clients

    def update_client_weather(self, client_id: int, client_weather: WeatherClient) -> None:
        """
        BUT :
        Mettre à jour la configuration météo (YAML) d'un client dans la base.

        ARGUMENTS :
        - client_id : Identifiant du client à mettre à jour.
        - client_weather : Objet WeatherClient (weather_manager.Client) déjà configuré.

        ÉTAPES :
        1. Sérialiser client_weather en JSON (via to_dict).
        2. Exécuter un UPDATE sur la colonne config_weather de users_main pour l'id donné.
        """
        if not isinstance(client_weather, WeatherClient):
            raise TypeError("client_weather doit être une instance de weather_manager.Client")

        config_weather_yaml = json.dumps(client_weather.to_dict())
        self.db_manager.execute_commit(
            "UPDATE users_main SET config_weather = ? WHERE id = ?",
            (config_weather_yaml, client_id),
        )

    def get_auto_correction(self, client_id: int) -> bool:
        """
        BUT :
        Lire la valeur booléenne Auto_correction pour un client donné.

        ARGUMENTS :
        - client_id : Identifiant du client.

        RETOUR :
        - bool : True si Auto_correction vaut 1, False sinon (ou si absent).
        """
        rows = self.db_manager.execute_query(
            "SELECT Auto_correction FROM users_main WHERE id = ?",
            (client_id,),
        )
        if not rows:
            raise ValueError(f"Client id {client_id} introuvable dans users_main")
        value = rows[0][0]
        return bool(value)
    
    def store_all_clients(self, all_clients: AllClients) -> None:
        """
        BUT : 
        Sauvegarder l'état complet des clients dans la base. 
        Utile lors de l'initialisation ou si la configuration change dynamiquement.

        ARGUMENTS :
        - all_clients : L'objet contenant toute la configuration actuelle en mémoire.

        ÉTAPES :
        1. Pour chaque client dans all_clients :
             a. Sérialiser les configurations (Engine, Weather, Driver) en format JSON string.
             b. Vérifier si le Driver existe dans la table 'Drivers', sinon l'insérer (INSERT OR IGNORE).
             c. Préparer la requête INSERT OR REPLACE INTO users_main.
             d. Exécuter la requête via self.db_manager.execute_commit() avec les paramètres 
                (id, weather_ref, config_engine_yaml, config_weather_yaml, driver_id, ...).
        """
        for client in all_clients.list_of_clients:
            client_id = client.client_id

            # Leader météo (None si le client est leader lui-même)
            leader_id = all_clients.leader_id_of_client(client)
            weather_ref = leader_id if leader_id != client_id else None

            # Sérialisation Engine / Weather
            config_engine_yaml = json.dumps(client.client_engine.to_dict())
            config_weather_yaml = json.dumps(client.client_weather.to_dict())

            # Sérialisation Driver
            driver = client.driver
            driver_id = getattr(driver, "DRIVER_TYPE_ID", None)
            if driver_id is None:
                raise ValueError(f"Le driver du client {client_id} n'a pas de DRIVER_TYPE_ID défini.")

            try:
                driver_name = driver.get_driver_def().get("id") or driver.get_driver_def().get("name")
            except Exception:
                driver_name = driver.__class__.__name__

            config_driver_yaml = json.dumps(driver.device_to_dict())

            # 1) S'assurer que le driver est répertorié
            self.db_manager.execute_commit(
                "INSERT OR IGNORE INTO Drivers (driver_id, nom_driver) VALUES (?, ?)",
                (driver_id, driver_name),
            )

            # 2) Insérer / Mettre à jour le client
            self.db_manager.execute_commit(
                """
                INSERT OR REPLACE INTO users_main (id, weather_ref, config_engine, config_weather, driver_id, config_driver)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (client_id, weather_ref, config_engine_yaml, config_weather_yaml, driver_id, config_driver_yaml),
            )
