from __future__ import annotations

from optimasol.drivers.router_smart_electromation import SmartEMDriver
from optimiser_engine import Client as EngineClient
from weather_manager import Client as WeatherClient
from weather_manager import Installation_PV, Panneau, Position


def _engine_payload() -> dict:
    """Canonical EngineClient payload produced by optimiser_engine.Client.to_dict()."""
    consumption_profile = [[100.0 + hour for hour in range(24)] for _ in range(7)]
    return {
        "client_id": 1,
        "water_heater": {
            "volume": 200.0,
            "power": 3000.0,
            "insulation_coeff": 0.35,
            "temp_cold_water": 12.0,
        },
        "prices": {
            "mode": "BASE",
            "base_price": 0.18,
            "resell_price": 0.08,
        },
        "features": {"gradation": True, "mode": "cost"},
        "constraints": {
            "min_temp": 45.0,
            "forbidden_slots": [{"start": "12:00", "end": "13:00"}],
            "consumption_profile": consumption_profile,
            "background_noise": 300.0,
        },
        "planning": [
            {"day": 0, "time": "06:30", "target_temp": 50.0, "volume": 60.0},
            {"day": 3, "time": "18:00", "target_temp": 55.0, "volume": 40.0},
        ],
    }


def _weather_payload() -> dict:
    """Canonical WeatherClient payload produced by weather_manager.Client.to_dict()."""
    return {
        "client_id": 7,
        "position": {"latitude": 48.8566, "longitude": 2.3522, "altitude": 35.0},
        "installation": {
            "rendement_global": 0.85,
            "liste_panneaux": [
                {
                    "azimuth": 180.0,
                    "tilt": 30.0,
                    "surface_panneau": 1.6,
                    "puissance_nominale": 400.0,
                },
                {
                    "azimuth": 200.0,
                    "tilt": 28.0,
                    "surface_panneau": 1.7,
                    "puissance_nominale": 420.0,
                },
            ],
        },
    }


def test_engine_client_dict_roundtrip():
    payload = _engine_payload()

    engine_client = EngineClient.from_dict(payload)
    assert engine_client.to_dict() == payload

    rebuilt = EngineClient.from_dict(engine_client.to_dict())
    assert rebuilt.to_dict() == engine_client.to_dict()


def test_weather_client_dict_roundtrip():
    payload = _weather_payload()

    weather_client = WeatherClient.from_dict(payload)
    assert weather_client.to_dict() == payload

    rebuilt = WeatherClient.from_dict(weather_client.to_dict())
    assert rebuilt.to_dict() == weather_client.to_dict()


def test_driver_device_dict_roundtrip():
    driver = SmartEMDriver(serial_number="ROUTER-TEST-ROUNDTRIP")

    driver_dict = driver.device_to_dict()
    rebuilt = SmartEMDriver.dict_to_device(driver_dict)

    assert driver_dict == {"serial_number": "ROUTER-TEST-ROUNDTRIP"}
    assert rebuilt.device_to_dict() == driver_dict
