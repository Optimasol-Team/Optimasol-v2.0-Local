from ..base_driver import BaseDriver 
import json
from pathlib import Path
import paho.mqtt.client as mqtt
import logging

logger = logging.getLogger(__name__)

class SmartEMDriver(BaseDriver):
    DRIVER_TYPE_ID = 1
    # MQTT configuration is injected at runtime (see optimasol.main._apply_runtime_config).
    # Defaults are kept locally to avoid any file-system dependency.
    CONFIG_MQTT = {"host": "test.mosquitto.org", "port": 1883}
    
    @staticmethod
    def get_driver_def():
        """Get the driver definition for UI form generation.
        
        Returns metadata about this driver including identification, description,
        and a form schema for collecting the serial number configuration.
        
        Returns:
            dict: Driver definition containing:
                - id: Technical identifier
                - name: Display name
                - description: Brief description
                - icon_path: Path to device icon
                - form_schema: List of configuration fields
        
        Note:
            The icon_path will be None if the icon file does not exist.
            The form_schema currently requires only the device serial number.
        """
        logger.debug("Retrieving driver definition for SmartEMDriver")
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
        """Initialize SmartEMDriver with device serial number.
        
        Sets up the MQTT client, validates the serial number, and registers
        internal callback handlers for MQTT events.
        
        Args:
            **kwargs: Must include 'serial_number' (str) for device identification.
        
        Raises:
            ValueError: If serial_number is missing or not a string.
        
        Note:
            The MQTT client is configured but not connected until start() is called.
            Connection state starts as False (disconnected).
        """
        logger.debug("Initializing SmartEMDriver with kwargs: %s", list(kwargs.keys()))
        # On extrait les données du formulaire
        serial_number = kwargs.get('serial_number')
        
        # Validation
        if not serial_number or not isinstance(serial_number, str):
            logger.error("Invalid or missing serial number: %s (type: %s)", serial_number, type(serial_number))
            raise ValueError("Le numéro de série est requis (str).")
        
        logger.info("SmartEMDriver initialization: serial=%s", serial_number)
        super().__init__(**kwargs)
        
        self.serial = serial_number 
        self.connexion = False
        logger.debug("SmartEMDriver: Setting up MQTT client for serial %s", self.serial)
        
        # Configuration du client MQTT
        self.client = mqtt.Client(client_id=f"Optimasol_Software_for_{self.serial}")
        self.client.on_connect = self._on_connect_internal
        self.client.on_disconnect = self._on_disconnect_internal # Ajout pour gérer la déconnexion
        self.client.on_message = self._on_mqtt_message_internal
        logger.debug("SmartEMDriver %s: MQTT client configured and callbacks registered", self.serial)
    
    def device_to_dict(self) -> dict:
        """Serialize driver configuration to dictionary for database storage.
        
        Converts the minimal necessary information to reconstruct this driver
        instance later from database storage.
        
        Returns:
            dict: Dictionary containing only the serial_number, which is sufficient
                to recreate the driver via dict_to_device().
        
        Note:
            Only the serial number is persisted as it is the only user-provided
            configuration; MQTT settings are injected globally via CONFIG_MQTT.
        """
        logger.debug("Serializing SmartEMDriver %s to dictionary", self.serial)
        return {
            "serial_number": self.serial
        }

    @classmethod
    def dict_to_device(cls, data: dict):
        """Recreate a driver instance from database storage dictionary.
        
        Factory method to reconstruct a SmartEMDriver instance from data previously
        saved via device_to_dict(). This is used when loading driver configuration
        from the database.
        
        Args:
            data (dict): Serialized driver data with 'serial_number' key.
                Example: {'serial_number': 'PVROUTER001'}
        
        Returns:
            SmartEMDriver: A new instance with the restored serial number.
        
        Note:
            The data dictionary is passed directly as kwargs to __init__(),
            allowing flexible configuration.
        """
        logger.debug("Reconstructing SmartEMDriver from dictionary: %s", data)
        # On passe directement le dict en arguments nommés (kwargs)
        # Cela appellera __init__(serial_number="...")
        return cls(**data)
    
    def start(self):
        """Establish MQTT connection and start listening for device messages.
        
        Initiates the connection to the MQTT broker using credentials from CONFIG_MQTT,
        and starts the background network thread that handles message reception
        and automatic reconnection.
        
        Note:
            - Connection timeout is set to 60 seconds
            - The client uses internal loop_start() for non-blocking operation
            - Subscription to device topics is handled in _on_connect_internal
            - Failures are logged but don't raise exceptions (connection retry is automatic)
        """
        logger.info("SmartEMDriver %s: starting MQTT connection", self.serial)
        host, port = self.CONFIG_MQTT['host'], self.CONFIG_MQTT['port']
        logger.debug("SmartEMDriver %s: attempting to connect to MQTT broker at %s:%d", 
                    self.serial, host, port)
        try:
            # On lance la connexion. 
            # Note: On ne fait PAS le subscribe ici, c'est le travail de on_connect.
            self.client.connect(host, port, 60)
            logger.debug("SmartEMDriver %s: initial connection request sent", self.serial)
            self.client.loop_start() # Gère les reconnexions auto
            logger.info("SmartEMDriver %s: network loop started - auto-reconnection enabled", self.serial)
        except Exception as e:
            logger.error("SmartEMDriver %s: initial connection failed - %s", self.serial, e)
            self.connexion = False

    def send_decision(self, decision):
        """Send optimization decision to the device via MQTT.
        
        Transmits the power control decision to the router. The decision value
        (0.0 to 1.0 ratio) is converted to appropriate MQTT commands:
        - 0.0: Stop (mode 0)
        - 1.0: Full power (mode 2)
        - 0.0 < x < 1.0: Dimmer mode with scaled value (mode 4)
        
        Args:
            decision (float): Power ratio between 0.0 and 1.0.
        
        Raises:
            TypeError: If decision is not int or float.
            ValueError: If decision is not in range [0.0, 1.0].
        
        Note:
            - Command is silently ignored if not connected (with warning log)
            - Output 2 is always set to Auto (S2_MODE = "1")
        """
        logger.debug("SmartEMDriver %s: send_decision called with value %.3f", self.serial, decision)
        # Sécurité : Si on n'est pas connecté, on ne tente même pas d'envoyer
        if not self.connexion:
            logger.warning("SmartEMDriver %s: decision ignored - no MQTT connection", self.serial)
            return

        if not isinstance(decision, (int, float)):
            logger.error("SmartEMDriver %s: invalid decision type: %s (expected int or float)", 
                        self.serial, type(decision))
            raise TypeError("La décision doit être un nombre")
        if decision > 1 or decision < 0:
            logger.error("SmartEMDriver %s: decision out of range: %.3f (must be 0.0-1.0)", 
                        self.serial, decision)
            raise ValueError("La décision doit être un ratio compris entre 0 et 1")

        s2_mode = "1" # Sortie 2 en Auto par défaut

        # CAS 1 : ARRÊT TOTAL (0%)
        if decision == 0:
            logger.info("SmartEMDriver %s: sending OFF command (mode 0)", self.serial)
            self._safe_publish(f"{self.serial}/SETMODE", f"{s2_mode}0")

        # CAS 2 : MARCHE FORCÉE (100%)
        elif decision == 1:
            logger.info("SmartEMDriver %s: sending FULL POWER command (mode 2)", self.serial)
            self._safe_publish(f"{self.serial}/SETMODE", f"{s2_mode}2")

        # CAS 3 : GRADATION
        else:
            dimmer_value = decision * 100
            logger.info("SmartEMDriver %s: sending DIMMER command (mode 4, value=%.1f%%)", 
                       self.serial, dimmer_value)
            # On force le mode 4 puis on envoie la valeur
            self._safe_publish(f"{self.serial}/SETMODE", f"{s2_mode}4")
            self._safe_publish(f"{self.serial}/DIMMER1", dimmer_value)

    def activate_safety_mode(self):
        """Activate safety mode on the device.
        
        Sends command to put the device in automatic mode (mode 11), which is the
        safe default behavior where the router operates normally without external control.
        
        Note:
            Command is silently ignored if not connected.
            This method is typically called during shutdown or error conditions.
        """
        logger.info("SmartEMDriver %s: activating safety mode", self.serial)
        if not self.connexion:
            logger.warning("SmartEMDriver %s: safety mode activation ignored - no connection", self.serial)
            return
        # Remet tout en auto (Mode 11)
        logger.debug("SmartEMDriver %s: sending AUTO/SAFETY mode command (mode 11)", self.serial)
        self._safe_publish(f"{self.serial}/SETMODE", "11")
   
    def _safe_publish(self, topic, payload):
        """Safely publish an MQTT message without crashing on errors.
        
        Wrapper around client.publish() that catches exceptions and logs them
        without propagating failures. Allows graceful handling of temporary
        communication issues.
        
        Args:
            topic (str): MQTT topic to publish to.
            payload: Message payload (will be converted to appropriate type).
        
        Note:
            Exceptions are logged but not raised. Connection state is not modified
            here; let the MQTT callbacks handle connection status updates.
        """
        try:
            logger.debug("SmartEMDriver %s: publishing to topic %s with payload %s", 
                        self.serial, topic, payload)
            info = self.client.publish(topic, payload)
            logger.debug("SmartEMDriver %s: publish result code: %d", self.serial, info.rc)
            # Optionnel : vérifier info.rc si besoin de debug poussé
        except Exception as e:
            logger.error("SmartEMDriver %s: failed to publish on topic %s: %s", 
                        self.serial, topic, e)

    # --- CALLBACKS MQTT ---

    def _on_connect_internal(self, client, userdata, flags, rc):
        """MQTT callback: handle successful connection or reconnection.
        
        Called automatically when the client connects or reconnects to the broker.
        On success, subscribes to the device data topic. On failure, logs the error code.
        
        Args:
            client: MQTT client instance.
            userdata: User-defined data (unused).
            flags: Connection flags (unused).
            rc (int): Connection result code:
                - 0: Connection successful
                - >0: Connection failed with error code
        
        Note:
            Subscription must happen here, not in start(), to handle reconnections
            automatically when network connection is restored.
        """
        if rc == 0:
            logger.info("SmartEMDriver %s: successfully connected to MQTT broker", self.serial)
            self.connexion = True 
            
            # C'est ICI qu'il faut s'abonner. 
            # Comme ça, si le wifi coupe et revient, on se réabonne tout seul.
            topic_data = f"{self.serial}/DATA"
            logger.debug("SmartEMDriver %s: subscribing to data topic %s", self.serial, topic_data)
            client.subscribe(topic_data)
            logger.info("SmartEMDriver %s: subscription to %s successful", self.serial, topic_data)
        else:
            logger.error("SmartEMDriver %s: connection failed with return code %d", self.serial, rc)
            self.connexion = False 

    def _on_disconnect_internal(self, client, userdata, rc):
        """MQTT callback: handle disconnection from broker.
        
        Called automatically when the client disconnects from the broker.
        Updates the connection status and logs the event.
        
        Args:
            client: MQTT client instance.
            userdata: User-defined data (unused).
            rc (int): Disconnection reason code:
                - 0: Normal disconnection
                - >0: Unexpected disconnection (will trigger auto-reconnect)
        
        Note:
            The MQTT client will automatically attempt to reconnect if rc != 0.
        """
        logger.warning("SmartEMDriver %s: disconnected from MQTT broker (rc=%d)", self.serial, rc)
        self.connexion = False

    def _on_mqtt_message_internal(self, client, userdata, msg):
        """MQTT callback: handle incoming message from device.
        
        Called automatically when a message is received on a subscribed topic.
        Parses the JSON payload and calls appropriate callbacks with extracted data.
        Parsing errors are logged but do not crash the receive thread.
        
        Args:
            client: MQTT client instance.
            userdata: User-defined data (unused).
            msg: MQTT message object with payload and topic.
        
        Data Mapping:
            - TEMP1 field -> on_receive_temperature callback
            - PROD field -> on_receive_production callback
            - POUT field -> on_receive_power callback
        
        Note:
            Callbacks are only invoked if they are registered (not None).
            JSON parsing errors are caught and logged without interrupting the loop.
        """
        try:
            logger.info("SmartEMDriver %s: donnée reçue sur %s", self.serial, msg.topic)
            payload_str = msg.payload.decode("utf-8")
            logger.debug("SmartEMDriver %s: payload decoded: %s", self.serial, payload_str)
            data = json.loads(payload_str)
            logger.debug("SmartEMDriver %s: JSON parsed successfully: %s", self.serial, list(data.keys()))
            
            # Mapping des données selon la documentation JSON du routeur
            if "TEMP1" in data and self.on_receive_temperature:
                temp_value = float(data["TEMP1"])
                logger.debug("SmartEMDriver %s: temperature callback triggered with %.2f°C", 
                           self.serial, temp_value)
                self.on_receive_temperature(temp_value)

            if "PROD" in data and self.on_receive_production:
                prod_value = float(data["PROD"])
                logger.debug("SmartEMDriver %s: production callback triggered with %.2f", 
                           self.serial, prod_value)
                self.on_receive_production(prod_value)

            if "POUT" in data and self.on_receive_power:
                power_value = float(data["POUT"])
                logger.debug("SmartEMDriver %s: power callback triggered with %.2f", 
                           self.serial, power_value)
                self.on_receive_power(power_value)

        except Exception as e:
            # On ignore les erreurs de parsing pour ne pas bloquer le thread
            logger.error("SmartEMDriver %s: failed to parse incoming message: %s", self.serial, e)
            pass
