#!/usr/bin/env python3
"""
Smart Indoor Air Quality Recommendations
Suggests optimal times to open windows, run air purifiers, etc.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import List, Dict
from data_fetcher import get_readings_for_location
from worker import classify_aqi
import logging

logger = logging.getLogger(__name__)

def get_indoor_recommendations(
    current_aqi: float, 
    predicted_aqi: float,
    condition: str = "other",
    severity: str = "moderate"
) -> Dict:
    """
    Generate smart indoor air quality recommendations.
    
    Returns:
    - window_advice: When to open/close windows
    - purifier_advice: Air purifier settings
    - activity_advice: Indoor activity recommendations
    """
    
    recommendations = {
        "window_advice": {},
        "purifier_advice": {},
        "activity_advice": {},
        "optimal_ventilation_hours": []
    }
    
    # Window Management
    if current_aqi < 50:
        recommendations["window_advice"] = {
            "action": "open_windows",
            "message": "🌬️ Perfect time to open windows! Fresh outdoor air is better than most indoor air.",
            "duration": "Keep windows open for 15-30 minutes to refresh indoor air"
        }
    elif current_aqi < 100:
        recommendations["window_advice"] = {
            "action": "selective_ventilation", 
            "message": "🪟 Brief ventilation OK. Open windows for 5-10 minutes if indoor air feels stuffy.",
            "duration": "Short bursts only, avoid prolonged exposure"
        }
    else:
        recommendations["window_advice"] = {
            "action": "keep_closed",
            "message": "🚫 Keep all windows and doors sealed. Outdoor air quality is poor.",
            "duration": "Wait for AQI to improve below 100"
        }
    
    # Air Purifier Settings
    if current_aqi > 150:
        recommendations["purifier_advice"] = {
            "setting": "max_speed",
            "message": "💨 Run air purifier on HIGHEST setting continuously. Change filters if overdue.",
            "runtime": "24/7 until AQI improves"
        }
    elif current_aqi > 100:
        recommendations["purifier_advice"] = {
            "setting": "high_speed",
            "message": "🔄 Run air purifier on HIGH setting, especially in bedrooms.",
            "runtime": "At least 12 hours/day"
        }
    elif current_aqi > 50:
        recommendations["purifier_advice"] = {
            "setting": "medium_speed", 
            "message": "⚙️ Run air purifier on MEDIUM setting during sleep and work hours.",
            "runtime": "8-10 hours/day"
        }
    else:
        recommendations["purifier_advice"] = {
            "setting": "low_or_off",
            "message": "✨ Air purifier can run on LOW or be turned off. Great outdoor air quality!",
            "runtime": "Optional, save energy"
        }
    
    # Indoor Activities
    if condition in ["copd", "asthma", "both"] and current_aqi > 100:
        recommendations["activity_advice"] = {
            "exercise": "❌ Avoid indoor cardio near windows/doors. Light stretching only.",
            "cooking": "🍳 Use exhaust fans while cooking. Avoid frying or high-heat cooking.",
            "cleaning": "🧹 Postpone dust-generating cleaning. Use damp cloths if necessary."
        }
    elif current_aqi > 150:
        recommendations["activity_advice"] = {
            "exercise": "🧘 Light yoga/stretching OK. Avoid intense cardio workouts.",
            "cooking": "🥗 Prefer no-cook meals. If cooking, use lids and ventilation.",
            "cleaning": "✨ Good time for indoor organizing (non-dusty activities)."
        }
    else:
        recommendations["activity_advice"] = {
            "exercise": "💪 Perfect for indoor workouts! Air quality supports exercise.",
            "cooking": "👨‍🍳 Great time for cooking. Open kitchen windows if desired.",
            "cleaning": "🏠 Excellent day for deep cleaning and organizing."
        }
    
    return recommendations

async def get_24h_indoor_forecast(lat: float, lon: float) -> List[Dict]:
    """
    Provide hour-by-hour indoor air quality guidance for next 24 hours.
    """
    forecast = []
    
    try:
        # Get current data
        df, _, current_aqi = await asyncio.to_thread(get_readings_for_location, lat, lon)
        
        if current_aqi is None:
            current_aqi = 100  # fallback
        
        # Generate hourly recommendations (simplified - in reality would use ML predictions)
        for hour in range(24):
            future_time = datetime.now(timezone.utc) + timedelta(hours=hour)
            
            # Simulate daily AQI pattern (typically worse during rush hours)
            hour_of_day = future_time.hour
            if hour_of_day in [7, 8, 18, 19]:  # Rush hours
                simulated_aqi = current_aqi * 1.2
            elif hour_of_day in [2, 3, 4, 5]:  # Early morning
                simulated_aqi = current_aqi * 0.8
            else:
                simulated_aqi = current_aqi
            
            recommendations = get_indoor_recommendations(simulated_aqi, simulated_aqi)
            
            forecast.append({
                "hour": future_time.strftime("%H:00"),
                "predicted_aqi": round(simulated_aqi),
                "window_action": recommendations["window_advice"]["action"],
                "purifier_setting": recommendations["purifier_advice"]["setting"],
                "is_optimal_ventilation": simulated_aqi < 50
            })
    
    except Exception as e:
        logger.error(f"Error generating indoor forecast: {e}")
        
    return forecast

def get_optimal_ventilation_windows(forecast: List[Dict]) -> List[str]:
    """Extract the best times for natural ventilation."""
    optimal_times = []
    
    for item in forecast:
        if item["is_optimal_ventilation"]:
            optimal_times.append(item["hour"])
    
    if not optimal_times:
        # Find least bad times
        sorted_forecast = sorted(forecast, key=lambda x: x["predicted_aqi"])
        optimal_times = [item["hour"] for item in sorted_forecast[:6]]
    
    return optimal_times[:6]  # Return top 6 time slots