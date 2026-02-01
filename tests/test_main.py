"""L'objectif de ce script est de tester que la fonction main() définie dans main.py marche comme prévu :"""

import random

from optimasol.core import AllClients, Client
from optimasol.database import DBManager
from optimasol.drivers import SmartEMDriver
from optimasol.main import main
from optimiser_engine import Client as EngineClient
from weather_manager import Client as WeatherClient

# Création des configurations requis par le main() :

config = {
  "update_with_db": {
    "frequency": 2
  },
  "update_weather": {
    "frequency": 1
  },
  "path_to_db": {
    "path_to_db": "/Users/anaselb/Dev/Projects/Optimasol-v2.0-local/tests/db_test.db"
  },
  "optimizer_config": {
    "horizon": 24,
    "step_minutes": 15
  },
  "mqtt_config": {
    "host": "test.mosquitto.org",
    "port": 1883
  },
  "chack_efficiency_pannels": {
    "frequency": 7
  },
  "min_distance": {
    "minimal_distance": 15
  }
}

# En particulier le chamin vers la DB : 
DIR_TO_DB_TEST = config["path_to_db"]["path_to_db"] 

# Création de trois clients modèles aléatoires : 

random.seed(2026)


def _engine_payload(cid: int) -> dict:
    """Fabrique une configuration optimiser_engine.Client pseudo-aléatoire déterministe."""
    consumption_profile = [
        [round(random.uniform(80.0, 250.0), 2) for _ in range(24)] for _ in range(7)
    ]
    return {
        "client_id": cid,
        "water_heater": {
            "volume": round(random.uniform(150, 300), 1),
            "power": round(random.uniform(2000, 3500), 1),
            "insulation_coeff": round(random.uniform(0.2, 0.5), 2),
            "temp_cold_water": round(random.uniform(8, 14), 1),
        },
        "prices": {
            "mode": "BASE",
            "base_price": round(random.uniform(0.15, 0.30), 3),
            "resell_price": round(random.uniform(0.05, 0.12), 3),
        },
        "features": {"mode": "cost", "gradation": random.choice([True, False])},
        "constraints": {
            "min_temp": round(random.uniform(42, 55), 1),
            "consumption_profile": consumption_profile,
            "forbidden_slots": [{"start": "12:00", "end": "13:00"}],
            "background_noise": 250.0,
        },
        "planning": [
            {
                "day": random.randint(0, 6),
                "time": f"{random.randint(5, 22):02d}:{random.choice([0, 15, 30, 45]):02d}",
                "target_temp": round(random.uniform(48, 60), 1),
                "volume": round(random.uniform(25, 60), 1),
            }
            for _ in range(2)
        ],
    }


def _weather_payload(cid: int) -> dict:
    """Fabrique une configuration weather_manager.Client pseudo-aléatoire déterministe."""
    panneaux = [
        {
            "azimuth": round(random.uniform(0, 360), 1),
            "tilt": round(random.uniform(10, 45), 1),
            "surface_panneau": round(random.uniform(1.5, 2.1), 2),
            "puissance_nominale": round(random.uniform(350, 450), 1),
        }
        for _ in range(2)
    ]
    return {
        "client_id": cid,
        "position": {
            "latitude": round(random.uniform(-60, 60), 4),
            "longitude": round(random.uniform(-120, 120), 4),
            "altitude": round(random.uniform(0, 500), 1),
        },
        "installation": {
            "rendement_global": round(random.uniform(0.75, 0.95), 2),
            "liste_panneaux": panneaux,
        },
    }


def _build_client(cid: int) -> Client:
    """Assemble les dépendances pour construire un Client Optimasol complet."""
    engine_client = EngineClient.from_dict(_engine_payload(cid))
    weather_client = WeatherClient.from_dict(_weather_payload(cid))
    driver = SmartEMDriver(serial_number=f"SN-{cid:04d}-{random.randint(1000, 9999)}")
    return Client(client_id=cid, client_engine=engine_client, client_weather=weather_client, driver=driver)


client1 = _build_client(1) 

client2 = _build_client(2) 

client3 = _build_client(3) 

# All clients : 

all_clients = AllClients() 
all_clients.add(client1) 
all_clients.add(client2) 
all_clients.add(client3)  

# On stocke all_clients dans une DB de test : 

db_manager = DBManager(DIR_TO_DB_TEST) 

db_manager.client_manager.store_all_clients(all_clients) 

# Maintenant on dispose d'une DB, commençons le main() : 
print("on est ici")
try :
    main(config) 
except Exception as e :
    print(f"Non, ça échoue. {e}") 
    
