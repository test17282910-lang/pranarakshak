#!/usr/bin/env python3
"""
Update user location to Ghatkesar coordinates for accurate AQI
"""

import asyncio
from db import db

async def update_to_ghatkesar():
    user_id = "1ab47d15-0ecf-4e14-8bdd-0e4ed49b8f04"
    
    # Ghatkesar coordinates (Hyderabad district)
    ghatkesar_lat = 17.5449  
    ghatkesar_lon = 78.6898
    
    print(f"Updating user location to Ghatkesar: {ghatkesar_lat}, {ghatkesar_lon}")
    
    # Get current user
    user = await asyncio.to_thread(db.get_user_by_id, user_id)
    if not user:
        print(f"❌ User {user_id} not found!")
        return
    
    print(f"Current location: {user.get('last_known_lat')}, {user.get('last_known_lon')}")
    
    # Update location using the existing update_user_location method
    try:
        await asyncio.to_thread(
            db.update_user_location, 
            user_id, 
            ghatkesar_lat, 
            ghatkesar_lon,
            "Ghatkesar, Hyderabad"
        )
        print(f"✅ Location updated to Ghatkesar successfully!")
        
        # Verify update
        updated_user = await asyncio.to_thread(db.get_user_by_id, user_id)
        if updated_user:
            print(f"Verified location: {updated_user.get('last_known_lat')}, {updated_user.get('last_known_lon')}")
    except Exception as e:
        print(f"❌ Error updating location: {e}")

if __name__ == "__main__":
    asyncio.run(update_to_ghatkesar())