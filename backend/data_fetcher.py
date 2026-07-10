"""
data_fetcher.py — AQI Data Fetcher
Fetches real-time AQI readings from:
  1. WAQI / aqicn.org  (primary — CPCB India stations, GPS-based)
  2. OpenAQ            (secondary — global, GPS radius)
  3. OpenWeatherMap    (tertiary  — global, hourly history)

Returns normalized DataFrames ready for LSTM inference.
"""

import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
import numpy as np
import pandas as pd
from dotenv import load_dotenv

load_dotenv(override=True)
logger = logging.getLogger(__name__)

OPENAQ_BASE = "https://api.openaq.org/v3"
OWM_BASE    = "https://api.openweathermap.org/data/2.5"
WAQI_BASE   = "https://api.waqi.info"

OPENAQ_KEY  = os.getenv("X-API-Key", "").strip()
OWM_KEY     = os.getenv("OWM_API_KEY", "").strip()
WAQI_TOKEN  = os.getenv("WAQI_TOKEN", "").strip()


# ─── India NAQI Calculation ──────────────────────────────────────────────────

def _breakpoint_aqi(c: float, breakpoints: list) -> float:
    """Linear interpolation between AQI breakpoints."""
    for cl, ch, il, ih in breakpoints:
        if cl <= c <= ch:
            return ((ih - il) / (ch - cl)) * (c - cl) + il
    return 500.0


def calculate_india_aqi(pm25: float, pm10: float) -> float:
    """
    Calculate India National AQI (NAQI) from PM2.5 and PM10.
    Returns the dominant pollutant AQI (higher of the two).
    """
    pm25_bp = [
        (0, 30, 0, 50), (30, 60, 51, 100), (60, 90, 101, 200),
        (90, 120, 201, 300), (120, 250, 301, 400), (250, 500, 401, 500),
    ]
    pm10_bp = [
        (0, 50, 0, 50), (50, 100, 51, 100), (100, 250, 101, 200),
        (250, 350, 201, 300), (350, 430, 301, 400), (430, 600, 401, 500),
    ]
    return max(
        _breakpoint_aqi(max(0, pm25), pm25_bp),
        _breakpoint_aqi(max(0, pm10), pm10_bp),
    )


# ─── WAQI Fetcher (Primary — CPCB India) ─────────────────────────────────────

def fetch_waqi_snapshot(lat: float, lon: float) -> Optional[float]:
    """
    Fetch ONLY the live current AQI from the nearest WAQI station,
    regardless of distance. Used purely for the 'Current AQI' display
    on the dashboard — NOT for LSTM historical data.

    Returns the AQI float or None on failure.
    """
    if not WAQI_TOKEN:
        return None
    try:
        url = f"{WAQI_BASE}/feed/geo:{lat};{lon}/"
        with httpx.Client(timeout=10) as client:
            resp = client.get(url, params={"token": WAQI_TOKEN})
            resp.raise_for_status()
            data = resp.json()
        if data.get("status") != "ok":
            return None
        result = data["data"]
        aqi_val = float(result.get("aqi", np.nan))
        station_name = result.get("city", {}).get("name", "unknown")
        logger.info(f"WAQI snapshot: station '{station_name}' → live AQI={aqi_val}")
        return aqi_val if not np.isnan(aqi_val) else None
    except Exception as exc:
        logger.warning(f"WAQI snapshot failed: {exc}")
        return None


def fetch_waqi(lat: float, lon: float) -> Optional[pd.DataFrame]:
    """
    Fetch the nearest CPCB/WAQI station reading for the given GPS coordinates.

    WAQI returns current AQI + individual pollutant iaqi breakdown.
    We replicate 48 synthetic hourly rows from this snapshot so the LSTM
    window is satisfied — the current value is the most recent truth.

    Only accepts stations within 1.0 degree (~100km) to prevent WAQI from
    silently snapping to a distant city station (e.g. Delhi for Hyderabad).

    Returns a DataFrame with columns:
        timestamp, pm25, pm10, no2, o3, co, aqi, source
    or None if the fetch fails or station is too far.
    """
    if not WAQI_TOKEN:
        logger.warning("WAQI_TOKEN not set — skipping WAQI fetch")
        return None

    try:
        url = f"{WAQI_BASE}/feed/geo:{lat};{lon}/"
        with httpx.Client(timeout=15) as client:
            resp = client.get(url, params={"token": WAQI_TOKEN})
            resp.raise_for_status()
            data = resp.json()

        if data.get("status") != "ok":
            logger.warning(f"WAQI returned non-ok status: {data.get('status')} — {data.get('data', '')}")
            return None

        result = data["data"]

        # Verify the returned station is reasonably close to requested coordinates.
        # WAQI falls back to the nearest ACTIVE station in the country if local ones are offline.
        # Reject if the distance is greater than 1.0 degree (~100km) to trigger local fallback.
        station_geo = result.get("city", {}).get("geo", [])
        if len(station_geo) == 2:
            st_lat, st_lon = float(station_geo[0]), float(station_geo[1])
            deg_distance = ((st_lat - lat)**2 + (st_lon - lon)**2)**0.5
            if deg_distance > 1.0:
                logger.warning(
                    f"WAQI: nearest active station '{result.get('city', {}).get('name')}' is too far "
                    f"({deg_distance:.2f} degrees) — rejecting to trigger local fallback"
                )
                return None

        iaqi = result.get("iaqi", {})

        # Extract pollutants (WAQI uses 'v' key for the value)
        def _val(key):
            return float(iaqi[key]["v"]) if key in iaqi else np.nan

        aqi_val = float(result.get("aqi", np.nan))
        pm25    = _val("pm25")
        pm10    = _val("pm10")
        no2     = _val("no2")
        o3      = _val("o3")
        co      = _val("co")
        temp    = _val("t")    # temperature (°C)
        hum     = _val("h")    # humidity (%)
        wind    = _val("w")    # wind speed (m/s)

        # Recompute India NAQI from PM2.5 / PM10 if available
        if not np.isnan(pm25) and not np.isnan(pm10):
            india_aqi = calculate_india_aqi(pm25, pm10)
        elif not np.isnan(aqi_val):
            india_aqi = aqi_val   # WAQI already uses AQI scale
        else:
            logger.warning("WAQI: no usable AQI value")
            return None

        station_name = result.get("city", {}).get("name", "unknown")
        logger.info(f"WAQI: station '{station_name}' → AQI={india_aqi:.1f} (PM2.5={pm25}, PM10={pm10})")

        # Build 48-hour synthetic history (constant fill with latest reading).
        now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        timestamps = [now - timedelta(hours=i) for i in range(47, -1, -1)]

        rows = [{
            "timestamp":   ts,
            "pm25":        pm25,
            "pm10":        pm10,
            "no2":         no2,
            "o3":          o3,
            "co":          co,
            "temperature": temp,
            "humidity":    hum,
            "wind_speed":  wind,
            "aqi":         india_aqi,
            "source":      "waqi",
        } for ts in timestamps]

        df = pd.DataFrame(rows)
        return df.sort_values("timestamp").reset_index(drop=True)

    except Exception as exc:
        logger.error(f"WAQI fetch error: {exc}")
        return None


# ─── OpenAQ Fetcher ──────────────────────────────────────────────────────────

def fetch_openaq(lat: float, lon: float, radius_km: int = 25, hours: int = 48) -> Optional[pd.DataFrame]:
    """
    Fetch last `hours` hours of readings from the nearest OpenAQ v3 stations.

    Flow:
      1. GET /v3/locations  → find nearby stations
      2. GET /v3/locations/{id}/latest  → get most recent sensor readings
      3. GET /v3/sensors/{sensor_id}/measurements  → get historical time-series

    Returns a DataFrame with columns:
        timestamp, pm25, pm10, no2, o3, aqi, source
    or None if the fetch fails or no stations are found.
    """
    if not OPENAQ_KEY:
        logger.warning("X-API-Key not set — skipping OpenAQ fetch")
        return None

    headers  = {"X-API-Key": OPENAQ_KEY}
    radius_m = min(radius_km * 1000, 25000)

    try:
        with httpx.Client(timeout=15) as client:
            # Step 1: Find nearby locations
            loc_resp = client.get(
                f"{OPENAQ_BASE}/locations",
                params={
                    "coordinates": f"{lat},{lon}",
                    "radius":      radius_m,
                    "limit":       5,
                },
                headers=headers,
            )
            loc_resp.raise_for_status()
            locations = loc_resp.json().get("results", [])

        if not locations:
            logger.warning(f"No OpenAQ stations within {radius_km}km of ({lat:.4f}, {lon:.4f})")
            return None

        # Step 2: Get latest sensor readings for each location (quickest path)
        latest_rows = []
        sensor_ids_by_param: dict[str, list[int]] = {"pm25": [], "pm10": [], "no2": [], "o3": []}

        PARAM_MAP = {
            "pm25": "pm25", "pm2.5": "pm25",
            "pm10": "pm10",
            "no2":  "no2",
            "o3":   "o3",
        }

        with httpx.Client(timeout=15) as client:
            for loc in locations[:3]:
                loc_id = loc["id"]

                # Collect sensor IDs from the location payload
                for sensor in loc.get("sensors", []):
                    param_raw = sensor.get("parameter", {}).get("name", "").lower()
                    param_key = PARAM_MAP.get(param_raw)
                    if param_key:
                        sensor_ids_by_param[param_key].append(sensor["id"])

                # Get latest values for this location
                lat_resp = client.get(
                    f"{OPENAQ_BASE}/locations/{loc_id}/latest",
                    headers=headers,
                )
                if lat_resp.status_code in (404, 422):
                    logger.debug(f"OpenAQ: location {loc_id} latest returned {lat_resp.status_code} — skipping")
                    continue
                lat_resp.raise_for_status()

                for sensor_reading in lat_resp.json().get("results", []):
                    param_raw = sensor_reading.get("parameter", {}).get("name", "").lower()
                    param_key = PARAM_MAP.get(param_raw)
                    if param_key:
                        latest_rows.append({
                            "timestamp": datetime.now(timezone.utc),
                            "parameter": param_key,
                            "value":     float(sensor_reading.get("value", np.nan)),
                        })

        # Step 3: Fetch historical measurements for the top sensors of each parameter
        history_rows = []
        date_from = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        date_to   = datetime.now(timezone.utc).isoformat()

        with httpx.Client(timeout=20) as client:
            for param_key, s_ids in sensor_ids_by_param.items():
                for s_id in s_ids[:2]:  # Use at most 2 sensors per parameter
                    hist_resp = client.get(
                        f"{OPENAQ_BASE}/sensors/{s_id}/measurements",
                        params={
                            "date_from": date_from,
                            "date_to":   date_to,
                            "limit":     500,
                        },
                        headers=headers,
                    )
                    if hist_resp.status_code in (404, 422):
                        logger.debug(f"OpenAQ: sensor {s_id} returned {hist_resp.status_code} — skipping")
                        continue
                    hist_resp.raise_for_status()
                    for r in hist_resp.json().get("results", []):
                        try:
                            ts_str = r.get("period", {}).get("datetimeFrom", {}).get("utc") or r.get("datetime", {}).get("utc", "")
                            history_rows.append({
                                "timestamp": ts_str,
                                "parameter": param_key,
                                "value":     float(r.get("value", np.nan)),
                            })
                        except Exception:
                            continue

        # Combine latest + history
        all_rows = latest_rows + history_rows
        if not all_rows:
            logger.warning("OpenAQ returned no measurements")
            return None

        df = pd.DataFrame(all_rows)
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)

        df = df.pivot_table(
            index="timestamp", columns="parameter", values="value", aggfunc="mean"
        ).reset_index()

        for col in ["pm25", "pm10", "no2", "o3"]:
            if col not in df.columns:
                df[col] = np.nan

        df["aqi"] = df.apply(
            lambda r: calculate_india_aqi(r.get("pm25", 0) or 0, r.get("pm10", 0) or 0),
            axis=1,
        )
        df["source"] = "openaq"

        df = df.sort_values("timestamp").reset_index(drop=True)
        logger.info(f"OpenAQ: {len(df)} records for ({lat:.4f}, {lon:.4f})")
        return df

    except Exception as exc:
        logger.error(f"OpenAQ fetch error: {exc}")
        return None



# ─── OpenWeatherMap Fetcher ──────────────────────────────────────────────────

def fetch_owm(lat: float, lon: float, hours: int = 48) -> Optional[pd.DataFrame]:
    """
    Fetch air pollution history from OpenWeatherMap.
    Converts OWM pollutants to India NAQI via PM2.5/PM10 breakpoints.

    Returns a DataFrame with columns:
        timestamp, pm25, pm10, no2, o3, co, aqi, source
    or None if the fetch fails.
    """
    if not OWM_KEY:
        logger.warning("OWM_API_KEY not set — skipping OWM fetch")
        return None

    now_ts   = int(datetime.now(timezone.utc).timestamp())
    start_ts = now_ts - (hours * 3600)

    try:
        with httpx.Client(timeout=15) as client:
            resp = client.get(
                f"{OWM_BASE}/air_pollution/history",
                params={
                    "lat":   lat,
                    "lon":   lon,
                    "start": start_ts,
                    "end":   now_ts,
                    "appid": OWM_KEY,
                },
            )
            resp.raise_for_status()
            data = resp.json().get("list", [])

        if not data:
            return None

        records = []
        for item in data:
            comp = item.get("components", {})
            pm25 = comp.get("pm2_5", np.nan)
            pm10 = comp.get("pm10", np.nan)
            records.append({
                "timestamp":   datetime.fromtimestamp(item["dt"], tz=timezone.utc),
                "pm25":        pm25,
                "pm10":        pm10,
                "no2":         comp.get("no2", np.nan),
                "o3":          comp.get("o3", np.nan),
                "co":          comp.get("co", np.nan),
                "temperature": np.nan,
                "humidity":    np.nan,
                "wind_speed":  np.nan,
                "aqi":         calculate_india_aqi(pm25 or 0, pm10 or 0),
                "source":      "owm",
            })

        df = pd.DataFrame(records).sort_values("timestamp").reset_index(drop=True)
        logger.info(f"OWM: {len(df)} records for ({lat:.4f}, {lon:.4f})")
        return df

    except Exception as exc:
        logger.error(f"OWM fetch error: {exc}")
        return None


# ─── Primary Entry Point ──────────────────────────────────────────────────────

def get_readings_for_location(
    lat: float, lon: float, hours: int = 48
) -> tuple[Optional[pd.DataFrame], str, Optional[float]]:
    """
    Fetch AQI readings for given GPS coordinates using a tiered fallback chain:
      1. WAQI  — live CPCB India stations (GPS geo-endpoint)
      2. OpenAQ — global open data platform (radius-based)
      3. OWM   — OpenWeatherMap hourly history

    Additionally, always fetches a live snapshot AQI from WAQI (ignoring
    distance) to display the real-time 'Current AQI' on the dashboard.

    Returns:
        (DataFrame | None, source_name, live_current_aqi | None)
        source_name: 'waqi' | 'openaq' | 'owm' | 'none'
    """
    # ── Always get live current AQI snapshot for display (ignores distance) ──
    live_aqi = fetch_waqi_snapshot(lat, lon)

    # ── Tier 1: WAQI historical data (distance-restricted for LSTM accuracy) ─
    df = fetch_waqi(lat, lon)
    if df is not None and len(df) >= 12:
        # If WAQI passed the distance check, its AQI IS the live AQI
        live_aqi = float(df.iloc[-1]["aqi"])
        return df, "waqi", live_aqi

    logger.info("WAQI insufficient — trying OpenAQ")

    # ── Tier 2: OpenAQ ────────────────────────────────────────────────────────
    df = fetch_openaq(lat, lon, hours=hours)
    if df is not None and len(df) >= 12:
        return df, "openaq", live_aqi

    logger.info("OpenAQ insufficient — trying OpenWeatherMap")

    # ── Tier 3: OWM ──────────────────────────────────────────────────────────
    df = fetch_owm(lat, lon, hours=hours)
    if df is not None and len(df) >= 12:
        return df, "owm", live_aqi

    logger.warning(f"All data sources failed for ({lat:.4f}, {lon:.4f})")
    return None, "none", live_aqi
