import pandas as pd

class Getter:
    def __init__(self, db_manager):
        """
        BUT : 
        Récupérer des historiques de données sous forme de DataFrames Pandas, prêts pour le calcul.

        ARGUMENTS :
        - db_manager : Instance de DBManager pour exécuter les SELECT.

        ÉTAPES :
        1. Stocker self.db_manager.
        """
        self.db_manager = db_manager
    
    def get_production_forecast(self, client_id: int, number: int = None) -> pd.DataFrame:
        """
        BUT : 
        Récupérer l'historique ou le futur des prévisions de production stockées.

        ARGUMENTS :
        - client_id : L'ID de l'utilisateur.
        - number (int, optionnel) : Le nombre de points les plus récents à récupérer.
          Si None, on récupère tout l'historique.

        RETOUR :
        - DataFrame Pandas avec colonnes : ['Datetime', 'production'].
          L'index doit être le Datetime converti en objets datetime.

        ÉTAPES :
        1. Construire la requête SQL de base : 
           "SELECT timestamp, production FROM Productions WHERE id = ? ORDER BY timestamp DESC".
        2. Si 'number' est défini, ajouter " LIMIT ?" à la requête.
        3. Exécuter self.db_manager.execute_query().
        4. Si le résultat est vide, renvoyer un DataFrame vide avec les bonnes colonnes.
        5. Sinon, charger la liste de tuples dans un DataFrame Pandas.
        6. Convertir la colonne 'timestamp' en datetime objects.
        7. Trier le DataFrame par ordre chronologique (sort_values).
        8. Renvoyer le DF.
        """
        base_query = "SELECT timestamp, production FROM Productions WHERE id = ? ORDER BY timestamp DESC"
        params = (client_id,)
        if number is not None:
            base_query += " LIMIT ?"
            params = (client_id, number)

        results = self.db_manager.execute_query(base_query, params)

        if not results:
            return pd.DataFrame(columns=["Datetime", "production"])

        df = pd.DataFrame(results, columns=["timestamp", "production"])
        df["Datetime"] = pd.to_datetime(df["timestamp"], utc=True)
        df = df.drop(columns=["timestamp"])
        df = df[["Datetime", "production"]].sort_values("Datetime")
        df = df.set_index("Datetime")
        return df
    
    def get_production_measured(self, client_id: int, number: int = None) -> pd.DataFrame:
        """
        BUT : 
        Récupérer l'historique des productions réelles mesurées.

        ÉTAPES :
        1. Requête sur la table 'productions_measurements'.
        2. Logique identique à get_production_forecast (SELECT, LIMIT, conversion Pandas).
        """
        base_query = "SELECT timestamp, production FROM productions_measurements WHERE id = ? ORDER BY timestamp DESC"
        params = (client_id,)
        if number is not None:
            base_query += " LIMIT ?"
            params = (client_id, number)

        results = self.db_manager.execute_query(base_query, params)

        if not results:
            return pd.DataFrame(columns=["Datetime", "production"])

        df = pd.DataFrame(results, columns=["timestamp", "production"])
        df["Datetime"] = pd.to_datetime(df["timestamp"], utc=True)
        df = df.drop(columns=["timestamp"])
        df = df[["Datetime", "production"]].sort_values("Datetime")
        df = df.set_index("Datetime")
        return df

    def get_temperatures(self, client_id: int, number: int = None) -> pd.DataFrame:
        """
        BUT : 
        Récupérer l'historique des températures (utile pour le machine learning ou l'analyse thermique).

        ÉTAPES :
        1. Requête sur la table 'temperatures'.
        2. Retourner un DataFrame ['Datetime', 'temperature'].
        """
        base_query = "SELECT timestamp, temperature FROM temperatures WHERE id = ? ORDER BY timestamp DESC"
        params = (client_id,)
        if number is not None:
            base_query += " LIMIT ?"
            params = (client_id, number)

        results = self.db_manager.execute_query(base_query, params)

        if not results:
            return pd.DataFrame(columns=["Datetime", "temperature"])

        df = pd.DataFrame(results, columns=["timestamp", "temperature"])
        df["Datetime"] = pd.to_datetime(df["timestamp"], utc=True)
        df = df.drop(columns=["timestamp"])
        df = df[["Datetime", "temperature"]].sort_values("Datetime")
        df = df.set_index("Datetime")
        return df

    def get_decisions(self, client_id: int, number: int = None) -> pd.DataFrame:
        """
        BUT : 
        Récupérer l'historique des décisions prises par l'algorithme.

        ÉTAPES :
        1. Requête sur la table 'Decisions'.
        2. Retourner un DataFrame ['Datetime', 'decision'].
        """
        base_query = "SELECT timestamp, decision FROM Decisions WHERE id = ? ORDER BY timestamp DESC"
        params = (client_id,)
        if number is not None:
            base_query += " LIMIT ?"
            params = (client_id, number)

        results = self.db_manager.execute_query(base_query, params)

        if not results:
            return pd.DataFrame(columns=["Datetime", "decision"])

        df = pd.DataFrame(results, columns=["timestamp", "decision"])
        df["Datetime"] = pd.to_datetime(df["timestamp"], utc=True)
        df = df.drop(columns=["timestamp"])
        df = df[["Datetime", "decision"]].sort_values("Datetime")
        df = df.set_index("Datetime")
        return df
