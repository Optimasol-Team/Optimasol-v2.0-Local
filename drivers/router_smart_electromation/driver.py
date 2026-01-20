from ..base_driver import BaseDriver 
import json
from pathlib import Path
import paho.mqtt.client as mqtt

class SmartEMDriver(BaseDriver):
    DRIVER_TYPE_ID = 1 
    @staticmethod 
    def load_mqtt_config(path : Path) :
        try:
            with open(path, 'r') as f:
                config = json.load(f)
            return config
        except Exception as e:
            raise ImportError(f"Erreur critique : Impossible de lire {path} : {e}")
        
    # CORRECTION : Bon nom de fichier
    MQTT_CONFIG_DIR = Path(__file__).parent / "mqtt_config.json"
    CONFIG_MQTT = load_mqtt_config(MQTT_CONFIG_DIR) 
    
    @staticmethod
    def get_driver_def():
        # Calcul du chemin de l'icône
        icon_path = Path(__file__).parent / "assets" / "product_icon.png"
        
        return {
            "id": "smart_electromation_mqtt",
            "name": "Smart Electromation (PV Router)",
            "description": "Pilote les routeurs Smart Electromation V1/V2 via MQTT local.",
            "icon_path": str(icon_path) if icon_path.exists() else None,
            
            "form_schema": [
                {
                    "key": "serial_number", # IMPORTANT : Doit matcher l'argument récupéré dans __init__
                    "label": "Numéro de Série",
                    "type": "text",
                    "required": True,
                    "placeholder": "Ex: PVROUTER001",
                    "help": "Visible sur l'étiquette ou l'interface web (Page /Status)."
                }
                # Si besoin d'ajouter l'IP ou le port plus tard, il suffit d'ajouter un bloc ici !
            ]
        }
    
    def __init__(self, **kwargs):
        # On extrait les données du formulaire
        serial_number = kwargs.get('serial_number')
        
        # Validation
        if not serial_number or not isinstance(serial_number, str):
            raise ValueError("Le numéro de série est requis (str).")
            
        super().__init__(**kwargs)
        
        self.serial = serial_number 
        self.connexion = False
        
        # Configuration du client MQTT
        self.client = mqtt.Client(client_id=f"Optimasol_Software_for_{self.serial}")
        self.client.on_connect = self._on_connect_internal
        self.client.on_disconnect = self._on_disconnect_internal # Ajout pour gérer la déconnexion
        self.client.on_message = self._on_mqtt_message_internal
    
    def device_to_dict(self) -> dict:
        """
        Sérialise le driver pour la base de données.
        On ne sauvegarde que le strict nécessaire pour le reconstruire (le serial).
        """
        return {
            "serial_number": self.serial
        }

    @classmethod
    def dict_to_device(cls, data: dict):
        """
        Reconstruit le driver depuis le JSON de la BDD.
        Exemple de data reçu : {'serial_number': 'PVROUTER001'}
        """
        # On passe directement le dict en arguments nommés (kwargs)
        # Cela appellera __init__(serial_number="...")
        return cls(**data)
    
    def start(self):
        """Lance la connexion et l'écoute"""
        host, port = self.CONFIG_MQTT['host'], self.CONFIG_MQTT['port'] 
        try:
            # On lance la connexion. 
            # Note: On ne fait PAS le subscribe ici, c'est le travail de on_connect.
            self.client.connect(host, port, 60)
            self.client.loop_start() # Gère les reconnexions auto
        except Exception as e:
            print(f"Echec connexion initiale : {e}")
            self.connexion = False

    def send_decision(self, decision):
        # Sécurité : Si on n'est pas connecté, on ne tente même pas d'envoyer
        if not self.connexion:
            print(f"[Driver {self.serial}] Commande ignorée : Pas de connexion MQTT.")
            return

        if not isinstance(decision, (int, float)):
            raise TypeError("La décision doit être un nombre")
        if decision > 1 or decision < 0:
            raise ValueError("La décision doit être un ratio compris entre 0 et 1")

        s2_mode = "1" # Sortie 2 en Auto par défaut

        # CAS 1 : ARRÊT TOTAL (0%)
        if decision == 0:
            self._safe_publish(f"{self.serial}/SETMODE", f"{s2_mode}0")

        # CAS 2 : MARCHE FORCÉE (100%)
        elif decision == 1:
            self._safe_publish(f"{self.serial}/SETMODE", f"{s2_mode}2")

        # CAS 3 : GRADATION
        else:
            # On force le mode 4 puis on envoie la valeur
            self._safe_publish(f"{self.serial}/SETMODE", f"{s2_mode}4")
            self._safe_publish(f"{self.serial}/DIMMER1", decision * 100)

    def activate_safety_mode(self):
        if not self.connexion:
            return
        # Remet tout en auto (Mode 11)
        self._safe_publish(f"{self.serial}/SETMODE", "11")
   
    def _safe_publish(self, topic, payload):
        """Wrapper pour gérer les erreurs d'envoi sans crasher"""
        try:
            info = self.client.publish(topic, payload)
            # Optionnel : vérifier info.rc si besoin de debug poussé
        except Exception as e:
            print(f"Erreur publication sur {topic}: {e}")
            # On ne passe pas forcément self.connexion à False ici, 
            # on laisse le callback on_disconnect gérer l'état réel.

    # --- CALLBACKS MQTT ---

    def _on_connect_internal(self, client, userdata, flags, rc):
        """Appelé automatiquement à la connexion ET à la reconnexion"""
        if rc == 0:
            print(f"[Driver {self.serial}] Connecté au broker MQTT.")
            self.connexion = True 
            
            # C'est ICI qu'il faut s'abonner. 
            # Comme ça, si le wifi coupe et revient, on se réabonne tout seul.
            topic_data = f"{self.serial}/DATA"
            client.subscribe(topic_data)
        else:
            print(f"[Driver {self.serial}] Echec connexion, code retour : {rc}")
            self.connexion = False 

    def _on_disconnect_internal(self, client, userdata, rc):
        """Appelé quand la connexion est perdue"""
        print(f"[Driver {self.serial}] Déconnecté du broker.")
        self.connexion = False

    def _on_mqtt_message_internal(self, client, userdata, msg):
        try:
            payload_str = msg.payload.decode("utf-8")
            data = json.loads(payload_str)
            
            # Mapping des données selon la documentation JSON du routeur
            if "TEMP1" in data and self.on_receive_temperature:
                self.on_receive_temperature(float(data["TEMP1"]))

            if "PROD" in data and self.on_receive_production:
                self.on_receive_production(float(data["PROD"]))

            if "POUT" in data and self.on_receive_power:
                self.on_receive_power(float(data["POUT"]))

        except Exception as e:
            # On ignore les erreurs de parsing pour ne pas bloquer le thread
            print("On a reçu qqch, mais c'était mal formé :", e)
            pass