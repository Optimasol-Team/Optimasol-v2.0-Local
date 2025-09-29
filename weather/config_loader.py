#config_loader.py
"""
Le but de ce module est de charger les configurations depuis le dossier config/weather. 
Il permet de charger les configurations et de créer des instances de classes comme définies dans le module config_model.py
Auteur : @anaselb
"""


from pathlib import Path 
import yaml 
from config_model import Position, Requetes, Features, Installation_PV

PATH_DIR = Path(__file__).parent.resolve() # C'est le dossier weather. 
Dir_project = PATH_DIR.parent #C'est la racine du projet.
#Les paths : 
Path_config_position = Dir_project / "config" / "weather" / "position.yaml" 
Path_config_pannels = Dir_project / "config" / "weather" / "pannels.yaml" 
Path_config_providers = Dir_project / "config" / "weather" / "providers.yaml"
Path_config_settings = Dir_project / "config" / "weather" / "settings.yaml" 
Path_config_fournisseur_propre = Dir_project / "config" / "weather" / "fournisseur_propre.yaml" 


def load_yaml(path : Path) -> dict :
   """Le but de cette fonction c'est juste de charger un fichier yaml depuis le path, et mettre les données sous forme de dictionnaire python."""
   try : 
      with open(path) as f :
         data = yaml.safe_load(f) 
         print(f"Le fichier de configuration {path} a été ouvert avec succès.") 
         return data 
   except :
      print(f"Le chargement du fichier {path} a échoué") 
      return None 
   

def load_position() -> Position  :
    """
    Cette fonction charge les configurations depuis position.yaml et renvoie une instance de classe position remplie.
    """
    data = load_yaml(Path_config_position) 
    if data is None :
       print("Le fichier du config de position n'a pas pu être chargé, on va donc passer aux valeurs par défaut de la position (Lille, 50.633333, 3.06, 20m)")
       latitude, longitude, altitude = 50.633333, 3.06, 20
       cfg_position = Position(latitude, longitude, altitude, "Europe/Paris") 
       return cfg_position 
      #Sinon on a les données, on crée l'instance de classe position :
    else :
       latitude, longitude, altitude, timezone = data["latitude"], data["longitude"] , data["altitude"] , data["fuseau_horaire"] 
       try :
          cfg_position = Position(latitude, longitude, altitude, timezone) 
          print("La positiion respecte bien le format de la classe Position, on crée l'instance de classe position")
          return cfg_position
       except :
          print("Le format des données n'est pas bon, veuillez vérifiez les paramètres saisies. On a basculé sur les données par défaut de Lille ")
          latitude, longitude, altitude = 50.633333, 3.06, 20
          cfg_position = Position(latitude, longitude, altitude, "Europe/Paris") 
          return cfg_position 


def load_cfg_requetes() -> Requetes :
    """
    Cette fonction charge les configurations des requêtes. 
    """
    data = load_yaml(Path_config_settings)
    if data is None :
       print("Le chargement du fichier de configuration a échoué, nous allons passer aux données par défaut 48h pour l'horizon, 15min pour le pas, 6heures pour la fréquence des mises à jour")
       frequence, pas, horizon = 300, 15, 48
       cfg_requetes = Requetes(horizon, pas, frequence)
       return cfg_requetes
    else :
       
       try :
          frequence, pas, horizon = data["requetes"]["frequence_rafraichissement"], data["requetes"]["pas_de_temps"] , data["requetes"]["horizon_temporel"]
          cfg_requetes = Requetes(horizon, pas, frequence)
          print("Les paramètres ont bien été importés et vont être gérés par le système") 
          return cfg_requetes 
       except :
          print("Les données ne respectent pas le format souhaité pour le type requetes, on bascule sur les valeurs par défaut : 48h pour l'horizon, 15min pour le pas, 6heures pour la fréquence des mises à jour")
          frequence, pas, horizon = 300, 15, 48
          cfg_requetes = Requetes(horizon, pas, frequence)
          return cfg_requetes


def load_cfg_features() -> Features :
    """
    Cette fonction charge les configs des fonctionnalités et les met dans une instance de features. 
    """ 
    data = load_yaml(Path_config_settings) 
    if data is None :
       print("Puisque le chargement du fichier des configs a échoué, on va passer aux valeurs défaut, aucune fonctionnalité n'est choisie.")
       selection_fournisseur , ajusteur_ranking , ajusteur_parametres , fournisseur_propre_auto , saisie_manuelle , IA_feature = False , False, False, False, False, False
       details = Features.Features_details(None, None, None) 
       cfg_features = Features(selection_fournisseur , ajusteur_ranking , ajusteur_parametres , fournisseur_propre_auto , saisie_manuelle , IA_feature, details)
       return cfg_features
    else :
          #On va essayer de créer une instance avec les valeurs extraites, si moindre erreur, passage aux valeurs par défaut : 
          #On va maintenant déchiffrer le dictionnaire data : 
          
          selection_fournisseur ,  fournisseur_propre_auto , saisie_manuelle ,  = False , False, False #On initialise les données liées aux trois fonctionnalités qui correspondent pas à des booléens dans le yaml
          
          #----------LE CAS DE L'USER QUI VEUT PRIORISER UN FOURNISSEUR D'IRRADIANCE--------------
          if data["features"]["selection_fournisseur"] != 0 :  
             #Dans ce cas, l'utilisateur veut un fournisseur parmi ceux qu'on propose.
             selection_fournisseur = True
             quel_fournisseur = data["features"]["selection_fournisseur"] 
             print(f"OK l'utilisateur veut prioriser le fournisseur météo particulier : {quel_fournisseur}") 

             #Créons l'instance liée à ce fournisseur :
             try :
                 details = Features.Features_details(quel_fournisseur, None, None) 
                 print("Le fournisseur a bien été pris en compte dans l'instance")
             except :
                 selection_fournisseur = False 
                 details = Features.Features_details(None, None, None) 
                 print("Le string du fournisseur ne respecte pas les exigences, passage aux paramètres défauts")


          #-----------LE CAS DE l'USER AVEC SON PROPRE FOURNISSEUR AVEC MODE AUTO----------------#
          if data["features"]["fournisseur_propre"] == 1 :
             fournisseur_propre_auto = True 
             print("OK, l'utilisateur veut utiliser son API commercial automatiquement, on va donc charger les données nécessaires à celles ci") 
             #Les configuraitions de l'API propre existent dans un autre fichier, on va le charger
             fourniss_propre = load_yaml(Path_config_fournisseur_propre) 
             if fourniss_propre is None : #Échec de chargement du fichier lié au fournisseur propre
                print("Le chargement du fichier configurations de la propre API a échoué, donc pas d'API personnalisé, on bouscule aux paramètres par défaut") 
                fournisseur_propre_auto = False 
                details = Features.Features_details(None, None, None) 
             else :
                print("Le chargement a réussi, maintenant on essaie de créer une instance de cet objet") 
                nom_fournisseur = quel_fournisseur["nom_fournisseur"] 
                cle_API = quel_fournisseur["API_key"]
                try :
                   details = Features.Features_details(None, nom_fournisseur, cle_API) 
                   print("On a bien chargé les données du fournisseur automatique propre dans l'instance") 
                except :
                   print("Les données de configurations de l'API propre ne respectent pas les exigences, passage en mode par défaut")
                   fournisseur_propre_auto = False 
                   details = Features.Features_details(None, None, None) 

          if data["features"]["fournisseur_propre"] == 2 :
             saisie_manuelle = True 
             details = Features.Features_details(None, None, None) 
          
          ajusteur_ranking , ajusteur_parametres , IA_feature = data["features"]["ajusteur_ranking"] , data["features"]["ajusteur_parametres"] , data["features"]["IA_model"] 

          try :
             cfg_features = Features(selection_fournisseur , ajusteur_ranking , ajusteur_parametres , fournisseur_propre_auto , saisie_manuelle , IA_feature, details)
             print("Toutes les paramètres souhaitées ont été pris en compte")
             return cfg_features
          except :
             print("La classe n'accepte pas ces fichiers, il y a un problème quelque part, on passe aux données par défaut") 
             selection_fournisseur , ajusteur_ranking , ajusteur_parametres , fournisseur_propre_auto , saisie_manuelle , IA_feature = False , False, False, False, False, False
             details = Features.Features_details(None, None, None) 
             cfg_features = Features(selection_fournisseur , ajusteur_ranking , ajusteur_parametres , fournisseur_propre_auto , saisie_manuelle , IA_feature, details)
             return cfg_features


          
def load_cfg_installation() -> Installation_PV :
   """
   Cette fonction a pour but de charger les configurations liées à l'installation PV, et de renvoyer une instance de la classe Installation_PV
   Si cette fonction renvoie None, le programme main doit arrêter l'extraction météo.
   """

   #On commence par charger le fichier yaml lié aux panneaux : 
   data = load_yaml(Path_config_pannels)
   if data is None :
      print("Le chargement du fichier de configuration des panneaux a échoué. Il faut absolument que les configurations des panneaux soient présentes. L'extraction météo va être arrêtée") 
      return None #Il faut voir dans le main comment gérer ce None, car on ne peut pas continuer sans les données des panneaux.
   else :
      #On a les données, on va essyaer de créer l'instance de la classe Installation_PV
      #Si une donnée est manquante, le programme va renvoyer None pour que main l'arrête systématiquement. 

      #On commence par l'onduleur :
      try :
         efficacite, plafond_puissance, pertes_cables = data["Onduleur"]["efficacite"], data["Onduleur"]["plafond_puissance"], data["Onduleur"]["pertes_cables"]
         onduleur = Installation_PV.Onduleur(plafond_puissance, efficacite, pertes_cables) 
         print("L'instance de l'onduleur a bien été créée")
      except :
         print("Les données de l'onduleur sont incompatibles avec l'instance. Ils vont pas être pris en compte.")
         onduleur = Installation_PV.Onduleur(None, None, None)  
      #On continue avec les panneaux : l'idée c'est de créer une liste d'instances de la classe panneau
      liste_panneaux = []
      for panneau in data["panneaux"] :
         try :
            azimuth = panneau['azimuth'] 
            tilt = panneau['tilt']
            surface_panneau = panneau["surface_panneau"] 
            puissance_nominale = panneau["puissance_nominale"]
            panneau_instance = Installation_PV.Panneau(azimuth, tilt, surface_panneau, puissance_nominale) 
            liste_panneaux.append(panneau_instance)
            print('Une instance de panneau a bien été crée et ajoutée à la liste des panneaux') 
         except :
            print("Les données d'un panneau ne respectent pas le format de la classe panneau, ce panneau ne sera pas pris en compte.")
            return None 
      #On a la liste des panneaux et l'instance de l'onduleur, on crée l'instance de l'installation PV
      rendement_global = data["rendement_global"] 
      try :
         cfg_installation = Installation_PV(liste_panneaux, onduleur, rendement_global) 
         print("L'instance de l'installation PV a bien été créée")
         return cfg_installation
      except :
         print("Les données de l'installation PV ne respectent pas le format de la classe Installation_PV, l'extraction météo va être arrêtée.")
         return None




def load_providers() -> list[str] :
   """
   Cette fonction charge les fournisseurs météo depuis le fichier providers.yaml et renvoie une liste de strings.
   Si le chargement échoue, la fonction renvoie None.
   """
   data = load_yaml(Path_config_providers) 
   if data is None :
      print("Le chargement du fichier des fournisseurs a échoué, on ne peut pas continuer l'extraction météo")
      return None 
   else :
      try :
         liste_fournisseurs = data["fournisseurs"] 
         print("La liste des fournisseurs a bien été extraite")
         return liste_fournisseurs
      except :
         print("Le format des données ne respecte pas ce qu'on attendait, on ne peut pas continuer l'extraction météo")
         return None






          



    

