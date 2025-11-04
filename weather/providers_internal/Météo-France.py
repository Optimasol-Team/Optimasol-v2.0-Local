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


# 4) Météo-France (via Open-Meteo Météo-France endpoint; no key)
# Docs: https://open-meteo.com/en/docs/meteofrance-api
# -----------------------------
def meteo_france_via_open_meteo(latitude: float, longitude: float, altitude: float, timezone: str,
                                horizon: int, pas_de_temps: int,
                                azimuth: Optional[float] = None, tilt: Optional[float] = None,
                                **kwargs) -> pd.DataFrame:
    """
    Uses Open-Meteo's Météo-France API wrapper (AROME/ARPEGE).
    Focus on temp/wind; solar components may be limited in this endpoint → we fallback to NaN if missing.
    """
    base = "https://api.open-meteo.com/v1/meteofrance"
    start_iso, end_iso = _time_range(timezone, horizon, pas_de_temps)
    hourly_vars = [
        "temperature_2m",
        "windspeed_10m",
        # Some MF endpoints may not provide solar components directly
        "shortwave_radiation",
        "direct_normal_irradiance",
        "diffuse_radiation"
    ]
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": ",".join(hourly_vars),
        "timezone": "UTC",
        "start_hour": start_iso,
        "end_hour": end_iso
    }
    r = requests.get(base, params=params, timeout=30)
    r.raise_for_status()
    js = r.json()

    times = pd.to_datetime(js["hourly"]["time"], utc=True)
    # Build with safe getters
    def _s(key):
        return pd.Series(js["hourly"][key], index=times) if key in js["hourly"] else pd.Series(np.nan, index=times)

    ghi = _s("shortwave_radiation")
    dni = _s("direct_normal_irradiance")
    dhi = _s("diffuse_radiation")
    t2m = _s("temperature_2m")
    wind = _s("windspeed_10m")

    df = _make_frame(times, ghi, dni, dhi, t2m, wind)
    df = df.tz_convert(pytz.timezone(timezone))
    df = _resample(df, pas_de_temps, "mean")
    return df



