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


# 5) NWS (USA National Weather Service; free, no key)
# Docs: https://api.weather.gov (no irradiance provided)
# We return Temperature/Wind and set GHI/DNI/DHI = NaN.
# -----------------------------
def nws_api(latitude: float, longitude: float, altitude: float, timezone: str,
            horizon: int, pas_de_temps: int,
            azimuth: Optional[float] = None, tilt: Optional[float] = None,
            **kwargs) -> pd.DataFrame:
    """
    NWS gridpoint forecast → Temperature/Wind. Irradiance not available (NaN).
    Only valid for locations covered by NWS (US & territories).
    """
    # 1) Resolve gridpoint
    points = requests.get(
        "https://api.weather.gov/points/{:.4f},{:.4f}".format(latitude, longitude),
        timeout=30,
        headers={"User-Agent": "pv-router/1.0"}
    )
    points.raise_for_status()
    pjs = points.json()
    grid_url = pjs["properties"]["forecastHourly"]

    # 2) Hourly forecast
    r = requests.get(grid_url, timeout=30, headers={"User-Agent": "pv-router/1.0"})
    r.raise_for_status()
    js = r.json()

    rows = []
    for p in js.get("properties", {}).get("periods", []):
        t = pd.to_datetime(p["startTime"], utc=True)
        temp_c = None
        if p.get("temperature") is not None:
            if p.get("temperatureUnit") == "F":
                temp_c = (p["temperature"] - 32) * 5.0 / 9.0
            else:
                temp_c = float(p["temperature"])
        wind_ms = None
        if p.get("windSpeed"):
            # windSpeed like "10 mph" or "5 to 10 mph"
            try:
                spd = p["windSpeed"].split(" ")[0]
                wind_ms = float(spd) * 0.44704
            except Exception:
                wind_ms = None

        rows.append({
            "Datetime": t,
            "Temperature": temp_c,
            "Wind": wind_ms
        })
    df = pd.DataFrame(rows).set_index("Datetime").sort_index()

    # Add irradiance placeholders
    for col in ["GHI", "DNI", "DHI"]:
        df[col] = np.nan

    # Reorder, TZ, resample
    df = df[["GHI", "DNI", "DHI", "Temperature", "Wind"]]
    df.index = df.index.tz_convert(pytz.timezone(timezone))
    df = _resample(df, pas_de_temps, "mean")
    return df


def main():
    # 1. 调用函数（你给的示例完全OK）
    df = nws_api(
        latitude=50.63, longitude=3.06, altitude=20,
        timezone="Europe/Paris",
        horizon=72,           # 未来72小时
        pas_de_temps=60       # 步长60分钟
    )

    # 2. 看一眼数据
    print("DataFrame shape:", df.shape)
    print(df.head(10))       # 打印前10行

    # 3. 导出到CSV（最常用）
    out_csv = "open_meteo_forecast.csv"
    df.to_csv(out_csv)
    print(f"CSV 已导出：{out_csv}")

    # 4. 如果你喜欢 parquet（更快更省空间，分析方便）
    # pip install pyarrow
    # df.to_parquet("open_meteo_forecast.parquet")

    # 5. 若你有后续计算/可视化，直接对 df 做处理即可
    # 例如：只看白天的样本
    # df_day = df.between_time("06:00", "20:00")

if __name__ == "__main__":
    main()