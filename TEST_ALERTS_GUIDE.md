# 🧪 Alert System Testing Guide

Your alert system is fully implemented! Let's test it step by step to diagnose why alerts aren't being sent.

## 📋 Quick Diagnostic Steps

### Step 1: Check Railway Environment Variables

1. Go to Railway Dashboard → Your Service → Variables
2. Verify these are set (no spaces, no quotes):
   ```
   TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxx (starts with AC)
   TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxx (32 characters)
   TWILIO_FROM_NUMBER=+1234567890 (with country code)
   ```

3. **Important for Trial Accounts**: Make sure your phone number is verified in Twilio Console
   - Go to https://console.twilio.com/
   - Phone Numbers → Verified Caller IDs
   - Add your phone number if not already verified

### Step 2: Test Alert Endpoint Directly

Use this test endpoint to verify Twilio/SendGrid configuration:

**A. First register a test user with your real phone/email:**

```bash
# Use your real phone number and email
curl -X POST "https://pranarakshak-production.up.railway.app/register" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test User",
    "phone": "+91XXXXXXXXXX",
    "email": "your@email.com",
    "password": "testpass123",
    "condition": "asthma",
    "severity": "moderate",
    "alert_threshold": 50
  }'
```

**B. Copy the returned `user_id` and test alerts:**

```bash
# Replace USER_ID_HERE with the actual ID from step A
curl "https://pranarakshak-production.up.railway.app/test-alert/USER_ID_HERE"
```

**Expected Response:**
```json
{
  "user_id": "your-user-id",
  "sms": {
    "status": "sent",
    "id": "SMxxxxxxxxxxxxxxxx",
    "phone": "+91XXXXXXXXXX"
  },
  "email": {
    "status": "sent", 
    "id": "email_id_here",
    "email": "your@email.com"
  }
}
```

### Step 3: Check Railway Logs

1. Railway Dashboard → Your Service → Logs
2. Look for these log messages after testing:

**✅ Success Messages:**
```
✓ SMS alert successfully sent to +91... via Twilio. SID: SM...
✓ Email alert successfully sent to user@... via SendGrid. ID: ...
```

**🧪 Mock Mode (means credentials not working):**
```
📬 [MOCK SMS] to +91...: Test message
📬 [MOCK EMAIL] to user@...: Subject: Test Alert
```

**❌ Error Messages:**
```
❌ Twilio SMS dispatch failed: [Error details]
❌ SendGrid Email dispatch failed: [Error details]
```

### Step 4: Test Real Alert Trigger

Once the test endpoint works, trigger a real alert by making a prediction with low threshold:

```bash
# This should trigger an alert since threshold is set to 50
curl -X POST "https://pranarakshak-production.up.railway.app/predict" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "YOUR_USER_ID_HERE",
    "lat": 28.6139,
    "lon": 77.2090,
    "condition": "asthma",
    "severity": "severe"
  }'
```

The alert will trigger if:
- **Predicted AQI ≥ 50** (your custom threshold), OR
- **Health risk tier is "High Risk" or "Critical"**

---

## 🚨 Common Issues & Solutions

### Issue 1: Still Seeing Mock Mode
**Symptoms:** Railway logs show `[MOCK SMS]` and `[MOCK EMAIL]`
**Solutions:**
1. Double-check Railway environment variables have no spaces
2. Restart the Railway service after adding variables
3. Make sure credentials don't contain placeholder text like "your_twilio_sid"

### Issue 2: Twilio "Unable to create record"
**Symptoms:** `❌ Twilio SMS dispatch failed: Unable to create record`
**Solutions:**
1. **Trial Account**: Phone number must be verified in Twilio Console
2. Check phone number format: `+919999999999` (with country code, no spaces)
3. Check TWILIO_FROM_NUMBER is your actual Twilio number

### Issue 3: SendGrid Authentication Error
**Symptoms:** `❌ SendGrid Email dispatch failed: Unauthorized`
**Solutions:**
1. Regenerate API key in SendGrid dashboard
2. Make sure API key has "Mail Send" permission
3. Verify sender email in SendGrid → Settings → Sender Authentication

### Issue 4: No Entries in alerts_log Table
**Symptoms:** Supabase `alerts_log` table is empty
**Solutions:**
1. Alerts only trigger when AQI crosses threshold or risk is High/Critical
2. Test with very low custom threshold (like 50) to force trigger
3. Use the `/test-alert` endpoint to bypass AQI logic

---

## 💡 Next Steps After Testing

Once alerts work:

1. **Set Realistic Threshold**: Update user's `alert_threshold` to reasonable value (100-150)
2. **Deploy Worker**: Set up `worker.py` to send periodic alerts automatically
3. **Monitor Costs**: Watch Twilio/SendGrid usage to avoid unexpected charges

---

## 📞 Quick Test Commands

**Replace these with your actual values:**

```bash
# 1. Register test user
curl -X POST "https://pranarakshak-production.up.railway.app/register" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "John Doe", 
    "phone": "+919876543210", 
    "email": "john@example.com",
    "password": "test123", 
    "condition": "asthma", 
    "alert_threshold": 50
  }'

# 2. Test alerts (use returned user_id)
curl "https://pranarakshak-production.up.railway.app/test-alert/USER_ID_HERE"

# 3. Check health endpoint
curl "https://pranarakshak-production.up.railway.app/health"
```

---

## 🎯 Expected Results

After following this guide:
- ✅ You should receive test SMS and email
- ✅ Railway logs show successful Twilio/SendGrid messages  
- ✅ `alerts_log` table in Supabase gets populated
- ✅ Real predictions trigger alerts when AQI is high

If you're still having issues after this guide, check the Railway logs and share the error messages!