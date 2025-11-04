from __future__ import annotations
import math
import datetime as dt
from typing import Optional, Dict, Any, List

import pandas as pd
import requests
import pytz
import numpy as np


# -----------------------------
# Helpers
# -----------------------------
def _now_utc():

    return dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc)

def _to_tz(ts: pd.DatetimeIndex, tz: str) -> pd.DatetimeIndex:
    return ts.tz_convert(pytz.timezone(tz))

def _time_range(timezone: str, horizon_hours: int, step_min: int) -> (str, str):
    """Return ISO8601 start/end strings in the provider's expected timezone (mostly UTC)."""
    now = _now_utc()
    end = now + dt.timedelta(hours=horizon_hours)
    # Many APIs expect ISO8601 without microseconds in UTC
    return now.strftime("%Y-%m-%dT%H:%M"), end.strftime("%Y-%m-%dT%H:%M")

def _resample(df: pd.DataFrame, pas_de_temps: int, agg: str = "mean") -> pd.DataFrame:
    """Resample to user step in minutes with mean or asfreq if equal."""
    if len(df.index) == 0:
        return df
    rule = f"{int(pas_de_temps)}T"
    if pd.infer_freq(df.index) == rule:
        return df
    if agg == "mean":
        return df.resample(rule).mean()
    return df.resample(rule).asfreq()

def _make_frame(index: pd.DatetimeIndex,
                ghi=None, dni=None, dhi=None, t2m=None, wind=None,
                albedo=None, gti=None) -> pd.DataFrame:
    """Uniform DataFrame output with required columns."""
    data = {
        "GHI": ghi if ghi is not None else np.nan,
        "DNI": dni if dni is not None else np.nan,
        "DHI": dhi if dhi is not None else np.nan,
        "Temperature": t2m if t2m is not None else np.nan,
        "Wind": wind if wind is not None else np.nan
    }
    if albedo is not None:
        data["Albedo"] = albedo
    if gti is not None:
        data["GTI"] = gti
    df = pd.DataFrame(data, index=index)
    df.index.name = "Datetime"
    return df

# Simple/optional GTI (plane-of-array) using an isotropic diffuse model
# Needs solar zenith/azimuth; to stay dependency-light we skip full astro calc.
# If the API already provides GTI (e.g., some Open-Meteo endpoints), prefer that.
def _gti_isotropic(ghi, dni, dhi, solar_zenith_deg, tilt_deg):
    """
    Minimalist isotropic model:
    POA = DNI * cos(theta_i) + DHI * (1 + cos(tilt))/2 + GHI * rho_g * (1 - cos(tilt))/2
    Here we omit ground-reflected (rho_g) unless you pass an albedo separately upstream.
    This placeholder requires solar geometry we do not compute here; kept for extension.
    """
    return None  # intentionally not used without proper sun position


#1) Open-Meteo (free, no key)
# Docs: Weather/Solar/Ensemble APIs incl. GHI/DNI/DHI/GTI
# https://open-meteo.com/en/docs  |  https://open-meteo.com/en/docs/ensemble-api
# -----------------------------
def open_meteo(latitude: float, longitude: float, altitude: float, timezone: str,
               horizon: int, pas_de_temps: int,
               azimuth: Optional[float] = None, tilt: Optional[float] = None,
               **kwargs) -> pd.DataFrame:
    """
    Uses Open-Meteo forecast API with solar variables (GHI/DNI/DHI).
    If GTI is available in your chosen endpoint (e.g., Ensemble API), you can switch the base URL.
    """
    # Choose base API (standard forecast has GHI/DNI/DHI; ensemble can offer GTI)
    base = "https://api.open-meteo.com/v1/forecast"  # GHI/DNI/DHI available
    # If you want GTI from the ensemble endpoint, toggle next line:
    # base = "https://ensemble-api.open-meteo.com/v1/ensemble"

    start_iso, end_iso = _time_range(timezone, horizon, pas_de_temps)

    hourly_vars = [
        "shortwave_radiation",            # GHI surrogate (W/m^2, integrated per time step)
        "direct_normal_irradiance",       # DNI (W/m^2)
        "diffuse_radiation",              # DHI (W/m^2)
        "temperature_2m",                 # °C
        "windspeed_10m"                   # m/s
    ]

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": ",".join(hourly_vars),
        "timezone": "UTC",
        "start_hour": start_iso,
        "end_hour": end_iso,
        "elevation": altitude,
    }

    r = requests.get(base, params=params, timeout=30)
    r.raise_for_status()
    js = r.json()

    # Parse
    times = pd.to_datetime(js["hourly"]["time"], utc=True)
    ghi = pd.Series(js["hourly"]["shortwave_radiation"], index=times)
    dni = pd.Series(js["hourly"]["direct_normal_irradiance"], index=times)
    dhi = pd.Series(js["hourly"]["diffuse_radiation"], index=times)
    t2m = pd.Series(js["hourly"]["temperature_2m"], index=times)
    wind = pd.Series(js["hourly"]["windspeed_10m"], index=times)

    df = _make_frame(times, ghi, dni, dhi, t2m, wind)
    # Convert to requested TZ and resample
    df = df.tz_convert(pytz.timezone(timezone))
    df = _resample(df, pas_de_temps, "mean")

    # Optional: if endpoint provided GTI, you could add it as df["GTI"] = ...
    return df

import pandas as pd


