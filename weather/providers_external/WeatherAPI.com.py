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

# 3) WeatherAPI.com (requires api_key)
# Docs overview mention solar irradiance availability; fields vary by plan.
# https://www.weatherapi.com/ (Docs)
# -----------------------------
def weatherapi_com(latitude: float, longitude: float, altitude: float, timezone: str,
                   horizon: int, pas_de_temps: int,
                   azimuth: Optional[float] = None, tilt: Optional[float] = None,
                   **kwargs) -> pd.DataFrame:
    """
    Requires api_key in kwargs. We pull hourly forecast and map available fields.
    Some plans expose 'solarradiation' (W/m^2) per hour; when present we map to GHI.
    DNI/DHI are not exposed → returned as NaN.
    """
    api_key = kwargs.get("api_key", None)
    if not api_key:
        raise ValueError("weatherapi_com requires api_key=<YOUR_KEY> in kwargs.")

    # WeatherAPI forecast with hourly steps; horizon capped by plan (e.g., 14 days)
    # We call /forecast.json with 'q=lat,lon' and 'dt' windows by day; here we fetch next 3 days then trim.
    base = "https://api.weatherapi.com/v1/forecast.json"
    days = max(1, min(14, int(math.ceil(horizon / 24.0))))  # plan-dependent
    params = {
        "key": api_key,
        "q": f"{latitude},{longitude}",
        "days": days,
        "aqi": "no",
        "alerts": "no",
        "hour": "yes"
    }
    r = requests.get(base, params=params, timeout=30)
    r.raise_for_status()
    js = r.json()

    rows = []
    for d in js.get("forecast", {}).get("forecastday", []):
        for h in d.get("hour", []):
            t = pd.to_datetime(h["time"]).tz_localize(None).tz_localize("UTC")
            rows.append({
                "Datetime": t,
                # If 'solarradiation' exists, treat it as GHI (unit can be W/m^2 or Wh/m^2 depending on plan; adjust as needed)
                "GHI": h.get("solarradiance") or h.get("solarradiation"),
                "Temperature": h.get("temp_c"),
                "Wind": h.get("wind_mph") * 0.44704 if h.get("wind_mph") is not None else None
            })
    df = pd.DataFrame(rows).set_index("Datetime").sort_index()
    # Ensure columns
    for col in ["GHI", "DNI", "DHI", "Temperature", "Wind"]:
        if col not in df.columns:
            df[col] = np.nan
    df.index = df.index.tz_convert(pytz.timezone(timezone))
    df = _resample(df[["GHI", "DNI", "DHI", "Temperature", "Wind"]], pas_de_temps, "mean")
    return df

