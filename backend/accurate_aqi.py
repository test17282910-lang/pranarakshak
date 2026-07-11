#!/usr/bin/env python3
"""
accurate_aqi.py - Improved AQI Data Accuracy System
Fetches from multiple sources and cross-validates for better accuracy.
"""

import os
import logging
import httpx
import numpy as np
from typing import Dict, Tuple, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

WAQI_TOKEN = os.getenv("WAQI_TOKEN", "")
WAQI_BASE = "https://api.waqi.info"

def fetch_multiple_aqi_sources(lat: float, lon: float) -> Dict:
    """
    Fetch AQI from multiple sources for cross-validation and accuracy.
    Returns all available readings with reliability scores.
    """
    sources = {}
    
    # Source 1: WAQI (World Air Quality Index) - Primary source
    try:
        if WAQI_TOKEN:
            url = f"{WAQI_BASE}/feed/geo:{lat};{lon}/"
            with httpx.Client(timeout=10) as client:
                resp = client.get(url, params={"token": WAQI_TOKEN})
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("status") == "ok":
                        result = data["data"]
                        station_geo = result.get("city", {}).get("geo", [])
                        
                        # Calculate distance to determine reliability
                        distance_km = 0
                        if len(station_geo) == 2:
                            st_lat, st_lon = float(station_geo[0]), float(station_geo[1])
                            # Haversine distance approximation
                            distance_km = ((st_lat - lat)**2 + (st_lon - lon)**2)**0.5 * 111
                        
                        # Extract pollutant data
                        iaqi = result.get("iaqi", {})
                        pm25_val = iaqi.get("pm25", {}).get("v") if "pm25" in iaqi else None
                        pm10_val = iaqi.get("pm10", {}).get("v") if "pm10" in iaqi else None
                        
                        sources["waqi"] = {
                            "aqi": result.get("aqi"),
                            "station_name": result.get("city", {}).get("name", "Unknown"),
                            "distance_km": round(distance_km, 1),
                            "coordinates": station_geo,
                            "pm25": pm25_val,
                            "pm10": pm10_val,
                            "last_update": result.get("time", {}).get("s"),
                            "reliable": distance_km < 25,  # Reliable if within 25km
                            "data_age_hours": 0  # Assume current
                        }
    except Exception as e:
        sources["waqi_error"] = str(e)
        logger.warning(f"WAQI fetch failed: {e}")
    
    # Source 2: OpenAQ for validation
    try:
        url = "https://api.openaq.org/v2/measurements"
        params = {
            "coordinates": f"{lat},{lon}",
            "radius": 30000,  # 30km radius
            "parameter": "pm25",
            "limit": 5,  # Get multiple recent readings
            "order_by": "datetime",
            "sort": "desc"
        }
        with httpx.Client(timeout=15) as client:
            resp = client.get(url, params=params)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("results"):
                    # Take the most recent reading
                    result = data["results"][0]
                    pm25_val = result.get("value", 0)
                    
                    if pm25_val and pm25_val > 0:
                        # Convert PM2.5 to AQI using US EPA formula (approximation)
                        aqi_est = pm25_to_aqi(pm25_val)
                        
                        # Calculate data age
                        try:
                            update_time = datetime.fromisoformat(result.get("date", {}).get("utc", "").replace('Z', '+00:00'))
                            age_hours = (datetime.now().replace(tzinfo=update_time.tzinfo) - update_time).total_seconds() / 3600
                        except:
                            age_hours = 24  # Assume old if can't parse
                        
                        sources["openaq"] = {
                            "aqi": round(aqi_est),
                            "station_name": result.get("location", "OpenAQ Station"),
                            "distance_km": "within_30km",
                            "pm25": pm25_val,
                            "last_update": result.get("date", {}).get("utc"),
                            "reliable": age_hours < 6,  # Reliable if data is <6 hours old
                            "data_age_hours": round(age_hours, 1)
                        }
    except Exception as e:
        sources["openaq_error"] = str(e)
        logger.warning(f"OpenAQ fetch failed: {e}")
    
    # Source 3: PurpleAir (community sensors) - if available
    try:
        # PurpleAir API for community sensor data
        url = "https://api.purpleair.com/v1/sensors"
        headers = {"X-API-Key": os.getenv("PURPLEAIR_API_KEY", "")} if os.getenv("PURPLEAIR_API_KEY") else {}
        
        if headers:
            params = {
                "fields": "pm2.5_atm,latitude,longitude,last_seen,name",
                "location_type": "0",  # Outdoor sensors only
                "max_age": "3600",  # Last hour only
                "nwlng": lon - 0.1,  # Bounding box around location
                "nwlat": lat + 0.1,
                "selng": lon + 0.1,
                "selat": lat - 0.1
            }
            
            with httpx.Client(timeout=10) as client:
                resp = client.get(url, headers=headers, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    sensors = data.get("data", [])
                    
                    if sensors:
                        # Find closest sensor
                        closest_sensor = None
                        min_distance = float('inf')
                        
                        for sensor in sensors:
                            if len(sensor) >= 5:
                                s_pm25, s_lat, s_lon, s_last_seen, s_name = sensor[:5]
                                if s_pm25 and s_lat and s_lon:
                                    dist = ((s_lat - lat)**2 + (s_lon - lon)**2)**0.5 * 111
                                    if dist < min_distance:
                                        min_distance = dist
                                        closest_sensor = {
                                            "pm25": s_pm25,
                                            "aqi": round(pm25_to_aqi(s_pm25)),
                                            "station_name": s_name or "PurpleAir Sensor",
                                            "distance_km": round(dist, 1),
                                            "last_seen": s_last_seen,
                                            "reliable": dist < 10  # Very local data
                                        }
                        
                        if closest_sensor:
                            sources["purpleair"] = closest_sensor
    except Exception as e:
        sources["purpleair_error"] = str(e)
    
    return sources


def pm25_to_aqi(pm25: float) -> float:
    """Convert PM2.5 concentration to AQI using US EPA breakpoints."""
    if pm25 <= 12.0:
        return (50/12.0) * pm25
    elif pm25 <= 35.4:
        return ((100-51)/(35.4-12.1)) * (pm25 - 12.1) + 51
    elif pm25 <= 55.4:
        return ((150-101)/(55.4-35.5)) * (pm25 - 35.5) + 101
    elif pm25 <= 150.4:
        return ((200-151)/(150.4-55.5)) * (pm25 - 55.5) + 151
    elif pm25 <= 250.4:
        return ((300-201)/(250.4-150.5)) * (pm25 - 150.5) + 201
    else:
        return ((500-301)/(500.4-250.5)) * (pm25 - 250.5) + 301


def get_most_accurate_aqi(sources: Dict, lat: float, lon: float) -> Tuple[float, str, Dict]:
    """
    Analyze multiple AQI sources and return the most accurate reading.
    Returns (aqi_value, source_name, accuracy_info)
    """
    reliable_sources = []
    accuracy_info = {
        "total_sources": len([k for k in sources.keys() if not k.endswith("_error")]),
        "reliable_sources": 0,
        "source_comparison": {},
        "selected_reason": ""
    }
    
    # Collect reliable sources
    for source_name, data in sources.items():
        if isinstance(data, dict) and not source_name.endswith("_error"):
            if data.get("aqi") and data.get("reliable", False):
                reliable_sources.append({
                    "name": source_name,
                    "aqi": float(data["aqi"]),
                    "distance": data.get("distance_km", 999),
                    "station": data.get("station_name", "unknown"),
                    "age": data.get("data_age_hours", 0)
                })
                
                accuracy_info["source_comparison"][source_name] = {
                    "aqi": data.get("aqi"),
                    "station": data.get("station_name"),
                    "distance": data.get("distance_km"),
                    "reliable": data.get("reliable")
                }
    
    accuracy_info["reliable_sources"] = len(reliable_sources)
    
    if not reliable_sources:
        # Fallback to any available source
        for source_name, data in sources.items():
            if isinstance(data, dict) and data.get("aqi"):
                accuracy_info["selected_reason"] = f"fallback_to_{source_name}"
                return float(data["aqi"]), f"{source_name}_fallback", accuracy_info
        
        accuracy_info["selected_reason"] = "no_data_available"
        return 100.0, "default_fallback", accuracy_info
    
    # Sort by reliability score (distance and data age)
    def reliability_score(source):
        dist_score = 1 / (1 + source["distance"]) if isinstance(source["distance"], (int, float)) else 0
        age_score = 1 / (1 + source["age"])
        return dist_score + age_score
    
    reliable_sources.sort(key=reliability_score, reverse=True)
    best_source = reliable_sources[0]
    
    # Cross-validation if multiple sources
    if len(reliable_sources) > 1:
        aqis = [s["aqi"] for s in reliable_sources]
        avg_aqi = sum(aqis) / len(aqis)
        variance = max(aqis) - min(aqis)
        
        accuracy_info["variance"] = round(variance, 1)
        
        # If readings are very different (>20 AQI points), prefer closest/newest
        if variance > 20:
            accuracy_info["selected_reason"] = f"high_variance_{variance:.1f}_prefer_closest"
            return best_source["aqi"], f"{best_source['name']}_closest", accuracy_info
        else:
            # Use weighted average for consistent readings
            accuracy_info["selected_reason"] = f"low_variance_{variance:.1f}_weighted_avg"
            weights = [reliability_score(s) for s in reliable_sources]
            weighted_aqi = sum(s["aqi"] * w for s, w in zip(reliable_sources, weights)) / sum(weights)
            return weighted_aqi, "multi_source_weighted", accuracy_info
    
    accuracy_info["selected_reason"] = f"single_best_{best_source['name']}"
    return best_source["aqi"], best_source["name"], accuracy_info


def get_accurate_current_aqi(lat: float, lon: float) -> Tuple[float, Dict]:
    """
    Main function to get the most accurate current AQI with full transparency.
    Returns (aqi_value, full_accuracy_report)
    """
    logger.info(f"🎯 Fetching accurate AQI for ({lat:.4f}, {lon:.4f})")
    
    # Fetch from all sources
    sources = fetch_multiple_aqi_sources(lat, lon)
    
    # Get most accurate reading
    aqi_value, source_name, accuracy_info = get_most_accurate_aqi(sources, lat, lon)
    
    # Build comprehensive accuracy report
    accuracy_report = {
        "final_aqi": round(aqi_value, 1),
        "selected_source": source_name,
        "coordinates": {"lat": lat, "lon": lon},
        "accuracy_info": accuracy_info,
        "all_sources": sources,
        "timestamp": datetime.now().isoformat()
    }
    
    # Log summary
    reliable_count = accuracy_info.get("reliable_sources", 0)
    total_count = accuracy_info.get("total_sources", 0)
    logger.info(f"🎯 Selected AQI: {aqi_value:.1f} from {source_name} ({reliable_count}/{total_count} sources reliable)")
    
    return aqi_value, accuracy_report