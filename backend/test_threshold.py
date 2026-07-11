#!/usr/bin/env python3
"""
Test script to lower alert threshold and trigger alerts
"""

from db import db

def lower_alert_threshold():
    user_id = "1ab47d15-0ecf-4e14-8bdd-0e4ed49b8f04"
    
    print("Setting alert threshold to 50 (very sensitive for testing)...")
    
    # Lower threshold to 50 so alerts trigger more easily
    result = db.client.table("users").update({
        "alert_threshold": 50
    }).eq("id", user_id).execute()
    
    if result.data:
        print("✅ Alert threshold lowered to 50 AQI")
        print("Now any AQI > 50 will trigger alerts")
    else:
        print("❌ Failed to update threshold")
    
    # Verify
    user = db.get_user_by_id(user_id)
    if user:
        print(f"Current threshold: {user.get('alert_threshold', 'Not set')}")

if __name__ == "__main__":
    lower_alert_threshold()