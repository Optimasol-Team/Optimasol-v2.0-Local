#writer.py
"""
Ceci est le programme qui contient une focntion d'entrée pricnipale write_to_db, qui prend en charge un message JSON du format spécifié par le routeur
et l'écrit dans le base de données SQLite de optimasol.db
Elle écrit ça dans la table router_data spécifique à ces données. Le but est de séparer les données du JSON, chaque colonne = une clé du JSON. 
"""

import sqlite3 
import json
from pathlib import Path 
from datetime import datetime

def decode_json(message) -> tuple :
    """Le but de cette fonction est de décoder les messages JSON reçus du routeur en renvoyant les valeurs sus forme d'une tuple de valeurs."""
    data = json.loads(message) #data est un dictionnaire Python. 
    try : 
        valeurs = (
            data['MODEL'],
            data['VIN'],
            data['CIN'],
            data['PIN'],
            data['COUT'],
            data['POUT'],
            data['LOAD1'],
            data['LOAD2'],
            data['MODEINFO'],
            data['STATUS_OUT1'],
            data['STATUS_OUT2'],
            data['LOAD1_SATURATED'],
            data['LOAD2_SATURATED'],
            data['BATT'],
            data['SAVED_POWER'],
            data['TOTAL_POWER'],
            data['INJECT'],
            data['INJECT_I'],
            data['TOT_PROD'],
            data['PROD'],
            data['EFF'],
            data['DISPLAY'],
            data['TEMP1'],
            data['REF_T'],
            data['BACT'],
            data['TIME'],
            data['NIGHT'],
            data['Version']
            )
        
        print("Le décodage du message JSON a été effectué") 
        return valeurs
    except Exception :
        print('Le décodage du message JSON a échoué, il faut penser à vérifier le format JSON des données reçues et leur compatibilité avec le programme python')
        return None 
    
def init_db(path_to_db): #Cette fonction dit à sql d'ajouter la table router_data si elle n'existe pas déjà.
    with sqlite3.connect(path_to_db) as conn:
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS router_data (
            timestamp TEXT,
            MODEL TEXT,
            VIN TEXT,
            CIN TEXT,
            PIN TEXT,
            COUT REAL,
            POUT REAL,
            LOAD1 REAL,
            LOAD2 REAL,
            MODEINFO TEXT,
            STATUS_OUT1 TEXT,
            STATUS_OUT2 TEXT,
            LOAD1_SATURATED TEXT,
            LOAD2_SATURATED TEXT,
            BATT REAL,
            SAVED_POWER REAL,
            TOTAL_POWER REAL,
            INJECT REAL,
            INJECT_I REAL,
            TOT_PROD REAL,
            PROD REAL,
            EFF REAL,
            DISPLAY TEXT,
            TEMP1 REAL,
            REF_T REAL,
            BACT REAL,
            TIME TEXT,
            NIGHT TEXT,
            VERSION TEXT
        );
        """)
        conn.commit()

def write_to_db(message) :
    """Le but de la fonction c'est de décoder le message JSON et de l'écrire dans optimasol.db qui se trouve dans le dossier database.
    Cela s'effectue en plusieurs étapes, on décode le JSON, on extrait les valeurs sans clés.""" 
    #On appelle la fonction decode_json :
    valeurs = decode_json(message) 
    if valeurs is None :
        print("L'écriture dans la base de données a échoué à cause d'un problème de décodage du JSON.")
    else :
        #On se connecte à la base de données SQLite :
        BASE_DIR = Path(__file__).resolve().parent #Nous sommes dans le dossier mqtt_receive
        Dir_project = BASE_DIR.parent #C'est la racine du projet.
        path_to_db = Dir_project / "database" / "optimasol.db" #On construit le chemin vers la base de données.
        init_db(path_to_db) #On initialise la base de données (on crée la table router_data si elle n'existe pas déjà).
        with sqlite3.connect(path_to_db) as conn : #On se connecte à la base de données.
            cursor = conn.cursor() #On crée un curseur pour exécuter les commandes SQL
            now = datetime.now().isoformat() #On récupère la date et l'heure actuelles.
            valeurs_avec_date = (now, ) + valeurs #On ajoute la date au début de la tuple des valeurs.
            try :
                cursor.execute("""
                INSERT INTO router_data (
                    timestamp, MODEL, VIN, CIN, PIN, COUT, POUT, LOAD1, LOAD2, MODEINFO, STATUS_OUT1, STATUS_OUT2, 
                    LOAD1_SATURATED, LOAD2_SATURATED, BATT, SAVED_POWER, TOTAL_POWER, INJECT, INJECT_I, 
                    TOT_PROD, PROD, EFF, DISPLAY, TEMP1, REF_T, BACT, TIME, NIGHT, VERSION
                ) VALUES (?,?, ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, valeurs_avec_date) #On insère les valeurs (avec la date au début de la colonne) dans la table router_data. 
                conn.commit() #On valide.
                print("L'insertion des données dans la base de données a été effectuée avec succès.")
            except Exception as e:
                print(f"L'insertion des données a échoué : {e}")
if __name__ == "__main__" :
    BASE_DIR = Path(__file__).resolve().parent 
    dossier_test = BASE_DIR / "tests"
    path_to_test_json = dossier_test / "test_fiche_technique.json"
    with open(path_to_test_json, "r", encoding="utf-8") as f:
       message = f.read()
    write_to_db(message) #On teste l'écriture dans la base de données.

