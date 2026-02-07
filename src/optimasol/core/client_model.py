from optimiser_engine import Client as Clt_engine
from weather_manager import Client as Clt_weather
from ..drivers import BaseDriver
from datetime import datetime, timezone
from optimiser_engine import OptimizerService
import logging

logger = logging.getLogger(__name__)


class Client:
    """Represents a client with optimization and monitoring capabilities.
    
    This class integrates client information from multiple sources (optimization engine,
    weather manager, and device driver) to manage real-time data collection and perform
    optimization decisions.
    
    Attributes:
        Static:
            CONFIG_OPTIMISATION (dict): Optimization configuration injected at runtime.
            HORIZON_HOURS (int): Optimization time horizon in hours (default: 24).
            STEP_MINUTES (int): Optimization time step in minutes (default: 15).
        
        Instance (Static Data):
            client_id (int): Unique identifier for the client.
            client_engine (Clt_engine): Client instance for the optimization engine.
            client_weather (Clt_weather): Client instance for weather data management.
            driver (BaseDriver): Communication driver for the client's device.
        
        Instance (Dynamic Data):
            last_temperature (float or None): Most recent temperature reading in °C.
            last_temperature_time (datetime or None): UTC timestamp of temperature reading.
            last_production (float or None): Most recent production reading.
            last_production_time (datetime or None): UTC timestamp of production reading.
            last_power (float or None): Most recent power consumption reading.
            last_power_time (datetime or None): UTC timestamp of power reading.
            production_forecast (array-like or None): Photovoltaic production forecast.
    
    Capabilities:
        - Monitor real-time temperature, power consumption, and production data
        - Check readiness for optimization process
        - Execute optimization: compute optimal decision and send to device
    """


    CONFIG_OPTIMISATION = {"horizon": 24, "step_minutes": 15}
    HORIZON_HOURS = 24
    STEP_MINUTES = 15

    def __init__(
        self,
        client_id: int,
        client_engine: Clt_engine,
        client_weather: Clt_weather,
        driver: BaseDriver,
        start_driver: bool = True,
    ):
        """Initialize a Client instance.
        
        Sets up the client with required components and initializes data collection
        by wiring callback hooks and starting the communication driver.
        
        Args:
            client_id (int): Unique identifier for the client.
            client_engine (Clt_engine): Optimization engine client instance.
            client_weather (Clt_weather): Weather manager client instance.
            driver (BaseDriver): Communication driver for the client's device.
        
        Note:
            The driver is automatically started during initialization, and callback
            hooks are registered to capture incoming data (temperature, production, power).
        """
        logger.debug("Initializing Client with ID %s", client_id)
        
        self.client_id = client_id
        self.client_engine = client_engine
        self.client_weather = client_weather
        self.driver = driver
        

        # On stocke la Valeur ET l'Instant (Time) de réception
        
        # Température
        self.last_temperature = None
        self.last_temperature_time = None # Timestamp UTC
        
        # Production
        self.last_production = None
        self.last_production_time = None # Timestamp UTC
        
        # Puissance (Power)
        self.last_power = None
        self.last_power_time = None # Timestamp UTC

        # --- 2. CÂBLAGE (HOOKS) ---
        self.driver.on_receive_temperature = self._update_temperature
        self.driver.on_receive_production = self._update_production
        self.driver.on_receive_power = self._update_power
        self.production_forecast = None 
        logger.debug("Client %s: callback hooks registered", client_id)
        if start_driver:
            self.driver.start()  # Démarrer le driver.
            logger.info("Client %s initialized successfully and driver started", client_id)
        else:
            logger.info("Client %s initialized (driver not started)", client_id)

    # --- 3. LES FONCTIONS DE MISE A JOUR (Callbacks) ---
    
    def _update_temperature(self, value: float):
        """Callback to update temperature data.
        
        This method is called automatically by the driver when new temperature
        data is received. It captures both the value and the exact UTC timestamp.
        
        Args:
            value (float): Temperature reading in degrees Celsius.
        
        Note:
            This is a callback method registered during initialization and should
            not be called directly.
        """
        # 1. On capture l'heure UTC exacte MAINTENANT
        now_utc = datetime.now(timezone.utc)
        
        # 2. On met à jour les deux variables (Valeur + Temps)
        self.last_temperature = value
        self.last_temperature_time = now_utc
        
        logger.debug("Client %s: temperature updated to %.2f°C at %s", 
                    self.client_id, value, now_utc.isoformat())

    def _update_production(self, value: float):
        """Callback to update production data.
        
        This method is called automatically by the driver when new production
        data is received. It captures both the value and the exact UTC timestamp.
        
        Args:
            value (float): Production reading (typically in kW or kWh).
        
        Note:
            This is a callback method registered during initialization and should
            not be called directly.
        """
        now_utc = datetime.now(timezone.utc)
        self.last_production = value
        self.last_production_time = now_utc
        logger.debug("Client %s: production updated to %.2f at %s", 
                    self.client_id, value, now_utc.isoformat())

    def _update_power(self, value: float):
        """Callback to update power consumption data.
        
        This method is called automatically by the driver when new power consumption
        data is received. It captures both the value and the exact UTC timestamp.
        
        Args:
            value (float): Power consumption reading (typically in kW).
        
        Note:
            This is a callback method registered during initialization and should
            not be called directly.
        """
        now_utc = datetime.now(timezone.utc)
        self.last_power = value
        self.last_power_time = now_utc
        logger.debug("Client %s: power consumption updated to %.2f at %s", 
                    self.client_id, value, now_utc.isoformat())
    
    def decision(self):
        """Compute optimal decision for the client.
        
        Uses the optimization engine to calculate the optimal control trajectory
        based on current temperature and production forecast, then returns the
        first (immediate) decision.
        
        Returns:
            Decision: The immediate optimal decision from the optimization engine.
        
        Note:
            Requires that temperature data and production forecast are available.
            Uses class-level HORIZON_HOURS and STEP_MINUTES for optimization parameters.
        """
        logger.info("Optimisation: appel solveur pour client %s", self.client_id)
        now = datetime.now(timezone.utc)
        service = OptimizerService(Client.HORIZON_HOURS, Client.STEP_MINUTES) 

        trajectory = service.trajectory_of_client(self.client_engine, now, self.last_temperature, self.production_forecast) 

        decision = trajectory.get_decisions()[0] 
        logger.info("Optimisation: décision calculée pour client %s -> %.3f", self.client_id, decision)

        return decision 

    @property
    def is_ready(self):
        """Check if client has all required data for optimization.
        
        Verifies that both temperature data and production forecast are available,
        which are the minimum requirements for running the optimization process.
        
        Returns:
            bool: True if temperature and production forecast are available, False otherwise.
        """
        return (self.last_temperature is not None and 
                self.production_forecast is not None)

    def process(self):
        """Execute the optimization process for the client.
        
        Performs the complete optimization workflow:
        1. Checks data readiness (temperature and production forecast)
        2. Computes optimal decision using the optimization engine
        3. Sends the decision to the client's device via the driver
        
        Returns:
            None: Returns early if required data is not available.
        
        Note:
            This method handles errors gracefully and logs warnings when data is
            unavailable or when the optimization process fails.
        """
        # SÉCURITÉ : On ne fait rien si on n'a pas les données
        if not self.is_ready:
            logger.warning("Client %s: optimization process skipped - waiting for data (temperature: %s, forecast: %s)",
                         self.client_id, 
                         self.last_temperature is not None,
                         self.production_forecast is not None)
            return

        logger.info("Client %s: starting optimization process", self.client_id)
        try:
            decision = self.decision() 
            self.driver.send_decision(decision)
            logger.info("Client %s: optimization process completed and decision sent successfully", self.client_id)
        except Exception as e:
            logger.error("Client %s: optimization process failed - %s", self.client_id, e, exc_info=True)


    


        
