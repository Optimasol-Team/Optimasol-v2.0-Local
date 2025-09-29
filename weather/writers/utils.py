"""
Ce fichier abrite des fonctions utilitaires utilées dans les autres modules de ce dossier, ces fonctions sont : 
- une fonction qui la table des forecasts dans la BDD si celle ci n'existe pas. 
- Une fonction qui supprime les lignes spécifiques à un fournisseur à partir d'une certaine date. 
- Une fonction qui traduit une ligne de data frame en tuple
- Une fonction qui insère un tuple dans la table weather_forecast
auteur : @anaselb
#Ajouter des fonctions au fur et à mesure qu'on code ici!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
"""

import sqlite3 
import pandas as pd 

def create_table_if_not_exists_internal(path_to_db): #Fonction qui crée la table weater_forecast si elle n'existe pas déjà. 
    with sqlite3.connect(path_to_db) as conn:
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS weather_forecast (
            Datetime TEXT,
            GHI REAL,
            DNI REAL,
            DHI REAL,
            Temperature REAL,
            Wind REAL,
            Albedo REAL,
            GTI REAL,
            Provider TEXT
            );
        """)
        conn.commit()
        print("La table weather_forecast a été créée ou elle existait déjà.")

def delete_rows_from_date_internal(path_to_db, provider, start_date) :
    """Le but de cette fonction c'est de supprimer les lignes d'un fournisseur à partir d'une certaine date.
    Cela permet de mettre à jour les données d'un fournisseur sans multiplier les lignes. 
    La date doit être au format ISO 8601 : 'YYYY-MM-DDTHH:MM:SS'"""
    with sqlite3.connect(path_to_db) as conn:
        cursor = conn.cursor()
        cursor.execute("""
        DELETE FROM weather_forecast
        WHERE provider = ? AND datetime >= ?;
        """, (provider, start_date))
        conn.commit()
        print(f"Les lignes du fournisseur {provider} à partir de la date {start_date} ont été supprimées.") 

def row_to_tuple_internal(row: pd.Series) -> tuple:
    """Le but de cette fonction c'est de transformer une ligne d'un dataframe pandas en tuple.
    Cela permet d'insérer facilement les données dans la base de données SQLite.
    L'ordre des colonnes doit être respecté : datetime, provider, GHI, DNI, DHI, Temperature, Wind, Albedo (Optionnel), GTI (optionnel)"""
    if 'Albedo' not in row.index:
        row['Albedo'] = None
    if 'GTI' not in row.index:
        row['GTI'] = None
    return (row['Datetime'], row['GHI'], row['DNI'], row['DHI'], row['Temperature'], row['Wind'], row['Albedo'], row['GTI'])

def insert_tuple_internal(path_to_db, data_tuple: tuple):
    """Le but de cette fonction c'est d'insérer un tuple dans la table weather_forecast.
    Le tuple doit être dans l'ordre : datetime, provider, GHI, DNI, DHI, Temperature, Wind, Albedo (Optionnel), GTI (optionnel)"""
    with sqlite3.connect(path_to_db) as conn:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO weather_forecast (
            Datetime, GHI, DNI, DHI, Temperature, Wind, Albedo, GTI, Provider
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, data_tuple)
        conn.commit()
        print("Le tuple a été inséré dans la table weather_forecast.")


########################################################LES UTILS DE L'EXTERNAL #######################################################

def create_table_if_not_exists_external(path_to_db): #Fonction qui crée la table weater_forecast si elle n'existe pas déjà. 
    with sqlite3.connect(path_to_db) as conn:
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS productions_pv (
            Datetime TEXT,
            Production REAL,
            Provider_type TEXT,
            Provider_name TEXT,
            Methode_calcul TEXT
            );
        """)
        conn.commit()
        print("La table productions_pv a été créée ou elle existait déjà.")

def delete_rows_from_date_external(path_to_db, provider, start_date) :
    """Le but de cette fonction c'est de supprimer les lignes d'un fournisseur à partir d'une certaine date.
    Cela permet de mettre à jour les données d'un fournisseur sans multiplier les lignes. 
    La date doit être au format ISO 8601 : 'YYYY-MM-DDTHH:MM:SS'"""
    with sqlite3.connect(path_to_db) as conn:
        cursor = conn.cursor()
        cursor.execute("""
        DELETE FROM productions_pv
        WHERE Provider_name = ? AND Datetime >= ?;
        """, (provider, start_date))
        conn.commit()
        print(f"Les lignes du fournisseur {provider} à partir de la date {start_date} ont été supprimées.") 


def row_to_tuple_external(row: pd.Series) -> tuple:
    """Transforme une ligne de dataframe pandas en tuple pour la table productions_pv.
    Ordre: datetime, production"""
    return (
        row['datetime'],
        row['production']
    )

def insert_tuple_external(path_to_db, data_tuple: tuple):
    """Insère un tuple dans la table productions_pv.
    Ordre: datetime, provider_type, provider_name, production_calculated, methode_calcul"""
    with sqlite3.connect(path_to_db) as conn:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO productions_pv (
            Datetime, Production, Provider_type, Provider_name, Methode_calcul
        ) VALUES (?, ?, ?, ?, ?);
        """, data_tuple)
        conn.commit()
        print("Le tuple a été inséré dans la table productions_pv.")

#Ajouter des fonctions au fur et à mesure qu'on code ici!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!