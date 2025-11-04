"""Ce fichier ressemble à format_general.py mais il est destiné à être utilisé pour les fournisseurs commerciaux qui donnent directement la production PV prévue.
Tu dois créer une fonction qui prend en argument : 
position : latitude, logitude, altitude, timezone
horizon, pas_de_temps
azimuth, tilt, + Des données qui te paraissent nécessaires d'après l'API. 
clé API évidemment.
Elle renvoie un dataframe pandas avec :
Datetime , Production PV prévue en W
Les programmes doivent être commentées et clairs, commentés en français ou en anglais (comme tu veux)
 """


#Imports : 
# normalement tu auras esoin de datetime et pandas, tu es libre d'importer d'autres modules si nécessaire.

from __future__ import annotations
import math
import datetime as dt
from typing import Optional, Dict, Any

import pandas as pd
import numpy as np
import pytz
# import requests  # Uncomment when enabling real API requests


# -----------------------------
# Utilities (shared)
# -----------------------------
def _now_utc() -> dt.datetime:
    
    return dt.datetime.now(dt.timezone.utc)

def _date_index(timezone: str, horizon_h: int, step_min: int) -> pd.DatetimeIndex:
    tz = pytz.timezone(timezone)
    start_utc = _now_utc()
    end_utc = start_utc + dt.timedelta(hours=horizon_h)
    
    idx_utc = pd.date_range(
        start=start_utc, end=end_utc,
        freq=f"{int(step_min)}min",
        inclusive="left", tz=dt.timezone.utc
    )
    return idx_utc.tz_convert(tz)


def _panel_orientation_factor(local_time: pd.DatetimeIndex,
                              azimuth: float, tilt: float, longitude: float) -> np.ndarray:
  
    hours = local_time.hour.to_numpy() + local_time.minute.to_numpy() / 60.0

    
    x = (hours - 12.0) / 6.0
    diurnal = np.clip(1.0 - x**2, 0.0, 1.0)

  
    az_err = abs(((azimuth - 180.0 + 180.0) % 360.0) - 180.0)
    az_factor = max(0.2, 1.0 - az_err / 180.0)

   
    tilt_opt = 32.0
    tilt_factor = max(0.3, 1.0 - abs(tilt - tilt_opt)/90.0)

    
    phase = (longitude % 15.0) / 15.0 * math.pi/8.0
    smooth_core = 0.5 * (1.0 + np.cos(np.clip((np.abs(x) - 1.0 + phase), 0, 1) * math.pi))
 
    smooth = np.where((x < -1) | (x > 1), 0.0, smooth_core)

    return diurnal * az_factor * tilt_factor * smooth

def _weather_factor(index: pd.DatetimeIndex, cloudiness: float = 0.35, wind_cooling: float = 0.05) -> np.ndarray:
    """
    Crude stochastic weather factor in [0..1], lower = cloudier.
    cloudiness ~ mean cloud attenuation; wind_cooling slightly boosts power midday.
    """
    rng = np.random.default_rng(42)  # deterministic for reproducibility
    base = 1.0 - cloudiness  # e.g., 0.65 if cloudiness=0.35
    noise = rng.normal(0, 0.08, size=len(index))

  
    hours = index.hour.to_numpy() + index.minute.to_numpy() / 60.0
    midday = np.exp(-((hours - 12.0) ** 2) / (2 * 2.5 ** 2))

 
    return np.clip(base + noise + wind_cooling * midday, 0.0, 1.0).astype(float)


def _simulate_pv_power(index_local: pd.DatetimeIndex,
                       latitude: float,
                       longitude: float,
                       azimuth: float,
                       tilt: float,
                       capacity_kwp: float,
                       losses: float = 0.12) -> pd.Series:
    """
    Simple synthetic PV power (W) time series:
    P_dc = capacity_kwp * 1000 * shape(t) * weather_factor
    P_ac = P_dc * (1 - losses)
    """
    shape = _panel_orientation_factor(index_local, azimuth, tilt, longitude)   # np.ndarray
    weather = _weather_factor(index_local)                                      # np.ndarray
    p_dc = capacity_kwp * 1000.0 * shape * weather                              # np.ndarray
    p_ac = p_dc * (1.0 - losses)                                                # np.ndarray

    #  hours 用 numpy，并用 np.where 避免对“索引/视图”原地赋值
    hours = index_local.hour.to_numpy() + index_local.minute.to_numpy() / 60.0
    night_mask = (hours < 5.5) | (hours > 21.5)
    p_ac = np.where(night_mask, 0.0, p_ac)

    return pd.Series(p_ac.astype(float), index=index_local, name="Production_PV_W")


def _ensure_output(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.index.name = "Datetime"
    # One and only required column:
    if "Production_PV_W" not in df.columns:
        raise ValueError("Output must have 'Production_PV_W' column.")
    # Sort & drop duplicates for safety
    df = df[~df.index.duplicated()].sort_index()
    return df



# 3) Meteomatics (Solar Power Forecasting via Weather API)
# =====================================================================
def meteomatics(position_latitude: float, position_longitude: float, position_altitude: float,
                position_timezone: str, horizon: int, pas_de_temps: int,
                azimuth: float, tilt: float,
                **kwargs) -> pd.DataFrame:
    """
    Meteomatics can return theoretical PV power parameter directly when given plant config.
    Inputs (when real): username/password or token, plant params, capacity, tilt/azimuth.
    """
    simulate = kwargs.get("simulate", True)
    capacity_kwp = float(kwargs.get("capacity_kwp", 5.0))
    losses = float(kwargs.get("losses", 0.12))

    idx = _date_index(position_timezone, horizon, pas_de_temps)

    if simulate:
        return _ensure_output(
            _simulate_pv_power(idx, position_latitude, position_longitude, azimuth, tilt,
                               capacity_kwp, losses).to_frame()
        )

    # --- Real API sketch (commented) ---
    # user = kwargs["username"]; pwd = kwargs["password"]
    # # Example parameter name might be 'solar_power_pv_{tilt}_{azimuth}_w' or similar per doc version.
    # # The API takes a valid ISO timeframe and coordinate path.
    # start = idx[0].astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    # end = (idx[-1].astimezone(dt.timezone.utc) + pd.Timedelta(minutes=pas_de_temps)).strftime("%Y-%m-%dT%H:%M:%SZ")
    # param = f"solar_power_pv_w:azimuth={azimuth};tilt={tilt};capacity={capacity_kwp}kW"
    # base = f"https://api.meteomatics.com/{start}--{end}:{pas_de_temps}m/{param}/{position_latitude},{position_longitude}/json"
    # r = requests.get(base, auth=(user, pwd), timeout=30)
    # r.raise_for_status()
    # js = r.json()
    # # Parse series...
    # rows = []
    # for s in js.get("data", []):
    #     for ts in s.get("coordinates", [])[0].get("dates", []):
        #         t = pd.to_datetime(ts["date"]).tz_convert(position_timezone)
        #         p_w = ts["value"]
        #         rows.append((t, p_w))
    # df = pd.DataFrame(rows, columns=["Datetime", "Production_PV_W"]).set_index("Datetime").sort_index()
    # df = df.reindex(idx, method="nearest")
    # return _ensure_output(df)

    resp = kwargs.get("response_json")
    if resp:
        rows = []
        for s in resp.get("data", []):
            for ts in s.get("coordinates", [])[0].get("dates", []):
                t = pd.to_datetime(ts["date"]).tz_convert(position_timezone)
                p_w = float(ts.get("value", 0.0))
                rows.append((t, p_w))
        df = pd.DataFrame(rows, columns=["Datetime", "Production_PV_W"]).set_index("Datetime").sort_index()
        df = df.reindex(idx, method="nearest")
        return _ensure_output(df)

    return _ensure_output(
        _simulate_pv_power(idx, position_latitude, position_longitude, azimuth, tilt,
                           capacity_kwp, losses).to_frame()
    )


# Il faut respecter l'ordre de la sortie, c'est le plus important. 
#Le dataframe doit être datetime (généralement AAAA-MM-JJ HH:MM:SS) en index, et la production PV prévue en W en colonne.
#Pour la moindre question, n'hésite pas à me demander.
#Bon courage !


