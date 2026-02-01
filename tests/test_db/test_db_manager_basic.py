import datetime as dt
from pathlib import Path

import pytest
import yaml

from optimasol.database import DBManager


def _insert_minimal_client(mgr: DBManager, client_id: int = 1):
    """Insert minimal driver and user rows to satisfy foreign keys."""
    driver_id = 1
    driver_name = "smart_electromation_mqtt"
    mgr.execute_commit(
        "INSERT OR IGNORE INTO Drivers (driver_id, nom_driver) VALUES (?, ?)",
        (driver_id, driver_name),
    )

    config_engine = yaml.safe_dump(
        {
            "water_heater": {"volume": 0, "power": 0},
            "prices": {"mode": "BASE", "base_price": 0},
            "features": {"mode": "cost", "gradation": False},
            "constraints": {},
            "planning": [],
            "client_id": client_id,
        },
        sort_keys=False,
    )

    config_weather = yaml.safe_dump(
        {
            "client_id": client_id,
            "position": {"latitude": 0.0, "longitude": 0.0, "altitude": 0.0},
            "installation": {"rendement_global": 1.0, "liste_panneaux": []},
        },
        sort_keys=False,
    )

    config_driver = yaml.safe_dump({"serial_number": "UNITTEST"}, sort_keys=False)

    mgr.execute_commit(
        """
        INSERT OR REPLACE INTO users_main
        (id, weather_ref, config_engine, config_weather, driver_id, config_driver)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (client_id, None, config_engine, config_weather, driver_id, config_driver),
    )


def test_tables_created(tmp_path: Path):
    db_path = tmp_path / "db_manager_test.db"
    mgr = DBManager(db_path)

    tables = {row[0] for row in mgr.execute_query("SELECT name FROM sqlite_master WHERE type='table'")}
    expected = {
        "Drivers",
        "users_main",
        "Decisions",
        "Productions",
        "temperatures",
        "decisions_measurements",
        "productions_measurements",
    }
    assert expected.issubset(tables)


def test_report_and_getters_roundtrip(tmp_path: Path):
    db_path = tmp_path / "db_roundtrip.db"
    mgr = DBManager(db_path)
    _insert_minimal_client(mgr, client_id=42)

    ts = dt.datetime.now(dt.timezone.utc)

    mgr.report_temperature(42, 17.5, ts)
    mgr.report_production_forecast(42, 250.0, ts)
    mgr.report_production_measured(42, 240.0, ts)
    mgr.report_decision_taken(42, 0.8, ts)
    mgr.report_decision_measured(42, 0.75, ts)

    temps = mgr.get_temperatures(42)
    assert not temps.empty
    assert pytest.approx(temps.iloc[-1]["temperature"]) == 17.5

    forecast = mgr.get_productions_forecasts(42)
    assert not forecast.empty
    assert pytest.approx(forecast.iloc[-1]["production"]) == 250.0

    measured = mgr.get_productions_measured(42)
    assert not measured.empty
    assert pytest.approx(measured.iloc[-1]["production"]) == 240.0

    decisions = mgr.get_decisions_taken(42)
    assert not decisions.empty
    assert pytest.approx(decisions.iloc[-1]["decision"]) == 0.8
