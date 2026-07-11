#!/usr/bin/env python3
"""
accurate_aqi.py - Multi-Source AQI Accuracy System
Queries WAQI, OpenAQ, and OpenWeatherMap independently,
then picks the best reading using distance + freshness scoring.
"""

import os
import logging
import httpx
import numpy as np
from typing import Dict, Optional, Tuple
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

WAQI_TOKEN  = os.getenv("WAQI_TOKEN", "").strip()
OPENAQ_KEY  = os.getenv("X-API-Key", "").strip()
OWM_KEY     = os.getenv("OWM_API_KEY", "").strip()

WAQI_BASE   = "https://api.waqi.info"
OPENAQ_BASE = "https://api.openaq.org/v3"
OWM_BASE    = "https://api.openweathermap.org/data/2.5"


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Accurate distance in km between two GPS points."""
    R = 6371.0
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = np.sin(dlat / 2)**2 + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon / 2)**2
    return R * 2 * np.arcsin(np.sqrt(a))


def _pm25_to_us_aqi(pm25: float) -> float:
    """Convert PM2.5 µg/m³ → US AQI (EPA breakpoints)."""
    bp = [
        (0.0,  12.0,  0,   50),
        (12.1, 35.4,  51,  100),
        (35.5, 55.4,  101, 150),
        (55.5, 150.4, 151, 200),
        (150.5,250.4, 201, 300),
        (250.5,500.4, 301, 500),
    ]
    for cl, ch, il, ih in bp:
        if cl <= pm25 <= ch:
            return round(((ih - il) / (ch - cl)) * (pm25 - cl) + il)
    return 500


def _india_naqi(pm25: float, pm10: float = 0) -> float:
    """Convert PM2.5/PM10 → India NAQI (CPCB breakpoints)."""
    def _bp(c, bps):
        for cl, ch, il, ih in bps:
            if cl <= c <= ch:
                return ((ih - il) / (ch - cl)) * (c - cl) + il
        return 500.0

    pm25_bp = [(0,30,0,50),(30,60,51,100),(60,90,101,200),
               (90,120,201,300),(120,250,301,400),(250,500,401,500)]
    pm10_bp = [(0,50,0,50),(50,100,51,100),(100,250,101,200),
               (250,350,201,300),(350,430,301,400),(430,600,401,500)]
    return max(_bp(max(0, pm25), pm25_bp), _bp(max(0, pm10), pm10_bp))


# ─── Source 1: WAQI ──────────────────────────────────────────────────────────

def _fetch_waqi(lat: float, lon: float) -> Optional[Dict]:
    """
    Query WAQI geo-feed. Also tries named Hyderabad stations if
    the nearest auto-detected one is >80 km away.
    """
    if not WAQI_TOKEN:
        logger.warning("WAQI_TOKEN not set — skipping WAQI")
        return None

    def _query_waqi(url: str, params: dict) -> Optional[Dict]:
        try:
            with httpx.Client(timeout=10) as c:
                r = c.get(url, params=params)
            if r.status_code != 200:
                return None
            d = r.json()
            if d.get("status") != "ok":
                return None
            return d["data"]
        except Exception as e:
            logger.warning(f"WAQI query failed: {e}")
            return None

    # Primary: geo feed
    result = _query_waqi(f"{WAQI_BASE}/feed/geo:{lat};{lon}/", {"token": WAQI_TOKEN})

    best = None
    candidates = []

    if result:
        aqi_val = result.get("aqi")
        geo = result.get("city", {}).get("geo", [])
        if aqi_val and aqi_val != "-" and len(geo) == 2:
            dist = _haversine_km(lat, lon, float(geo[0]), float(geo[1]))
            candidates.append({
                "aqi": float(aqi_val),
                "station": result.get("city", {}).get("name", "WAQI"),
                "distance_km": round(dist, 1),
                "pm25": result.get("iaqi", {}).get("pm25", {}).get("v"),
                "pm10": result.get("iaqi", {}).get("pm10", {}).get("v"),
                "source": "waqi_geo",
            })

    # Supplement: search for city-name stations (Hyderabad-specific)
    for keyword in ["hyderabad", "ghatkesar", "secunderabad", "medchal"]:
        try:
            with httpx.Client(timeout=8) as c:
                r = c.get(f"{WAQI_BASE}/search/", params={"token": WAQI_TOKEN, "keyword": keyword})
            if r.status_code == 200 and r.json().get("status") == "ok":
                for st in r.json().get("data", [])[:4]:
                    uid = st.get("uid")
                    geo = st.get("station", {}).get("geo", [])
                    if not uid or len(geo) < 2:
                        continue
                    dist = _haversine_km(lat, lon, float(geo[0]), float(geo[1]))
                    if dist > 100:          # skip far stations
                        continue
                    sd = _query_waqi(f"{WAQI_BASE}/feed/@{uid}/", {"token": WAQI_TOKEN})
                    if sd:
                        av = sd.get("aqi")
                        if av and av != "-":
                            candidates.append({
                                "aqi": float(av),
                                "station": sd.get("city", {}).get("name", keyword),
                                "distance_km": round(dist, 1),
                                "pm25": sd.get("iaqi", {}).get("pm25", {}).get("v"),
                                "pm10": sd.get("iaqi", {}).get("pm10", {}).get("v"),
                                "source": f"waqi_{keyword}",
                            })
        except Exception as e:
            logger.debug(f"WAQI search '{keyword}' failed: {e}")

    if not candidates:
        return None

    # Pick closest station
    best = min(candidates, key=lambda x: x["distance_km"])
    logger.info(f"WAQI best: {best['station']} @ {best['distance_km']}km → AQI {best['aqi']}")
    return best


# ─── Source 2: OpenAQ ────────────────────────────────────────────────────────

def _fetch_openaq(lat: float, lon: float) -> Optional[Dict]:
    """Query OpenAQ v3 for latest PM2.5 within 50 km."""
    if not OPENAQ_KEY:
        logger.warning("X-API-Key not set — skipping OpenAQ")
        return None

    headers = {"X-API-Key": OPENAQ_KEY}
    try:
        with httpx.Client(timeout=15) as c:
            r = c.get(
                f"{OPENAQ_BASE}/locations",
                params={"coordinates": f"{lat},{lon}", "radius": 50000, "limit": 10},
                headers=headers,
            )
        if r.status_code != 200:
            logger.warning(f"OpenAQ locations HTTP {r.status_code}")
            return None

        locs = r.json().get("results", [])
        if not locs:
            logger.warning("OpenAQ: no locations found within 50km")
            return None

        best_pm25 = None
        best_dist = float("inf")
        best_station = "OpenAQ"
        best_age_h = 999

        with httpx.Client(timeout=15) as c:
            for loc in locs[:5]:
                loc_id = loc["id"]
                loc_lat = loc.get("coordinates", {}).get("latitude", lat)
                loc_lon = loc.get("coordinates", {}).get("longitude", lon)
                dist = _haversine_km(lat, lon, loc_lat, loc_lon)

                # Get latest sensor readings
                lr = c.get(f"{OPENAQ_BASE}/locations/{loc_id}/latest", headers=headers)
                if lr.status_code not in (200,):
                    continue

                for reading in lr.json().get("results", []):
                    param = reading.get("parameter", {}).get("name", "").lower()
                    if param not in ("pm25", "pm2.5"):
                        continue
                    val = reading.get("value")
                    if val is None or val < 0:
                        continue

                    # Calculate data freshness
                    try:
                        dt_str = reading.get("datetime", {}).get("utc", "")
                        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                        age_h = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
                    except Exception:
                        age_h = 24

                    # Prefer fresh + close data
                    score = dist + age_h * 2   # weight age twice as much
                    best_score = best_dist + best_age_h * 2

                    if score < best_score:
                        best_pm25 = float(val)
                        best_dist = dist
                        best_station = loc.get("name", "OpenAQ")
                        best_age_h = age_h

        if best_pm25 is None:
            logger.warning("OpenAQ: no valid PM2.5 readings found")
            return None

        aqi = _pm25_to_us_aqi(best_pm25)
        logger.info(f"OpenAQ best: {best_station} @ {best_dist:.1f}km → PM2.5={best_pm25} → AQI~{aqi}")
        return {
            "aqi": aqi,
            "station": best_station,
            "distance_km": round(best_dist, 1),
            "pm25": best_pm25,
            "data_age_hours": round(best_age_h, 1),
            "source": "openaq",
        }

    except Exception as e:
        logger.error(f"OpenAQ fetch error: {e}")
        return None


# ─── Source 3: OpenWeatherMap ─────────────────────────────────────────────────

def _fetch_owm(lat: float, lon: float) -> Optional[Dict]:
    """Query OWM air_pollution endpoint for current PM2.5."""
    if not OWM_KEY:
        logger.warning("OWM_API_KEY not set — skipping OWM")
        return None

    try:
        with httpx.Client(timeout=10) as c:
            r = c.get(
                f"{OWM_BASE}/air_pollution",
                params={"lat": lat, "lon": lon, "appid": OWM_KEY},
            )
        if r.status_code != 200:
            logger.warning(f"OWM HTTP {r.status_code}")
            return None

        items = r.json().get("list", [])
        if not items:
            return None

        comp   = items[0].get("components", {})
        pm25   = comp.get("pm2_5", 0) or 0
        pm10   = comp.get("pm10",  0) or 0
        ts_raw = items[0].get("dt", 0)

        age_h = (datetime.now(timezone.utc).timestamp() - ts_raw) / 3600

        # Convert to India NAQI (OWM coords match exactly — distance=0)
        aqi = _india_naqi(pm25, pm10)
        logger.info(f"OWM: PM2.5={pm25:.1f} PM10={pm10:.1f} → India AQI={aqi:.0f} (age {age_h:.1f}h)")
        return {
            "aqi": round(aqi),
            "station": "OpenWeatherMap (exact coords)",
            "distance_km": 0,
            "pm25": pm25,
            "pm10": pm10,
            "data_age_hours": round(age_h, 1),
            "source": "owm",
        }

    except Exception as e:
        logger.error(f"OWM fetch error: {e}")
        return None


# ─── Aggregator ───────────────────────────────────────────────────────────────

def _reliability_score(entry: Dict) -> float:
    """
    Higher score = more reliable.
    Penalises distance and data age.
    """
    dist = entry.get("distance_km", 50)
    if not isinstance(dist, (int, float)):
        dist = 50
    age  = entry.get("data_age_hours", 1)
    # Score = 1 / (1 + dist_penalty + age_penalty)
    return 1.0 / (1.0 + dist / 10.0 + age / 2.0)


def get_accurate_current_aqi(lat: float, lon: float) -> Tuple[float, Dict]:
    """
    Fetch from all 3 sources, score each, then either:
    - Return a weighted average when readings agree (variance < 25 AQI)
    - Return the highest-scoring individual reading otherwise.

    Returns (aqi_value, report_dict)
    """
    logger.info(f"🎯 Multi-source AQI fetch for ({lat:.4f}, {lon:.4f})")

    waqi_data   = _fetch_waqi(lat, lon)
    openaq_data = _fetch_openaq(lat, lon)
    owm_data    = _fetch_owm(lat, lon)

    # Collect all available readings
    readings = []
    for d in [waqi_data, openaq_data, owm_data]:
        if d and d.get("aqi") and float(d["aqi"]) > 0:
            d["score"] = _reliability_score(d)
            readings.append(d)

    report = {
        "sources": {
            "waqi":   waqi_data,
            "openaq": openaq_data,
            "owm":    owm_data,
        },
        "readings_available": len(readings),
        "coordinates": {"lat": lat, "lon": lon},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if not readings:
        logger.warning("All 3 AQI sources failed — returning default 100")
        report["selected_source"] = "fallback"
        report["final_aqi"] = 100
        return 100.0, report

    # Sort by score
    readings.sort(key=lambda x: x["score"], reverse=True)
    best = readings[0]

    if len(readings) == 1:
        final_aqi = best["aqi"]
        report["selected_source"] = best["source"]
        report["method"] = "single_source"
        logger.info(f"✅ Single source: {best['source']} → AQI {final_aqi}")

    else:
        aqis     = [r["aqi"] for r in readings]
        variance = max(aqis) - min(aqis)
        report["variance"] = round(variance, 1)
        report["all_readings"] = [(r["source"], r["aqi"], round(r["score"], 3)) for r in readings]

        if variance <= 25:
            # Readings agree — take weighted average
            total_w = sum(r["score"] for r in readings)
            final_aqi = sum(r["aqi"] * r["score"] for r in readings) / total_w
            report["selected_source"] = "weighted_average"
            report["method"] = f"weighted_avg (variance={variance:.0f})"
            logger.info(f"✅ Weighted avg of {[r['source'] for r in readings]}: AQI {final_aqi:.1f}")
        else:
            # High variance — trust the closest/freshest (best score)
            final_aqi = best["aqi"]
            report["selected_source"] = best["source"]
            report["method"] = f"best_score (high variance={variance:.0f})"
            logger.info(f"⚠️  High variance {variance:.0f} — using best-scored: {best['source']} → AQI {final_aqi}")

    final_aqi = round(final_aqi, 1)
    report["final_aqi"] = final_aqi
    report["accuracy_info"] = {
        "reliable_sources": len(readings),
        "total_sources": 3,
        "method": report.get("method", ""),
    }

    return final_aqi, report
