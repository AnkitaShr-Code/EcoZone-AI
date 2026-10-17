"""Sun table (pvlib) and prevailing wind (Open-Meteo), PLANNING.md "Terms and what changes them"."""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any, cast

import httpx
import numpy as np
import pandas as pd
import pvlib

from ..config import AreaConfig, Paths
from ..store import read_json, write_json

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"


def centroid_lonlat(cfg: AreaConfig) -> tuple[float, float]:
    w, s, e, n = cfg.bbox_wgs84
    return ((w + e) / 2, (s + n) / 2)


def sun_table(cfg: AreaConfig) -> list[dict[str, Any]]:
    """Clear-sky sun altitude and azimuth (clockwise from north) at each reference time."""
    ref = cfg["reference"]
    lon, lat = centroid_lonlat(cfg)
    stamps = pd.DatetimeIndex([pd.Timestamp(f"{ref['date']} {t}", tz=ref["timezone"]) for t in ref["times_ist"]])
    pos = pvlib.solarposition.get_solarposition(stamps, latitude=lat, longitude=lon)
    return [
        {
            "time": str(t),
            "altitude_deg": round(float(alt), 4),
            "azimuth_deg": round(float(az), 4),
        }
        for t, alt, az in zip(ref["times_ist"], pos["elevation"], pos["azimuth"], strict=True)
    ]


def prevailing_wind_from_deg(directions_deg: np.ndarray, speeds: np.ndarray) -> float:
    """Speed-weighted vector mean of the direction the wind blows from, in degrees clockwise from north."""
    rad = np.radians(directions_deg)
    x = float(np.sum(speeds * np.sin(rad)))
    y = float(np.sum(speeds * np.cos(rad)))
    return float(math.degrees(math.atan2(x, y)) % 360)


def fetch_wind(cfg: AreaConfig, paths: Paths, *, refresh: bool = False) -> dict[str, Any]:
    raw_path = paths.raw / "open_meteo_wind.json"
    if raw_path.exists() and not refresh:
        return read_json(raw_path)
    wind = cfg["wind"]
    lon, lat = centroid_lonlat(cfg)
    params: dict[str, str | float] = {
        "latitude": round(lat, 4),
        "longitude": round(lon, 4),
        "start_date": str(wind["start_date"]),
        "end_date": str(wind["end_date"]),
        "hourly": "wind_speed_10m,wind_direction_10m",
        "timezone": cfg["reference"]["timezone"],
    }
    resp = httpx.get(ARCHIVE_URL, params=params, timeout=60)
    resp.raise_for_status()
    data = cast(dict[str, Any], resp.json())
    data["_fetched_at"] = datetime.now(UTC).isoformat(timespec="seconds")
    write_json(data, raw_path)
    return data


def wind_from_deg(cfg: AreaConfig, paths: Paths, *, refresh: bool = False) -> tuple[float, dict[str, Any]]:
    """Return (direction wind blows from, provenance). A config override skips the download."""
    wind = cfg["wind"]
    if wind.get("from_deg") is not None:
        return float(wind["from_deg"]), {"source": "config override", "from_deg": float(wind["from_deg"])}
    data = fetch_wind(cfg, paths, refresh=refresh)
    hourly = data["hourly"]
    times = pd.to_datetime(hourly["time"])
    speed = np.array(hourly["wind_speed_10m"], dtype=float)
    direction = np.array(hourly["wind_direction_10m"], dtype=float)
    keep = np.isin(times.hour, wind["hours_local"]) & np.isfinite(speed) & np.isfinite(direction)
    deg = prevailing_wind_from_deg(direction[keep], speed[keep])
    return deg, {
        "source": "Open-Meteo historical weather API (ERA5)",
        "url": ARCHIVE_URL,
        "licence": "CC BY 4.0",
        "fetched_at": data.get("_fetched_at"),
        "start_date": str(wind["start_date"]),
        "end_date": str(wind["end_date"]),
        "hours_local": list(wind["hours_local"]),
        "samples": int(keep.sum()),
    }


def run(cfg: AreaConfig, paths: Paths, *, refresh: bool = False) -> dict[str, Any]:
    deg, provenance = wind_from_deg(cfg, paths, refresh=refresh)
    result = {
        "sun": sun_table(cfg),
        "wind_from_deg": round(deg, 1),
        "wind_provenance": provenance,
    }
    write_json(result, paths.json("sun_wind"))
    return result
