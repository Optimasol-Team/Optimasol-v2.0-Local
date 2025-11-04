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


# 2) OpenWeather / OpenWeatherMap (commercial Solar Irradiance API)
# Docs: Solar Irradiance API (GHI/DNI/DHI; clear-sky & cloudy), Solar Panel Energy Prediction
# https://docs.openweather.co.uk/api/solar-radiation | https://openweather.org/api
# -----------------------------
def openweather_solar(latitude: float, longitude: float, altitude: float, timezone: str,
                      horizon: int, pas_de_temps: int,
                      azimuth: Optional[float] = None, tilt: Optional[float] = None,
                      **kwargs) -> pd.DataFrame:
    """
    Requires api_key in kwargs: OpenWeather Solar Irradiance API (paid add-on).
    Returns hourly GHI/DNI/DHI where available; temperature/wind can be pulled
    from One Call if you also pass onecall=True.
    """
    api_key = kwargs.get("api_key", None)
    if not api_key:
        raise ValueError("openweather_solar requires api_key=<YOUR_KEY> in kwargs.")

    # Solar Irradiance endpoint (daily payload with hourly detail; product-specific URL)
    # OpenWeather provides multiple endpoints; we use a typical pattern:
    # Example (subject to product plan): https://api.openweathermap.org/solar/1.0/solar_radiation
    # Check your exact endpoint/parameters in your account plan.
    base = "https://api.openweathermap.org/solar/1.0/solar_radiation"

    # OpenWeather expects date ranges per-day; to keep it simple we request 'horizon' hours as one span.
    start_iso, end_iso = _time_range(timezone, horizon, pas_de_temps)
    params = {
        "lat": latitude,
        "lon": longitude,
        "date_from": start_iso,   # product may also accept 'start'/'end' or 'date'—verify in your plan docs
        "date_to": end_iso,
        "appid": api_key
    }
    r = requests.get(base, params=params, timeout=30)
    r.raise_for_status()
    js = r.json()

    # Expected structure: list of time steps with ghi, dni, dhi (W/m^2); adapt if your plan differs
    # Build from generic possibilities:
    records = []
    def _coerce_step(step: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        # Common field names in the product (check plan): "ghi", "dni", "dhi", "time"
        t = step.get("time") or step.get("dt") or step.get("date")
        if not t:
            return None
        when = pd.to_datetime(t, utc=True)
        return {
            "Datetime": when,
            "GHI": step.get("ghi"),
            "DNI": step.get("dni"),
            "DHI": step.get("dhi")
        }

    if isinstance(js, dict) and "data" in js:
        for step in js["data"]:
            row = _coerce_step(step)
            if row:
                records.append(row)
    elif isinstance(js, list):
        for step in js:
            row = _coerce_step(step)
            if row:
                records.append(row)

    df = pd.DataFrame.from_records(records).set_index("Datetime").sort_index()
    # Optionally fetch temp/wind from One Call if asked
    if kwargs.get("onecall", False):
        onecall_url = "https://api.openweathermap.org/data/3.0/onecall"
        one_params = {
            "lat": latitude, "lon": longitude,
            "exclude": "minutely,daily,alerts",
            "appid": api_key, "units": "metric"
        }
        rr = requests.get(onecall_url, params=one_params, timeout=30)
        rr.raise_for_status()
        j2 = rr.json()
        # Hourly temps & wind
        tser = []
        wser = []
        for h in j2.get("hourly", []):
            tser.append((pd.to_datetime(h["dt"], unit="s", utc=True), h.get("temp")))
            wser.append((pd.to_datetime(h["dt"], unit="s", utc=True), h.get("wind_speed")))
        t2m = pd.Series({k: v for k, v in tser})
        wind = pd.Series({k: v for k, v in wser})
        df = df.join(t2m.rename("Temperature")).join(wind.rename("Wind"))

    # TZ + resample + ensure required columns exist
    df.index = pd.DatetimeIndex(df.index).tz_convert(pytz.timezone(timezone))
    for col in ["GHI", "DNI", "DHI", "Temperature", "Wind"]:
        if col not in df.columns:
            df[col] = np.nan
    df = _resample(df[["GHI", "DNI", "DHI", "Temperature", "Wind"]], pas_de_temps, "mean")
    return df

def main():
df = openweather_solar(50.63, 3.06, 20, "Europe/Paris", 48, 60, api_key="YOUR_KEY", onecall=True)


out_csv = "open_meteo_forecast.csv"
    df.to_csv(out_csv)
    print(f"CSV 已导出：{out_csv}")
if __name__ == "__main__":
    main()