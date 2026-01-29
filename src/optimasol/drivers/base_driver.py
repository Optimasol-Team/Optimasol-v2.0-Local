from abc import ABC, abstractmethod

class BaseDriver(ABC):
    DRIVER_TYPE_ID = None 
    def __init__(self, **kwargs):
        """
        :param kwargs: Les arguments dynamiques venant du formulaire
        """
        self.config = kwargs  # On stocke tout le dictionnaire
        
        self.on_receive_temperature = None
        self.on_receive_production = None
        self.on_receive_power = None
        
    
    @staticmethod
    @abstractmethod
    def get_driver_def():
        """
        Renvoie la définition complète du driver pour l'UI.
        Doit retourner un dictionnaire avec la structure suivante :
        {
            "id": str,          # Identifiant unique technique (ex: 'my_driver')
            "name": str,        # Nom affiché à l'utilisateur
            "description": str, # Courte description
            "icon_path": str,   # Chemin absolu vers l'image/icone
            
            # Schéma pour construire le formulaire de configuration dynamiquement
            "form_schema": [
                {
                    "key": str,         # Nom de l'argument dans __init__ (ex: 'serial_number')
                    "label": str,       # Libellé affiché (ex: 'Numéro de Série')
                    "type": str,        # 'text', 'number', 'password', 'select'
                    "required": bool,   # True ou False
                    "default": any,     # (Optionnel) Valeur par défaut
                    "options": list,    # (Optionnel) Pour type 'select' uniquement : [('val1', 'Label1'), ...]
                    "help": str         # (Optionnel) Petit texte d'aide
                },
                # ... autres champs ...
            ]
        }
        """
        pass


    @abstractmethod
    def start(self):
        """Démarre la connexion et le thread d'écoute"""
        pass

    @abstractmethod
    def send_decision(self, power_watt):
        """Envoie une consigne de puissance"""
        pass 

    @abstractmethod
    def device_to_dict(self) -> dict :
        """Doit renvoyer les informations de ce device. Cela est utile dans la BDD pour garantir la persistence.""" 
        pass 
    
    @classmethod 
    @abstractmethod
    def dict_to_device(cls, data: dict) -> BaseDriver :
        """Doit recréer une instance de ce device à partir des données stockées dans la BDD.""" 
        pass