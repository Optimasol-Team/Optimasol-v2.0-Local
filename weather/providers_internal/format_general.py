"""Ce n'est un module permanent. C'est juste pour expliquer comment serait les autres modules dans ce même dossier.
Le but c'est que chaque fichier py dans ce dossier contient une fonction qui prend en argument des données brutes : 
- latitude, longitude, altitude, timzeone
- horizon, pas de temps. 

Ce qu'on veut : 
Irradiance GHI, DNI, DHI, Température, Vent, Albédo (optionnal), GTI (optionnel)
Remarque : Si GTI est présente, pas besoin de GHI, DNI, DHI, mais là il faut aussi les infos panneaux (azimuth, tilt). 

"""

#Toujours commencer par importer les modules suivantes : 
# Normalement tu auras besoin de datetime et de pandas. Comme ça tu peux gérer demander à l'API des données à partir de maintenant. 
#Format général de la fonction qu'on souhaite coder : 

def nom_de_fournisseur(laitude, longitude, altitude, fuseau_horaire, horizon, pas_de_temps) :
    #Le code que tu vas écrire pour parler à l'API 


    return #Un dataframe pandas avec les colonnes suivantes : 
    #Datetime (index), GHI, DNI, DHI, Température, Vent, Albédo (optionnal), GTI (optionnel)


#Remarques : Si GTI est possible, tu ajoutes en argument de la fonction azimuth et tilt. 

#Pour la moindre question, n'hésite pas à me demander.
#Bon courage !