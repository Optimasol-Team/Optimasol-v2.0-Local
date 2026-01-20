from .client_model import Client
from pathlib import Path 
import math 
import pandas as pd 
from weather_manager import get_forecast_for_client, Converter
from datetime import datetime, timedelta 
class ClientAlreadyExists(Exception) :
    pass 

class AllClients :
    """Contient les informations sur touts les clients"""
    BASE_DIR = Path(__file__).parent.parent 
    DIR_CONFIG = BASE_DIR / "config" / "min_distance_weather.json" 
    @staticmethod 
    def load_min_distance_config() :
        import json 
        try:
            with open(AllClients.DIR_CONFIG, 'r') as f:
                config = json.load(f)
            return config["minimal_distance"] 
        except Exception as e:
            return 1 # Valeur par défaut
    
    MINIMAL_DISTANCE = load_min_distance_config() 
    
    def __init__(self) :
        self.list_of_clients = []
        self.clients_with_leaders = []
        self.leaders = []
        self.weather_infos = None 
        
    @property 
    def weather_infos(self) :
        return self._weather_infos 
    @weather_infos.setter
    def weather_infos(self, info) :
        # Check si info est soit none soit un DF pandas : 
        if not isinstance(info, dict) and info is not None :
            raise TypeError("Les informations météo doivent être un dict ou None")
        self._weather_infos = info
    
    def add(self, client) : 
        if not isinstance(client, Client) :
            raise TypeError("L'objet à ajouter doit être de type Client") 
        for clt in self.list_of_clients :
            if clt.client_id == client.client_id :
                raise ClientAlreadyExists("Ce client existe déjà, essayez avec un autre ID")
        
        closest_leader = self._closest_leader(client) 

        if closest_leader is None :
            self.list_of_clients.append(client) 
            self.clients_with_leaders.append((client, client)) 
            self.leaders.append(client) 
        else :
            self.list_of_clients.append(client) 
            self.clients_with_leaders.append((client, closest_leader)) 

    def which_client_by_id(self, ID : int) :
        """Recherche dans la liste des clients et retourne le client qui a ce ID, sinon None"""
        for client in self.list_of_clients :
            if client.client_id == ID :
                return client 
        return None  

    def delete_client(self, client : Client) :
        if client in self.list_of_clients :
            self.list_of_clients.remove(client)   
        
    def _closest_leader(self, client):
        if not self.leaders:
            return None

        lat1 = client.client_weather.position.latitude
        lon1 = client.client_weather.position.longitude

        def dist_km(c):
            R = 6371
            lat2 = c.client_weather.position.latitude
            lon2 = c.client_weather.position.longitude

            phi1, phi2 = map(math.radians, [lat1, lat2])
            dphi = math.radians(lat2 - lat1)
            dl = math.radians(lon2 - lon1)

            a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dl/2)**2
            return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        candidates = [(dist_km(l), l) for l in self.leaders]
        
        if not candidates:
            return None
            
        # On trouve le tuple avec la plus petite distance
        min_dist, best_leader_obj = min(candidates, key=lambda x: x[0])

        # On retourne l'OBJET, pas la distance
        return best_leader_obj if min_dist < AllClients.MINIMAL_DISTANCE else None
        
    def update_forecasts(self) :
        dico = {}
        for leader in self.leaders :
            try :
                forecast = get_forecast_for_client(leader.client_weather, datetime.now(), datetime.now() + timedelta(days=2)) 
                dico[leader.client_id] = forecast 
            except Exception as e :
                print(f"Échec pour ce leader {leader.client_id}") 
        
        self.weather_infos = dico 

    def leader_id_of_client(self, client) :
        for x in self.clients_with_leaders :
            if x[0] == client :
                return x[1].client_id

    def update_production_client(self, client) :
        leader_id = self.leader_id_of_client(client) 
        panda_df = self.weather_infos[leader_id] 
        converter = Converter() 
        productions = converter.convert(panda_df, client.client_weather) 
        client.production_forecast = productions 
        
    def update_weather(self) :
        self.update_forecasts() 
        for client in self.list_of_clients :
            self.update_production_client(client) 
    

    def __repr__(self) :
        return f"AllClients with {len(self.list_of_clients)} clients, {len(self.leaders)} leaders"

    
