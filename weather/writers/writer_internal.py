"""
Le but de ce module est de héberger une fonction qui prend en argument un dataframe pandas 
et le charge dans la table SQL de la BDD optimasol.db 
La fonction ne doit pas simplement ajouter les lignes, mais voir si la date existe déjà pour les mêmes fournisseurs 
et dans ce cas, mettre à jour les lignes qui suivent cette date sans multiplier les lignes. 
Étapes : 
- Créer la table si elle n'exsiste pas déjà (fonction utilitaire)
- Supprimer les lignes du fournisseur à partir de la date actuelle (fonction utilitaire)
- Ajouter les nouvelles lignes (fonction principale) (en utilisant une fonction utilitaire qui transforme une ligne de dataframe en tuple)
auteur : @anaselb
"""

import pandas as pd
from pathlib import Path
from utils import create_table_if_not_exists_internal, delete_rows_from_date_internal, row_to_tuple_internal, insert_tuple_internal
from datetime import datetime

def write_forecast_to_db(df: pd.DataFrame, fournisseur : str) :
    path_to_db = Path(__file__).parent.parent.parent / "database" / "optimasol.db" #Chemin vers la BDD
    #Créeons la table si elle n'existe pas déjà : 
    create_table_if_not_exists_internal(path_to_db)
    #Supprimons les lignes du fournisseur à partir de la date actuelle :
    now = datetime.now().isoformat() #Date actuelle au format ISO
    delete_rows_from_date_internal(path_to_db, fournisseur, now)    
    #Ajoutons les nouvelles lignes : Parcourons alors le dataframe et pour chaque ligne, transformons la en tuple et on l'insère
    for index, row in df.iterrows() :
        data_tuple = row_to_tuple_internal(row) #Transformons la ligne en tuple
        try :
            #Il faut ajouter les données de providers à data_type avant de l'insérer :
            data_tuple = data_tuple + (fournisseur,)
            #Insérons le tuple dans la table weather_forecast
            insert_tuple_internal(path_to_db, data_tuple)
            print(f"La ligne {data_tuple} a été insérée avec succès.")
        except Exception as e:
            print(f"L'insertion de la ligne {data_tuple} a échoué à cause de l'erreur : {e}")

