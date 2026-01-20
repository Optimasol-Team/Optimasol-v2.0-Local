import time 
from drivers import SmartEMDriver 

# Attention : Sur votre téléphone, assurez-vous de souscrire au topic "pv1/#" 
# et non "PVROUTER001/#" puisque vous avez changé le numéro de série ici !
routeur_test = SmartEMDriver(serial_number="pv1")

print("Démarrage du driver...")
routeur_test.start() 

# Temps de connexion
time.sleep(1)
print(f"État de connexion : {routeur_test.connexion}")

print("Envoi de la décision...")
routeur_test.send_decision(0.5) 

# --- LA CORRECTION EST ICI ---
# On laisse 2 secondes au "facteur" pour livrer le message avant de fermer la boutique.
time.sleep(2) 

print("Fin du script.")