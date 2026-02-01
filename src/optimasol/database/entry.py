from pathlib import Path
import sqlite3
from .client_manager import ClientManager
from .getters import Getter
from .reporters import Reporter

class DBManager:
    def __init__(self, path_db: Path):
        """
        BUT : 
        Initialiser l'orchestrateur de la base de données. C'est le point d'entrée unique 
        pour toute l'application. Il instancie les sous-modules (Getter, Reporter, ClientManager)
        en leur donnant accès à ses propres méthodes d'exécution.

        ARGUMENTS :
        - path_db (Path) : Chemin absolu ou relatif vers le fichier .db (ex: 'data/database.db').

        ÉTAPES :
        1. Stocker path_db dans self.path_db.
        2. Appeler self._initialize_db() pour s'assurer que le fichier et les tables existent.
        3. Instancier self.client_manager = ClientManager(db_manager=self).
           Note : On passe 'self' pour que le ClientManager puisse utiliser nos méthodes execute.
        4. Instancier self.reporter = Reporter(db_manager=self).
        5. Instancier self.getter = Getter(db_manager=self).
        """
        self.path_db = Path(path_db)
        self.path = self.path_db  # Alias pratique pour les appels externes éventuels

        # On s'assure que le dossier existe pour pouvoir créer le fichier SQLite
        self.path_db.parent.mkdir(parents=True, exist_ok=True)

        # Préparation du fichier et des tables
        self._initialize_db()

        # Sous-modules
        self.client_manager = ClientManager(db_manager=self)
        self.reporter = Reporter(db_manager=self)
        self.getter = Getter(db_manager=self)

        # Alias vers les méthodes utiles des sous-modules (pour compatibilité avec le reste du projet)
        self.get_all_clients_engine = self.client_manager.get_all_clients
        self.update_db_service = self.client_manager.store_all_clients
        self.update_table_client_ui = self.client_manager.store_all_clients

        self.report_temperature = self.reporter.report_temperature
        self.report_production_forecast = self.reporter.report_production_forecast
        self.report_production_measured = self.reporter.report_production_measured
        self.report_decision_taken = self.reporter.report_decision_taken
        self.report_decision_measured = self.reporter.report_decision_measured

        self.get_temperatures = self.getter.get_temperatures
        self.get_productions_forecasts = self.getter.get_production_forecast
        self.get_productions_measured = self.getter.get_production_measured
        self.get_decisions_taken = self.getter.get_decisions
        self.get_decisions = self.getter.get_decisions

    def _get_connection(self) -> sqlite3.Connection:
        """
        BUT : 
        Méthode utilitaire privée (interne). Crée et renvoie un objet connexion brut vers SQLite.
        Active impérativement les Foreign Keys.

        RETOUR :
        - conn (sqlite3.Connection) : L'objet de connexion ouvert.

        ÉTAPES :
        1. Créer la connexion avec sqlite3.connect(self.path_db).
        2. Exécuter la commande SQL "PRAGMA foreign_keys = ON;" pour garantir l'intégrité des données
           (pour que les cascades ON DELETE fonctionnent).
        3. Renvoyer l'objet conn.
        """
        conn = sqlite3.connect(self.path_db)
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _initialize_db(self) -> None:
        """
        BUT : 
        S'assurer que la structure de la base de données (Tables) est prête à l'emploi.
        Si le fichier n'existe pas ou est vide, il applique le schéma SQL.

        ÉTAPES :
        1. Localiser le fichier 'schema.sql' (généralement dans le même dossier que ce script).
        2. Lire le contenu texte du fichier 'schema.sql'.
        3. Ouvrir une connexion via self._get_connection().
        4. Exécuter le script SQL complet (executescript) pour créer les tables (Drivers, users_main, etc.)
           si elles n'existent pas (IF NOT EXISTS).
        5. Fermer la connexion.
        """
        schema_path = Path(__file__).resolve().parent / "schema.sql"
        with open(schema_path, "r", encoding="utf-8") as f:
            schema_sql = f.read()

        conn = self._get_connection()
        try:
            conn.executescript(schema_sql)
        finally:
            conn.close()

    def execute_query(self, query: str, params: tuple = ()) -> list:
        """
        BUT : 
        Exécuter une requête de lecture (SELECT) et renvoyer les résultats bruts.
        Utilisée par Getter et ClientManager.

        ARGUMENTS :
        - query (str) : La requête SQL (ex: "SELECT * FROM Drivers WHERE id=?").
        - params (tuple) : Les paramètres à injecter pour éviter les injections SQL (ex: (12,)).

        RETOUR :
        - results (list) : Une liste de tuples correspondant aux lignes trouvées.

        ÉTAPES :
        1. Utiliser un Context Manager (with self._get_connection() as conn) pour gérer ouverture/fermeture.
        2. Créer un curseur.
        3. Exécuter cursor.execute(query, params).
        4. Récupérer tous les résultats avec cursor.fetchall().
        5. Retourner les résultats.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            results = cursor.fetchall()
        return results

    def execute_commit(self, query: str, params: tuple = ()) -> None:
        """
        BUT : 
        Exécuter une requête d'écriture (INSERT, UPDATE, DELETE).
        Gère le commit (sauvegarde) automatique.
        Utilisée par Reporter et ClientManager.

        ARGUMENTS :
        - query (str) : La requête SQL.
        - params (tuple) : Les valeurs à insérer/modifier.

        ÉTAPES :
        1. Utiliser un Context Manager (with self._get_connection() as conn).
        2. Créer un curseur.
        3. Exécuter cursor.execute(query, params).
        4. La méthode __exit__ du Context Manager validera automatiquement le commit (conn.commit()).
           Si une erreur survient, elle fera un rollback.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
