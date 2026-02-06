class Reporter:
    def __init__(self, db_manager):
        """
        BUT : 
        Fournir des méthodes pour enregistrer les données temporelles (mesures, décisions, prévisions).

        ARGUMENTS :
        - db_manager : Instance de DBManager pour exécuter les INSERT.

        ÉTAPES :
        1. Stocker self.db_manager = db_manager.
        """
        self.db_manager = db_manager

    def report_temperature(self, client_id: int, temperature: float, time: str) -> None:
        """
        BUT : 
        Enregistrer une température mesurée pour un client à un instant T.

        ARGUMENTS :
        - client_id : ID de l'utilisateur concerné.
        - temperature : Valeur flottante.
        - time : Timestamp au format ISO string (UTC).

        ÉTAPES :
        1. Préparer la requête SQL : "INSERT INTO temperatures (id, temperature, timestamp) VALUES (?, ?, ?)".
        2. Appeler self.db_manager.execute_commit(query, (client_id, temperature, time)).
        3. Note : Si le client_id n'existe pas, SQLite lèvera une IntegrityError (grâce aux Foreign Keys).
           On peut laisser planter ou catcher l'erreur selon la stratégie voulue.
        """
        ts = time.isoformat() if hasattr(time, "isoformat") else str(time)
        query = """
            INSERT INTO temperatures (id, temperature, timestamp)
            VALUES (?, ?, ?)
            ON CONFLICT(id, timestamp) DO UPDATE SET
                temperature = excluded.temperature
        """
        self.db_manager.execute_commit(query, (client_id, temperature, ts))
    
    def report_production_forecast(self, client_id: int, production_forecast: float, time: str) -> None:
        """
        BUT : 
        Enregistrer une prévision de production solaire.
        Si une prévision existe déjà pour ce couple (id, timestamp), elle doit être mise à jour ou écrasée.

        ARGUMENTS :
        - production_forecast : La puissance prévue (Watts).
        - time : Timestamp ISO.

        ÉTAPES :
        1. Préparer la requête SQL : "INSERT OR REPLACE INTO Productions (id, timestamp, production) VALUES (?, ?, ?)".
           'INSERT OR REPLACE' permet d'écraser une vieille prévision par une nouvelle plus fraîche.
        2. Appeler self.db_manager.execute_commit(...).
        """
        ts = time.isoformat() if hasattr(time, "isoformat") else str(time)
        query = "INSERT OR REPLACE INTO Productions (id, timestamp, production) VALUES (?, ?, ?)"
        self.db_manager.execute_commit(query, (client_id, production_forecast, ts))
    
    def report_production_measured(self, client_id: int, production_measured: float, time: str) -> None:
        """
        BUT : 
        Enregistrer la production réelle mesurée par le hardware.
        Table cible : productions_measurements.

        ÉTAPES :
        1. Requête INSERT INTO productions_measurements (id, production, timestamp).
        2. Exécution via db_manager.
        """
        ts = time.isoformat() if hasattr(time, "isoformat") else str(time)
        query = """
            INSERT INTO productions_measurements (id, production, timestamp)
            VALUES (?, ?, ?)
            ON CONFLICT(id, timestamp) DO UPDATE SET
                production = excluded.production
        """
        self.db_manager.execute_commit(query, (client_id, production_measured, ts))
    
    def report_decision_taken(self, client_id: int, decision: float, time: str) -> None:
        """
        BUT : 
        Enregistrer l'ordre envoyé par l'algorithme (la consigne).
        Table cible : Decisions.

        ÉTAPES :
        1. Requête INSERT OR REPLACE INTO Decisions (id, timestamp, decision).
        2. Exécution via db_manager.
        """
        ts = time.isoformat() if hasattr(time, "isoformat") else str(time)
        query = "INSERT OR REPLACE INTO Decisions (id, timestamp, decision) VALUES (?, ?, ?)"
        self.db_manager.execute_commit(query, (client_id, decision, ts))
    
    def report_decision_measured(self, client_id: int, decision: float, time: str) -> None:
        """
        BUT : 
        Enregistrer ce que le système a réellement fait (retour d'état du driver).
        Parfois différent de la décision prise si le matériel sature ou ne répond pas.
        Table cible : decisions_measurements.

        ÉTAPES :
        1. Requête INSERT INTO decisions_measurements (id, decision, timestamp).
        2. Exécution via db_manager.
        """
        ts = time.isoformat() if hasattr(time, "isoformat") else str(time)
        query = """
            INSERT INTO decisions_measurements (id, decision, timestamp)
            VALUES (?, ?, ?)
            ON CONFLICT(id, timestamp) DO UPDATE SET
                decision = excluded.decision
        """
        self.db_manager.execute_commit(query, (client_id, decision, ts))
