import time  # Nécessaire pour faire une pause
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT_ROOT / "src"))

from optimasol.drivers import SmartEMDriver 

# Instanciation
# On doit utiliser la clé définie dans le form_schema ("key": "serial_number")
routeur_test = SmartEMDriver(serial_number="PVROUTER001")

# Définition des callbacks
def on_temperature(T) :
    print(f"🌡️ On a reçu la température {T} °C") 

def on_production(P) :
    print(f"☀️ On a reçu la production {P} A")

def on_power(P) :
    print(f"⚡ On a reçu la puissance {P} W") 

# Liaison des callbacks
routeur_test.on_receive_temperature = on_temperature 
routeur_test.on_receive_production = on_production
routeur_test.on_receive_power = on_power

# Démarrage
print("Démarrage du driver...")
routeur_test.start() 

# Vérification immédiate (peut être False si la connexion prend > 1ms)
# Mieux vaut attendre un tout petit peu
time.sleep(1) 
print(f"État de connexion : {routeur_test.connexion}")

# --- LA BOUCLE INFINIE ---
# C'est ce qui maintient le programme en vie pour écouter MQTT
try:
    print("Le programme écoute (Ctrl+C pour arrêter)...")
    while True:
        # On ne fait rien, on laisse le thread MQTT du driver bosser
        # On met un petit sleep pour ne pas utiliser 100% du processeur pour rien
        time.sleep(1)
except KeyboardInterrupt:
    print("Arrêt du programme.")
    # Optionnel : routeur_test.stop() si tu implémentes une méthode stop
