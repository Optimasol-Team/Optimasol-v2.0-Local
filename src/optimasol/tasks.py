from datetime import datetime, timezone

import logging

import numpy as np
import pandas as pd
from weather_manager import ForecastEvaluator

from .core import AllClients, Client
from .database import DBManager

logger = logging.getLogger(__name__)


def _nearest_forecast_point(df: pd.DataFrame | pd.Series | None, ref_time: datetime) -> tuple[float | None, datetime | None]:
    """Retourne la production et l'horodatage le plus proche de ``ref_time``."""
    if df is None:
        return None, None

    if hasattr(df, "empty") and getattr(df, "empty"):
        return None, None

    # Normalisation des données
    if isinstance(df, pd.Series):
        values = df
        times = df.index
    else:
        if not isinstance(df, pd.DataFrame):
            return None, None

        if "production" in df.columns:
            values = df["production"]
        elif "productions" in df.columns:
            values = df["productions"]
        else:
            values = df.iloc[:, 0]

        if isinstance(df.index, pd.DatetimeIndex):
            times = df.index
        else:
            time_col = next((c for c in ("Datetime", "time", "timestamp") if c in df.columns), None)
            if time_col is None:
                return None, None
            times = df[time_col]

    times = pd.to_datetime(times, utc=True)
    if times.empty:
        return None, None

    deltas = times - ref_time
    try:
        delta_vals = np.abs(deltas.to_numpy(dtype="timedelta64[ns]").astype("int64"))
    except Exception:
        delta_vals = np.array([abs((t - ref_time).total_seconds()) for t in times])
    idx = int(delta_vals.argmin())
    nearest_time = times[idx].to_pydatetime()
    nearest_value = float(values.iloc[idx]) if hasattr(values, "iloc") else float(values[idx])
    return nearest_value, nearest_time


# Mise à jour Météo (tâche périodique)
def update_weather(all_clients: AllClients, db_manager: DBManager):
    """Met à jour la météo/production et enregistre la prévision la plus proche de maintenant."""
    now_utc = datetime.now(timezone.utc)
    try:
        all_clients.update_forecasts()
        logger.info("Météo: mise à jour des prévisions réussie")
    except Exception as exc:  # noqa: BLE001
        logger.error("Météo: mise à jour échouée: %s", exc, exc_info=True)
        return

    for client in all_clients.list_of_clients:
        try:
            all_clients.update_production_client(client)
            logger.info("Météo->PV: conversion réussie pour client %s", client.client_id)
        except Exception as exc:  # noqa: BLE001
            logger.error("Météo->PV: conversion échouée pour client %s: %s", client.client_id, exc, exc_info=True)
            continue

        production, production_time = _nearest_forecast_point(client.production_forecast, now_utc)
        if production is None or production_time is None:
            continue
        db_manager.reporter.report_production_forecast(client.client_id, production, production_time)


def reports_data(all_clients: AllClients, db_manager: DBManager):
    """Reporte les mesures (température, puissance, production) vers la BDD."""
    for client in all_clients.list_of_clients:
        temperature, time_temperature = client.last_temperature, client.last_temperature_time
        power, power_time = client.last_power, client.last_power_time
        production, production_time = client.last_production, client.last_production_time

        if power is not None and power_time is not None:
            db_manager.reporter.report_decision_measured(client.client_id, power, power_time)
        if temperature is not None and time_temperature is not None:
            db_manager.reporter.report_temperature(client.client_id, temperature, time_temperature)
        if production is not None and production_time is not None:
            db_manager.reporter.report_production_measured(client.client_id, production, production_time)
    logger.info("Rapports de mesures envoyés à la BDD")


def correct_efficiency(all_clients: AllClients, db_manager: DBManager):
    """Corrige le rendement global pour les clients avec auto-correction activée."""
    for client in all_clients.list_of_clients:
        if not db_manager.client_manager.get_auto_correction(client.client_id):
            continue

        productions_forecast = db_manager.getter.get_production_forecast(client.client_id, 10000)
        productions_measures = db_manager.getter.get_production_measured(client.client_id, 10000)
        if productions_forecast.empty or productions_measures.empty:
            continue

        evaluator = ForecastEvaluator(productions_forecast, productions_measures)
        coef = evaluator.correction_coefficient()
        current_eff = getattr(client.client_weather.installation, "rendement_global", None)
        if coef is None or current_eff is None:
            continue

        new_efficiency = current_eff * coef
        client.client_weather.installation.rendement_global = new_efficiency
        db_manager.client_manager.update_client_weather(client.client_id, client.client_weather)
        logger.info("Rendement recalculé pour client %s (coef=%.3f)", client.client_id, coef)
