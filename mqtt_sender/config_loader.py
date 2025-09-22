import yaml
from pathlib import Path 

"""Ce module permet de charger la configuration MQTT concernant l'envoi depuis le fichier de configurations 
mqtt_send_config.yaml qui se trouve dans le dossier config à la racine du projet.
Il est censé être exécuté dès le début du programme global parce qu'il est importé par le sender.py
Il permet de définir les variables globales qui seront utilisées par le module sender.py
"""

def load_config() :
    BASE_DIR = Path(__file__).resolve().parent #Nous sommes dans le dossier mqtt_sender (c'est le dossier parent de ce fichier config_loader.py)
    Dir_project = BASE_DIR.parent #C'est la racine du projet.
    path_to_config = Dir_project / "config" / "mqtt" / "mqtt_send_config.yaml" #On construit le chemin vers le fichier de config.
    with open(path_to_config) as f:
        data = yaml.safe_load(f)
        print("Le fichier de configuration a été ouvert avec succès.") 

    host = data['broker']['host'] 
    port = data['broker']['port']
    username = data['broker']['username']
    password = data['broker']['password']

    client_id = data['client_id'] 

    return host, port, username, password, client_id


if __name__ == "__main__" :
    host, port, username, password, client_id = load_config() #On teste le chargement de la configuration
    print("host =", host)
    print("port =", port)
    print("username =", username)
    print("password =", password)
    print("client_id =", client_id)     