"""
Le but de ce programme est de charger les configurations à partir du fichier YAML 
mqtt_reveive_config.yaml qui se retrouve dans le dossier config à la racine du projet. 
Ce programme est censé être exécuté dès le début fu programme global, parce qu'il nomme les bonnes variables.
Il est importé par le main_receive.py qui lui écoute les topics.
"""

import yaml
from pathlib import Path 

def load_config() :
    BASE_DIR = Path(__file__).resolve().parent #Nous sommes dans le dossier mqtt_sender (c'est le dossier parent de ce fichier config_loader.py)
    Dir_project = BASE_DIR.parent #C'est la racine du projet.
    path_to_config = Dir_project / "config" / "mqtt" / "mqtt_receive_config.yaml" #On construit le chemin vers le fichier de config.
    with open(path_to_config) as f:
        data = yaml.safe_load(f)
        print("Le fichier de configuration a été ouvert avec succès.") 

    host = data['broker']['host'] 
    port = data['broker']['port']
    username = data['broker']['username']
    password = data['broker']['password']

    client_id = data['client_id'] 
    topic = data['topic']

    return host, port, username, password, client_id, topic


if __name__ == "__main__" :
    host, port, username, password, client_id = load_config() #On teste le chargement de la configuration
    print("host =", host)
    print("port =", port)
    print("username =", username)
    print("password =", password)
    print("client_id =", client_id)     