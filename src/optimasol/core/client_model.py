from optimiser_engine import Client as Clt_engine
from weather_manager import Client as Clt_weather
from ..drivers import BaseDriver
from datetime import datetime, timezone
from optimiser_engine import OptimizerService
import json
from ..paths import CONFIG_DIR

class Client:
    @staticmethod
    def load_config_optimisation() :
        DIR_CONFIG = CONFIG_DIR / "optimizer_config.json"
        try:
            with open(DIR_CONFIG, 'r') as f:
                config = json.load(f)
            return config
        except Exception as e:
            return {"horizon": 24, "step_minutes": 15}  # Valeur par défaut 
    CONFIG_OPTIMISATION = load_config_optimisation()
    HORIZON_HOURS = CONFIG_OPTIMISATION.get("horizon", 24)
    STEP_MINUTES = CONFIG_OPTIMISATION.get("step_minutes", 15)
    def __init__(self, 
                 client_id: int, 
                 client_engine : Clt_engine, 
                 client_weather : Clt_weather, 
                 driver: BaseDriver):
        
        self.client_id = client_id
        self.client_engine = client_engine
        self.client_weather = client_weather
        self.driver = driver
        

        # --- 1. MEMOIRE TAMPON (RAM) ---
        # On stocke la Valeur ET l'Instant (Time) de réception
        
        # Température
        self.last_temperature = None
        self.last_temperature_time = None # Timestamp UTC
        
        # Production
        self.last_production = None
        self.last_production_time = None # Timestamp UTC
        
        # Puissance (Power)
        self.last_power = None
        self.last_power_time = None # Timestamp UTC

        # --- 2. CÂBLAGE (HOOKS) ---
        self.driver.on_receive_temperature = self._update_temperature
        self.driver.on_receive_production = self._update_production
        self.driver.on_receive_power = self._update_power
        self.production_forecast = None 

    # --- 3. LES FONCTIONS DE MISE A JOUR (Callbacks) ---
    
    def _update_temperature(self, value: float):
        # 1. On capture l'heure UTC exacte MAINTENANT
        now_utc = datetime.now(timezone.utc)
        
        # 2. On met à jour les deux variables (Valeur + Temps)
        self.last_temperature = value
        self.last_temperature_time = now_utc
        
        # Debug optionnel
        # print(f"[{now_utc.isoformat()}] Client {self.client_id} : Temp reçue -> {value}°C")

    def _update_production(self, value: float):
        now_utc = datetime.now(timezone.utc)
        self.last_production = value
        self.last_production_time = now_utc

    def _update_power(self, value: float):
        now_utc = datetime.now(timezone.utc)
        self.last_power = value
        self.last_power_time = now_utc
    
    def decision(self) :
        now = datetime.now() 
        service = OptimizerService(Client.HORIZON_HOURS, Client.STEP_MINUTES) 

        trajectory = service.trajectory_of_client(self.client_engine, now, self.last_temperature, self.production_forecast) 

        decision = trajectory.get_decisions()[0] 

        return decision 

    @property
    def is_ready(self):
        """Vérifie qu'on a tout ce qu'il faut pour calculer"""
        return (self.last_temperature is not None and 
                self.production_forecast is not None)

    def process(self):
        # SÉCURITÉ : On ne fait rien si on n'a pas les données
        if not self.is_ready:
            print(f"Client {self.client_id} en attente de données (Temp ou Météo)...")
            return

        try:
            decision = self.decision() 
            self.driver.send_decision(decision)
        except Exception as e:
            print(f"Erreur process client {self.client_id}: {e}")


    


        
