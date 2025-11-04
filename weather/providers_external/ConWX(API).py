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
    # 原: dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc)
    return dt.datetime.now(dt.timezone.utc)

def _date_index(timezone: str, horizon_h: int, step_min: int) -> pd.DatetimeIndex:
    tz = pytz.timezone(timezone)
    start_utc = _now_utc()
    end_utc = start_utc + dt.timedelta(hours=horizon_h)
    # 原: freq=f"{int(step_min)}T"
    idx_utc = pd.date_range(
        start=start_utc, end=end_utc,
        freq=f"{int(step_min)}min",
        inclusive="left", tz=dt.timezone.utc
    )
    return idx_utc.tz_convert(tz)


def _panel_orientation_factor(local_time: pd.DatetimeIndex,
                              azimuth: float, tilt: float, longitude: float) -> np.ndarray:
    # 转成 numpy，避免 pandas Index 的不可变问题
    hours = local_time.hour.to_numpy() + local_time.minute.to_numpy() / 60.0

    # 以中午为峰值的简化日变化
    x = (hours - 12.0) / 6.0
    diurnal = np.clip(1.0 - x**2, 0.0, 1.0)

    # 方位角惩罚（南向180°最佳）
    az_err = abs(((azimuth - 180.0 + 180.0) % 360.0) - 180.0)
    az_factor = max(0.2, 1.0 - az_err / 180.0)

    # 倾角惩罚（~32°最佳）
    tilt_opt = 32.0
    tilt_factor = max(0.3, 1.0 - abs(tilt - tilt_opt)/90.0)

    # 清晨/傍晚平滑衰减 + 经度轻微相位
    phase = (longitude % 15.0) / 15.0 * math.pi/8.0
    smooth_core = 0.5 * (1.0 + np.cos(np.clip((np.abs(x) - 1.0 + phase), 0, 1) * math.pi))
    # 用 np.where 避免对“索引”原地赋值
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
    # Midday slight bump (module cooling by wind): apply a gentle bell
    hours = index.hour + index.minute/60.0
    midday = np.exp(-((hours - 12.0) ** 2) / (2 * 2.5 ** 2))
    return np.clip(base + noise + wind_cooling * midday, 0.0, 1.0)

def _simulate_pv_power(index_local: pd.DatetimeIndex,
                       latitude: float,
                       longitude: float,
                       azimuth: float,
                       tilt: float,
                       capacity_kwp: float,
                       losses: float = 0.12) -> pd.Series:
    shape = _panel_orientation_factor(index_local, azimuth, tilt, longitude)   # np.ndarray
    weather = _weather_factor(index_local)                                      # np.ndarray
    p_dc = capacity_kwp * 1000.0 * shape * weather                              # np.ndarray
    p_ac = p_dc * (1.0 - losses)                                                # np.ndarray

    # ✅ 关键点：把 hours 转为 numpy，避免 pandas Index 参与后续布尔索引
    hours = index_local.hour.to_numpy() + index_local.minute.to_numpy() / 60.0
    night_mask = (hours < 5.5) | (hours > 21.5)

    # ✅ 用 np.where 而不是原地赋值，避免潜在的“可变性”冲突
    p_ac = np.where(night_mask, 0.0, p_ac)

    return pd.Series(p_ac, index=index_local, name="Production_PV_W")

def _ensure_output(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.index.name = "Datetime"
    # One and only required column:
    if "Production_PV_W" not in df.columns:
        raise ValueError("Output must have 'Production_PV_W' column.")
    # Sort & drop duplicates for safety
    df = df[~df.index.duplicated()].sort_index()
    return df



# 4) ConWX
# =====================================================================
def conwx(position_latitude: float, position_longitude: float, position_altitude: float,
          position_timezone: str, horizon: int, pas_de_temps: int,
          azimuth: float, tilt: float,
          **kwargs) -> pd.DataFrame:
    """
    ConWX provides portfolio or site-level power forecasts. Delivery can be API/FTP/SFTP.
    Inputs (when real): credentials, site code, capacity, tilt/azimuth; often calibrated with actuals.
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

    # --- Real integration sketch (commented) ---
    # token = kwargs["api_token"]
    # site = kwargs["site_id"]
    # base = f"https://api.conwx.com/v1/solar/{site}/forecast"
    # params = {"interval": f"{pas_de_temps}m", "hours": horizon}
    # headers = {"Authorization": f"Bearer {token}"}
    # r = requests.get(base, params=params, headers=headers, timeout=30)
    # r.raise_for_status()
    # js = r.json()
    # rows = []
    # for it in js.get("timeseries", []):
    #     t = pd.to_datetime(it["time"]).tz_convert(position_timezone)
    #     p_w = float(it["power_w"])
    #     rows.append((t, p_w))
    # df = pd.DataFrame(rows, columns=["Datetime", "Production_PV_W"]).set_index("Datetime").sort_index()
    # df = df.reindex(idx, method="nearest")
    # return _ensure_output(df)

    resp = kwargs.get("response_json")
    if resp:
        rows = []
        for it in resp.get("timeseries", []):
            t = pd.to_datetime(it["time"]).tz_convert(position_timezone)
            p_w = float(it.get("power_w", 0.0))
            rows.append((t, p_w))
        df = pd.DataFrame(rows, columns=["Datetime", "Production_PV_W"]).set_index("Datetime").sort_index()
        df = df.reindex(idx, method="nearest")
        return _ensure_output(df)

    return _ensure_output(
        _simulate_pv_power(idx, position_latitude, position_longitude, azimuth, tilt,
                           capacity_kwp, losses).to_frame()
    )

def main():
        # 调用 solcast，返回一个 DataFrame
        df = conwx(
            position_latitude=50.63,
            position_longitude=3.06,
            position_altitude=20,
            position_timezone="Europe/Paris",
            horizon=48,  # 预测 48 小时
            pas_de_temps=60,  # 时间步长 60 分钟
            azimuth=180,  # 朝南
            tilt=30,  # 倾角 30°
            capacity_kwp=6.0,  # 模拟 6 kWp 的光伏系统
            simulate=True  # ⚠️ 默认 True = 模拟，不会去请求真实 API
        )

        # 查看前几行数据
        print(df.head())

        # 导出到 CSV
        output_file = "solcast_forecast.csv"
        df.to_csv(output_file)
        print(f"结果已导出到 {output_file}")


if __name__ == "__main__":
    main()