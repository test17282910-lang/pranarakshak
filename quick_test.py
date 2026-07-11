#!/usr/bin/env python3
"""
Quick Alert Test Script
Run this to test your Pranarakshak alert system in 2 minutes.
"""

import requests
import json
import time

# Configuration - UPDATE THESE WITH YOUR DETAILS
TEST_USER = {
    "name": "Alert Test User",
    "phone": "+919876543210",  # ← UPDATE: Your real phone number with country code
    "email": "your@email.com",  # ← UPDATE: Your real email address
    "password": "testpass123",
    "condition": "asthma",
    "severity": "moderate", 
    "alert_threshold": 50  # Low threshold to trigger alerts easily
}

BACKEND_URL = "https://pranarakshak-production.up.railway.app"

def test_backend_health():
    """Test if backend is responding"""
    print("🔍 Testing backend health...")
    try:
        response = requests.get(f"{BACKEND_URL}/health", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Backend is healthy: {data.get('status', 'unknown')}")
            return True
        else:
            print(f"❌ Backend unhealthy: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Backend connection failed: {e}")
        return False

def register_test_user():
    """Register a test user and return user_id"""
    print(f"\n📝 Registering test user: {TEST_USER['name']}")
    print(f"   Phone: {TEST_USER['phone']}")
    print(f"   Email: {TEST_USER['email']}")
    
    try:
        response = requests.post(
            f"{BACKEND_URL}/register",
            json=TEST_USER,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            user_id = data.get('user_id')
            print(f"✅ User registered successfully: {user_id}")
            return user_id
        else:
            print(f"❌ Registration failed: HTTP {response.status_code}")
            print(f"   Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Registration error: {e}")
        return None

def test_alerts(user_id):
    """Test alert system using the test endpoint"""
    print(f"\n🧪 Testing alert system for user: {user_id}")
    
    try:
        response = requests.get(
            f"{BACKEND_URL}/test-alert/{user_id}",
            timeout=15  # SMS/email can take a few seconds
        )
        
        if response.status_code == 200:
            data = response.json()
            print("📊 Alert test results:")
            
            # Check SMS result
            sms_result = data.get('sms', {})
            if sms_result.get('status') == 'sent':
                print(f"   ✅ SMS: Sent successfully (ID: {sms_result.get('id', 'N/A')})")
            elif sms_result.get('status') == 'skipped':
                print(f"   ⏭️  SMS: Skipped - {sms_result.get('reason', 'Unknown')}")
            else:
                print(f"   ❌ SMS: Failed - {sms_result}")
            
            # Check Email result  
            email_result = data.get('email', {})
            if email_result.get('status') == 'sent':
                print(f"   ✅ Email: Sent successfully (ID: {email_result.get('id', 'N/A')})")
            elif email_result.get('status') == 'skipped':
                print(f"   ⏭️  Email: Skipped - {email_result.get('reason', 'Unknown')}")
            else:
                print(f"   ❌ Email: Failed - {email_result}")
            
            return data
        else:
            print(f"❌ Alert test failed: HTTP {response.status_code}")
            print(f"   Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Alert test error: {e}")
        return None

def trigger_prediction_alert(user_id):
    """Trigger a real prediction to test automatic alerts"""
    print(f"\n🎯 Testing automatic alert via prediction for user: {user_id}")
    
    prediction_data = {
        "user_id": user_id,
        "lat": 28.6139,  # Delhi coordinates
        "lon": 77.2090,
        "condition": TEST_USER['condition'],
        "severity": TEST_USER['severity']
    }
    
    try:
        response = requests.post(
            f"{BACKEND_URL}/predict",
            json=prediction_data,
            timeout=15
        )
        
        if response.status_code == 200:
            data = response.json() 
            aqi = data.get('predicted_aqi_adjusted', 0)
            tier = data.get('alert_tier', 'Unknown')
            threshold = TEST_USER['alert_threshold']
            
            print(f"📊 Prediction results:")
            print(f"   AQI: {aqi}")
            print(f"   Risk Tier: {tier}")
            print(f"   Your Threshold: {threshold}")
            
            if aqi >= threshold or tier.lower() in ['high risk', 'critical']:
                print(f"   🚨 Alert should be triggered! (AQI {aqi} ≥ {threshold} OR tier is {tier})")
            else:
                print(f"   ℹ️  No alert triggered (AQI {aqi} < {threshold} AND tier is {tier})")
                
            return data
        else:
            print(f"❌ Prediction failed: HTTP {response.status_code}")
            print(f"   Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Prediction error: {e}")
        return None

def main():
    """Run the complete alert system test"""
    print("=" * 60)
    print("🧪 PRANARAKSHAK ALERT SYSTEM TEST")
    print("=" * 60)
    
    # Check if user updated the configuration
    if TEST_USER['phone'] == "+919876543210" or TEST_USER['email'] == "your@email.com":
        print("⚠️  WARNING: Please update TEST_USER details at the top of this script!")
        print("   Update 'phone' and 'email' with your real contact information.")
        return
    
    # Step 1: Test backend connectivity
    if not test_backend_health():
        print("\n❌ Backend is not responding. Check Railway deployment.")
        return
    
    # Step 2: Register test user
    user_id = register_test_user()
    if not user_id:
        print("\n❌ Could not register test user. Check backend logs.")
        return
    
    print("\n⏳ Waiting 2 seconds before testing alerts...")
    time.sleep(2)
    
    # Step 3: Test alert endpoints
    alert_results = test_alerts(user_id)
    if not alert_results:
        print("\n❌ Alert test failed. Check Railway logs and credentials.")
        return
    
    print("\n⏳ Waiting 3 seconds before testing prediction alerts...")
    time.sleep(3)
    
    # Step 4: Test prediction-triggered alerts
    prediction_results = trigger_prediction_alert(user_id)
    
    # Summary
    print("\n" + "=" * 60)
    print("📋 TEST SUMMARY")
    print("=" * 60)
    
    if alert_results:
        sms_ok = alert_results.get('sms', {}).get('status') == 'sent'
        email_ok = alert_results.get('email', {}).get('status') == 'sent'
        
        print(f"Direct Alert Test:")
        print(f"   SMS: {'✅ Working' if sms_ok else '❌ Failed'}")
        print(f"   Email: {'✅ Working' if email_ok else '❌ Failed'}")
        
        if sms_ok or email_ok:
            print(f"\n🎉 SUCCESS! Check your phone/email for test messages.")
        else:
            print(f"\n🔧 NEEDS SETUP: Add Twilio/SendGrid credentials to Railway")
    
    if prediction_results:
        print(f"\nPrediction Alert Test: ✅ Completed")
        print(f"   Check Railway logs for alert delivery confirmations")
    
    print("\n💡 Next Steps:")
    print("   1. Check your phone and email for test messages")
    print("   2. Check Railway → Logs for success/error messages") 
    print("   3. Check Supabase → alerts_log table for logged alerts")
    print("   4. If alerts not working, see TEST_ALERTS_GUIDE.md")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()