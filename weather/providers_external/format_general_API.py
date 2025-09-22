"""Ce fichier ressemble à format_general.py mais il est destiné à être utilisé pour les fournisseurs commerciaux qui donnent directement la production PV prévue.
Tu dois créer une fonction qui prend en argument : 
position : latitude, logitude, altitude, timezone
horizon, pas_de_temps
azimuth, tilt, + Des données qui te paraissent nécessaires d'après l'API. 
clé API évidemment.
Elle renvoie un dataframe pandas avec :
Datetime , Production PV prévue en W
Les programmes doivent être commentées et clairs, commentés en français ou en anglais (comme tu veux)
 """


#Imports : 
# normalement tu auras esoin de datetime et pandas, tu es libre d'importer d'autres modules si nécessaire.

def nom_de_fournisseur(position_latitude, position_longitude, position_altitude, position_timezone, horizon, pas_de_temps, azimuth, tilt) : #Tu peux ajouter d'autres arguments
    #Le code que tu vas écrire pour parler à l'API 

    return #Un dataframe pandas avec les colonnes suivantes : 
    #Datetime (index), Production PV prévue en W



# Il faut respecter l'ordre de la sortie, c'est le plus important. 
#Le dataframe doit être datetime (généralement AAAA-MM-JJ HH:MM:SS) en index, et la production PV prévue en W en colonne.
#Pour la moindre question, n'hésite pas à me demander.
#Bon courage !


