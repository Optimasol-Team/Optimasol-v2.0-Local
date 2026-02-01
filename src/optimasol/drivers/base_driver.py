from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)

class BaseDriver(ABC):
    """Abstract base class that all driver implementations must inherit from.
    
    This class defines the contract that all device drivers must implement to
    integrate with the optimization system. Drivers handle communication with
    physical devices, receiving sensor data and sending control decisions.
    
    Attributes:
        DRIVER_TYPE_ID (str or None): Unique identifier for the driver type.
            Must be set by concrete implementations.
        config (dict): Configuration parameters passed during initialization.
        on_receive_temperature (callable or None): Callback function for temperature updates.
        on_receive_production (callable or None): Callback function for production updates.
        on_receive_power (callable or None): Callback function for power consumption updates.
    
    Note:
        All abstract methods must be implemented by concrete driver classes.
        Callbacks should be set by the client before calling start().
    """

    DRIVER_TYPE_ID = None 
    def __init__(self, **kwargs):
        """Initialize the driver with dynamic configuration parameters.
        
        Args:
            **kwargs: Dynamic configuration arguments from the user interface form.
                These are stored in the config dictionary and can include any
                driver-specific parameters defined in get_driver_def().
        """
        logger.debug("Initializing %s driver with config: %s", self.__class__.__name__, kwargs)
        self.config = kwargs  # On stocke tout le dictionnaire
        
        self.on_receive_temperature = None
        self.on_receive_production = None
        self.on_receive_power = None
        logger.debug("%s driver initialized successfully", self.__class__.__name__)
        
    
    @staticmethod
    @abstractmethod
    def get_driver_def():
        """Return the complete driver definition for the user interface.
        
        This method provides metadata about the driver including its identification,
        display information, and a dynamic form schema for configuration. The UI
        uses this information to generate the configuration form automatically.
        
        Returns:
            dict: Driver definition with the following structure:
                {
                    "id": str,          # Unique technical identifier (e.g., 'my_driver')
                    "name": str,        # Display name shown to the user
                    "description": str, # Brief description of the driver
                    "icon_path": str,   # Absolute path to the icon/image file
                    
                    # Schema for building the configuration form dynamically
                    "form_schema": [
                        {
                            "key": str,         # Argument name in __init__ (e.g., 'serial_number')
                            "label": str,       # Display label (e.g., 'Serial Number')
                            "type": str,        # Input type: 'text', 'number', 'password', 'select'
                            "required": bool,   # True or False
                            "default": any,     # (Optional) Default value
                            "options": list,    # (Optional) For 'select' type only: [('val1', 'Label1'), ...]
                            "help": str         # (Optional) Help text for the field
                        },
                        # ... additional fields ...
                    ]
                }
        
        Note:
            This is a static method that must be implemented by all concrete drivers.
            The form_schema defines the configuration parameters that will be passed
            as **kwargs to __init__().
        """
        pass


    @abstractmethod
    def start(self):
        """Start the connection and listening thread.
        
        Initializes the communication with the device and starts any background
        threads or event loops necessary for receiving data.
        
        Note:
            Must be implemented by concrete driver classes.
            Should be called after callback functions are registered.
        """
        pass

    @abstractmethod
    def send_decision(self, power_watt):
        """Send a power setpoint to the device.
        
        Transmits the optimization decision (power setpoint) to the controlled device.
        
        Args:
            power_watt: Power setpoint value, typically in watts.
        
        Note:
            Must be implemented by concrete driver classes.
            The exact type and format of power_watt may vary by driver implementation.
        """
        pass 

    @abstractmethod
    def device_to_dict(self) -> dict:
        """Serialize device information to a dictionary.
        
        Converts the driver instance and its configuration to a dictionary format
        suitable for database storage, ensuring persistence.
        
        Returns:
            dict: Serialized device information including all necessary data to
                recreate the driver instance later.
        
        Note:
            Must be implemented by concrete driver classes.
            Should include all configuration and state needed for dict_to_device().
        """
    
    @classmethod 
    @abstractmethod
    def dict_to_device(cls, data: dict) -> 'BaseDriver':
        """Recreate a driver instance from serialized data.
        
        Factory method to reconstruct a driver instance from data previously
        stored in the database via device_to_dict().
        
        Args:
            data (dict): Serialized device information from the database.
        
        Returns:
            BaseDriver: A new instance of the driver class with restored configuration.
        
        Note:
            Must be implemented by concrete driver classes.
            Should be the inverse operation of device_to_dict().
        """
        pass