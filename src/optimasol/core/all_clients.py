from .client_model import Client
import math
import pandas as pd
from weather_manager.get_forecasts import get_forecast_for_client
from weather_manager.irradiance_converter import Converter
from datetime import datetime, timedelta

import logging 

logger = logging.getLogger(__name__) 

class ClientAlreadyExists(Exception):
    """Exception raised when attempting to add a client that already exists.
    
    This exception is raised when trying to add a client with an ID that
    is already present in the AllClients collection.
    """
    pass 

class AllClients:
    """Manages collection of all clients and their associated leaders.
    
    This class handles client management, including storing client information,
    managing leader-follower relationships based on geographic proximity, and
    updating weather forecasts for all clients.
    
    Attributes:
        MINIMAL_DISTANCE (float): Minimum distance threshold in kilometers for
            leader assignment, injected at runtime.
        list_of_clients (list): List of all Client objects.
        clients_with_leaders (list): List of tuples mapping each client to its leader.
        leaders (list): List of Client objects that serve as weather data leaders.
        weather_infos (dict): Dictionary mapping leader IDs to their weather forecasts.
    """
    MINIMAL_DISTANCE = 1.0
    
    def __init__(self):
        """Initialize AllClients container.
        
        Creates empty collections for clients, client-leader mappings, leaders,
        and weather information.
        """
        self.list_of_clients = []
        self.clients_with_leaders = []
        self.leaders = []
        self.weather_infos = None 
        logger.debug("AllClients object initialized successfully") 
        
    @property 
    def weather_infos(self):
        """Get weather information dictionary.
        
        Returns:
            dict or None: Dictionary mapping leader IDs to weather forecast data,
                or None if weather data hasn't been loaded yet.
        
        Note:
            Logs a warning if accessed before weather data is available.
        """
        if self._weather_infos is None:
            logger.warning("Weather information accessed but not yet available (None)")
        else:
            logger.debug("Weather information accessed successfully")
        return self._weather_infos 
    
    @weather_infos.setter
    def weather_infos(self, info):
        """Set weather information dictionary.
        
        Args:
            info (dict or None): Weather forecast data dictionary mapping leader IDs
                to their forecasts, or None to clear weather data.
        
        Raises:
            TypeError: If info is neither a dict nor None.
        """
        # Check si info est soit none soit un DF pandas : 
        if not isinstance(info, dict) and info is not None:
            logger.error("Failed to set weather information: value must be a dict or None, got %s", type(info).__name__)
            raise TypeError("Les informations météo doivent être un dict ou None")
        logger.info("Weather information updated successfully")
        self._weather_infos = info
    
    def add(self, client):
        """Add a new client to the collection.
        
        Adds a client and assigns it to the nearest leader based on geographic
        proximity. If no leader exists within the minimal distance threshold,
        the client becomes a new leader.
        
        Args:
            client (Client): The client object to add.
        
        Raises:
            TypeError: If the provided object is not a Client instance.
            ClientAlreadyExists: If a client with the same ID already exists.
        
        Note:
            Clients within MINIMAL_DISTANCE of an existing leader will be assigned
            to that leader. Otherwise, they become leaders themselves.
        """
        if not isinstance(client, Client):
            logger.error("Failed to add client: object must be of type Client, got %s", type(client).__name__)
            raise TypeError("L'objet à ajouter doit être de type Client")
        for clt in self.list_of_clients:
            if clt.client_id == client.client_id:
                logger.error("Failed to add client: client ID %s already exists", client.client_id)
                raise ClientAlreadyExists("Ce client existe déjà, essayez avec un autre ID")
        
        closest_leader = self._closest_leader(client)

        if closest_leader is None:
            self.list_of_clients.append(client)
            self.clients_with_leaders.append((client, client))
            self.leaders.append(client)
            logger.info("Client %s added as new leader (no nearby leaders found)", client.client_id)
        else:
            self.list_of_clients.append(client)
            self.clients_with_leaders.append((client, closest_leader))
            logger.info("Client %s added and assigned to leader %s", client.client_id, closest_leader.client_id) 

    def which_client_by_id(self, ID: int):
        """Find and return a client by their ID.
        
        Searches through the list of clients and returns the client matching
        the provided ID.
        
        Args:
            ID (int): The unique identifier of the client to find.
        
        Returns:
            Client or None: The Client object with matching ID, or None if not found.
        """
        for client in self.list_of_clients:
            if client.client_id == ID:
                logger.debug("Client found with ID %s", ID)
                return client
        logger.debug("No client found with ID %s", ID)
        return None  

    def delete_client(self, client: Client):
        """Remove a client from the collection.
        
        Removes the specified client from the list of clients if present.
        Does not modify leader assignments or leader list.
        
        Args:
            client (Client): The client object to remove.
        
        Note:
            This method only removes the client from list_of_clients. It does not
            update clients_with_leaders or leaders lists. Use with caution.
        """
        if client in self.list_of_clients:
            self.list_of_clients.remove(client)
            logger.info("Client %s removed from collection", client.client_id)
        else:
            logger.warning("Attempted to remove client %s that does not exist in collection", client.client_id)   
        
    def _closest_leader(self, client):
        """Find the closest leader within the minimal distance threshold.
        
        Calculates the geographic distance from the given client to all existing
        leaders using the Haversine formula. Returns the closest leader if within
        the MINIMAL_DISTANCE threshold.
        
        Args:
            client (Client): The client for which to find the nearest leader.
        
        Returns:
            Client or None: The closest leader Client object if within threshold,
                otherwise None.
        
        Note:
            Uses the Haversine formula to calculate great-circle distances between
            geographic coordinates. Earth radius is assumed to be 6371 km.
        """
        if not self.leaders:
            logger.debug("No leaders available for client %s", client.client_id)
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
        if min_dist < AllClients.MINIMAL_DISTANCE:
            logger.debug("Closest leader for client %s is %s at %.2f km", 
                        client.client_id, best_leader_obj.client_id, min_dist)
            return best_leader_obj
        else:
            logger.debug("No leader within minimal distance (%.2f km) for client %s; closest was %.2f km", 
                        AllClients.MINIMAL_DISTANCE, client.client_id, min_dist)
            return None
        
    def update_forecasts(self):
        """Update weather forecasts for all leaders.
        
        Fetches weather forecasts for all leader clients for the next 2 days
        and stores them in the weather_infos dictionary.
        
        Note:
            Failed forecast retrievals are logged but do not stop the update process.
            Leaders with failed forecasts will not have entries in weather_infos.
        """
        logger.info("Starting weather forecast update for %d leader(s)", len(self.leaders))
        dico = {}
        success_count = 0
        today = datetime.now().date()
        end_date = today + timedelta(days=2)
        for leader in self.leaders:
            try:
                forecast = get_forecast_for_client(leader.client_weather, today, end_date)
                dico[leader.client_id] = forecast
                success_count += 1
                logger.debug("Weather forecast retrieved successfully for leader %s", leader.client_id)
            except Exception as e:
                logger.error("Failed to retrieve weather forecast for leader %s: %s", leader.client_id, e)
        
        self.weather_infos = dico
        logger.info("Weather forecast update completed: %d/%d leaders updated successfully", 
                   success_count, len(self.leaders)) 

    def leader_id_of_client(self, client):
        """Get the leader ID for a specific client.
        
        Searches the client-leader mapping to find which leader is assigned
        to the given client.
        
        Args:
            client (Client): The client whose leader ID to retrieve.
        
        Returns:
            int or None: The leader's client ID, or None if client not found.
        """
        for x in self.clients_with_leaders:
            if x[0] == client:
                logger.debug("Leader ID %s found for client %s", x[1].client_id, client.client_id)
                return x[1].client_id
        logger.warning("No leader found for client %s in clients_with_leaders mapping", client.client_id)
        return None

    def update_production_client(self, client):
        """Update production forecast for a specific client.
        
        Retrieves the weather forecast from the client's assigned leader and
        converts it to a production forecast specific to the client's location
        and configuration.
        
        Args:
            client (Client): The client whose production forecast to update.
        
        Note:
            Requires weather_infos to be populated via update_forecasts() first.
            Updates the client's production_forecast attribute in place.
        """
        leader_id = self.leader_id_of_client(client)
        logger.debug("Updating production forecast for client %s using leader %s", 
                    client.client_id, leader_id)
        panda_df = self.weather_infos[leader_id]
        converter = Converter()
        productions = converter.convert(panda_df, client.client_weather)

        # Normalise output for optimiser_engine: datetime index only (no mixed int/Timestamp index).
        if isinstance(productions, pd.DataFrame):
            if "Datetime" in productions.columns:
                productions = productions.copy()
                productions["Datetime"] = pd.to_datetime(
                    productions["Datetime"], utc=True, errors="coerce"
                )
                productions = productions.dropna(subset=["Datetime"]).set_index("Datetime")
            elif not isinstance(productions.index, pd.DatetimeIndex):
                idx = pd.to_datetime(productions.index, utc=True, errors="coerce")
                if getattr(idx, "notna", None) is not None:
                    mask = idx.notna()
                    productions = productions.loc[mask].copy()
                    idx = idx[mask]
                productions.index = idx

            if isinstance(productions.index, pd.DatetimeIndex):
                if productions.index.tz is None:
                    productions.index = productions.index.tz_localize("UTC")
                else:
                    productions.index = productions.index.tz_convert("UTC")
                productions = productions.sort_index()

            if "production" in productions.columns:
                productions["production"] = pd.to_numeric(
                    productions["production"], errors="coerce"
                )
                productions = productions.dropna(subset=["production"])

        client.production_forecast = productions
        logger.debug("Production forecast updated successfully for client %s", client.client_id) 
        
    def update_weather(self):
        """Update weather forecasts and production forecasts for all clients.
        
        This is the main method to refresh all weather-related data. It first
        updates weather forecasts for all leaders, then updates production
        forecasts for all clients based on their assigned leaders.
        
        Process:
            1. Fetch fresh weather forecasts for all leaders
            2. Convert weather data to production forecasts for each client
        
        Note:
            This operation may take time proportional to the number of leaders
            and clients, as it involves external API calls and conversions.
        """
        logger.info("Starting complete weather update for all clients")
        self.update_forecasts()
        logger.info("Updating production forecasts for %d client(s)", len(self.list_of_clients))
        for client in self.list_of_clients:
            try:
                self.update_production_client(client)
            except Exception as e:
                logger.error("Failed to update production forecast for client %s: %s", 
                           client.client_id, e)
        logger.info("Weather update completed for all clients") 
    

    def __repr__(self):
        """Return string representation of AllClients object.
        
        Returns:
            str: Summary string showing number of clients and leaders.
        """
        return f"AllClients with {len(self.list_of_clients)} clients, {len(self.leaders)} leaders"
