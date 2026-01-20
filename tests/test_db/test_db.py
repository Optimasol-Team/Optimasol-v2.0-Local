from pathlib import Path
import sys

# Ajout de la racine du projet au path pour les imports
BASE_DIR = Path(__file__).parent.parent 
sys.path.append(str(BASE_DIR))

from database import DBManager 

# 1. Setup
# On utilise une DB de test pour ne pas casser la vraie
to_db = BASE_DIR / "data" / "test_optimasol.db" 

# Nettoyage préalable (pour repartir de zéro à chaque test)
if to_db.exists():
    to_db.unlink()

print(f"📂 Utilisation de la BDD : {to_db}")
manager = DBManager(to_db) 

# 2. Vérification des Drivers disponibles
print("\n🔍 Drivers disponibles :")
drivers = manager.get_available_drivers()
print(drivers)
# On récupère l'ID du premier driver dispo (normalement 'smart_electromation_mqtt')
driver_id_target = drivers[0]['id'] 

# 3. CRÉATION DU CLIENT (Le moment de vérité)
print(f"\n🛠️ Création d'un client avec le driver '{driver_id_target}'...")

try:
    new_id = manager.create_client_ui(
        name="Maison Test",
        email="test@optimasol.com",
        password="superpassword123",
        driver_type_id=driver_id_target,
        serial_number="SN-9999-TEST" # <--- Argument spécifique au Driver SmartEM
    )
    print(f"✅ Client créé avec succès ! ID généré : {new_id}")

except Exception as e:
    print(f"❌ CRASH à la création : {e}")
    exit(1)

# 4. SIMULATION REDÉMARRAGE (Rechargement depuis la BDD)
print("\n🔄 Rechargement de tous les clients (Simulation démarrage Service)...")

try:
    # C'est là que from_dict et la Factory Driver travaillent
    all_clients = manager.get_all_clients_engine()
    
    nb_clients = len(all_clients.list_of_clients)
    print(f"📊 Clients chargés en mémoire : {nb_clients}")
    
    if nb_clients == 1:
        # 5. INSPECTION DE L'OBJET RECONSTRUIT
        client = all_clients.which_client_by_id(new_id)
        
        print(f"   👤 Client ID : {client.client_id}")
        
        # Vérification du Driver
        print(f"   🔌 Driver Class : {type(client.driver).__name__}")
        # On vérifie si le serial a bien survécu à l'aller-retour BDD
        if hasattr(client.driver, 'serial'):
            print(f"   🏷️ Serial Driver : {client.driver.serial}")
            if client.driver.serial == "SN-9999-TEST":
                print("   ✅ Le Serial Number est correct.")
            else:
                print("   ❌ Erreur : Le Serial Number a changé !")
        
        # Vérification Moteur & Météo
        print(f"   ⚙️ Engine présent : {client.client_engine is not None}")
        print(f"   ☁️ Weather présent : {client.client_weather is not None}")
        
        # Test Login
        print("\n🔐 Test Authentification :")
        login_id = manager.check_login("test@optimasol.com", "superpassword123")
        if login_id == new_id:
            print("   ✅ Login OK (Hash vérifié)")
        else:
            print("   ❌ Login Echec")

    else:
        print("❌ Erreur : On attendait 1 client, on en a trouvé", nb_clients)

except Exception as e:
    print(f"❌ CRASH au rechargement : {e}")
    # Affiche le détail pour débugger (souvent un from_dict qui plante)
    import traceback
    traceback.print_exc()