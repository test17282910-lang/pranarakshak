#!/usr/bin/env python3
"""
Quick script to update user phone number in database
"""

import sys
from dotenv import load_dotenv
from db import db

load_dotenv()

def update_user_phone():
    user_id = "1ab47d15-0ecf-4e14-8bdd-0e4ed49b8f04"
    new_phone = "+918121094411"  # Correct phone number
    
    print(f"Updating user {user_id} phone to {new_phone}...")
    
    # Get current user
    user = db.get_user_by_id(user_id)
    if not user:
        print(f"❌ User {user_id} not found!")
        return
    
    print(f"Current phone: {user.get('phone', 'None')}")
    print(f"Current name: {user.get('name', 'None')}")
    
    # Update phone number directly using Supabase client
    try:
        result = db.client.table("users").update({
            "phone": new_phone
        }).eq("id", user_id).execute()
        
        if result.data:
            print(f"✅ Phone updated successfully to {new_phone}")
        else:
            print("❌ Failed to update phone")
    except Exception as e:
        print(f"❌ Error updating phone: {e}")
    
    # Verify update
    updated_user = db.get_user_by_id(user_id)
    if updated_user:
        print(f"Verified new phone: {updated_user.get('phone', 'None')}")

if __name__ == "__main__":
    update_user_phone()