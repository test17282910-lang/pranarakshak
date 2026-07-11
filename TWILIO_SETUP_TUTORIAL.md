# 📱 Twilio SMS Setup Tutorial for Pranarakshak

Complete step-by-step guide to set up SMS alerts for your air quality monitoring system.

---

## 🎯 **What You'll Accomplish**

By the end of this tutorial, you'll have:
- ✅ Twilio account with SMS capabilities
- ✅ Phone number for sending alerts
- ✅ API credentials configured in Railway
- ✅ Working SMS alerts for AQI predictions
- ✅ Tested and verified system

---

## 📋 **Prerequisites**

- Valid phone number for verification
- Railway account (where your backend is deployed)
- Credit card for Twilio (free trial available)

---

## 🚀 **Step 1: Create Twilio Account**

### 1.1 Sign Up
1. Go to https://www.twilio.com/try-twilio
2. Click **"Start your free trial"**
3. Fill in your details:
   - **Email**: Your email address
   - **Password**: Strong password
   - **First/Last Name**: Your real name

### 1.2 Verify Your Phone Number
1. Enter your phone number (with country code)
   - India: `+91XXXXXXXXXX`
   - US: `+1XXXXXXXXXX`
2. Choose **SMS** verification
3. Enter the 6-digit code you receive
4. Click **"Verify"**

### 1.3 Complete Account Setup
1. **What brings you to Twilio?**: Select "Personal Projects" or "Learning"
2. **Which Twilio products?**: Select **"SMS"**
3. **How do you want to use Twilio?**: Select "Send notifications to users"
4. **What's your role?**: Select "Developer"
5. **Do you write code?**: Select "Yes"
6. Click **"Get Started with Twilio"**

---

## 🔑 **Step 2: Get Your Credentials**

### 2.1 Find Your Account SID and Auth Token
1. You'll land on the Twilio Console Dashboard
2. Look for the **"Account Info"** section on the right
3. Copy these values:

```
Account SID: ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
Auth Token: Click "Show" to reveal → xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

⚠️ **Important**: Keep these credentials secure! Don't share them publicly.

### 2.2 Screenshot Guide
The dashboard looks like this:
```
┌─────────────────────────────────────┐
│ Project Info            Account Info │
│                                     │
│ Console Home            Account SID │
│                        AC1234567... │
│                                     │
│                        Auth Token   │
│                        [Show] ****  │
└─────────────────────────────────────┘
```

---

## 📞 **Step 3: Get a Twilio Phone Number**

### 3.1 Get Your Free Trial Number
1. In the Twilio Console, look for **"Get a Twilio phone number"**
2. Click **"Get your first Twilio number"**
3. You'll see a suggested number like `+1 415 123-4567`
4. Click **"Choose this Number"** (or search for a different one)
5. Your number is now active!

### 3.2 Note Your Phone Number
Your Twilio phone number will be in format:
- **US numbers**: `+1234567890`
- **Other countries**: Available based on region

---

## ⚙️ **Step 4: Configure Railway Environment**

### 4.1 Open Railway Dashboard
1. Go to https://railway.app/dashboard
2. Find your **Pranarakshak** project
3. Click on your backend service
4. Click **"Variables"** tab

### 4.2 Add Twilio Variables
Add these 3 environment variables:

```bash
# Variable 1
Name: TWILIO_ACCOUNT_SID
Value: ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Variable 2  
Name: TWILIO_AUTH_TOKEN
Value: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Variable 3
Name: TWILIO_FROM_NUMBER
Value: +1234567890
```

⚠️ **Important**: 
- No quotes around values
- No extra spaces
- Use the exact format shown

### 4.3 Deploy Changes
1. Railway will automatically redeploy after adding variables
2. Wait for deployment to complete (green checkmark)
3. Your backend now has Twilio credentials!

---

## 🧪 **Step 5: Test Your Setup**

### 5.1 Register a Test User
Open PowerShell or Command Prompt and run:

```powershell
$headers = @{"Content-Type" = "application/json"}
$body = @{
    name = "Test User"
    phone = "+91XXXXXXXXXX"  # Your real phone number
    email = "test@example.com"
    password = "testpass123"
    condition = "asthma"
    severity = "moderate"
    alert_threshold = 50
} | ConvertTo-Json

$response = Invoke-RestMethod -Uri "https://pranarakshak-production.up.railway.app/register" -Method POST -Headers $headers -Body $body
Write-Host "User ID: $($response.user_id)"
```

### 5.2 Test SMS Alerts
Use the returned user ID to test alerts:

```powershell
# Replace USER_ID_HERE with actual ID from step 5.1
Invoke-RestMethod -Uri "https://pranarakshak-production.up.railway.app/test-alert/USER_ID_HERE"
```

**Expected Result:**
- You should receive an SMS within 30 seconds
- Check Railway logs for success messages

---

## 🔍 **Step 6: Verify Everything Works**

### 6.1 Check Railway Logs
1. Railway Dashboard → Your Service → **"Logs"** tab
2. Look for these success messages:

```
✓ SMS alert successfully sent to +91... via Twilio. SID: SM...
```

### 6.2 Check Your Phone
You should receive an SMS like:
```
🧪 TEST ALERT from Pranarakshak

Hello Test User! This is a test SMS to verify Twilio is working correctly.
```

### 6.3 Check Supabase Database
1. Go to your Supabase dashboard
2. Check the `alerts_log` table
3. You should see a new entry with `status: "sent"`

---

## 🔧 **Troubleshooting Common Issues**

### Issue 1: "Unable to create record" Error

**Symptoms:** Railway logs show Twilio error
**Cause:** Trial account can only send to verified numbers

**Solution:**
1. Go to Twilio Console → **Phone Numbers** → **Verified Caller IDs**
2. Click **"+"** to add your phone number
3. Verify the number with SMS code
4. Try testing again

### Issue 2: Still Seeing Mock Mode

**Symptoms:** Railway logs show `[MOCK SMS]` instead of real SMS
**Causes & Solutions:**

1. **Wrong credentials format:**
   ```bash
   # Wrong ❌
   TWILIO_ACCOUNT_SID="AC123..."
   TWILIO_FROM_NUMBER="+1234567890"
   
   # Right ✅
   TWILIO_ACCOUNT_SID=AC123...
   TWILIO_FROM_NUMBER=+1234567890
   ```

2. **Credentials not deployed:**
   - Check Railway → Variables tab
   - Ensure all 3 variables are there
   - Redeploy if needed

3. **Typos in variable names:**
   - Must be exact: `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER`

### Issue 3: No SMS Received

**Check these in order:**

1. **Phone number format:**
   ```bash
   # Wrong ❌
   919876543210
   +91 9876 543 210
   
   # Right ✅  
   +919876543210
   ```

2. **Twilio Console → Messaging → Logs:**
   - Check for error messages
   - Look for delivery status

3. **Trial account limits:**
   - Can only send to verified numbers
   - Limited to 500 SMS per month
   - Upgrade to paid account for production use

---

## 💰 **Pricing Information**

### Free Trial Account
- **$15.50 credit** upon signup
- **SMS cost**: ~$0.02 per message to India
- **Limitations**: Only verified phone numbers
- **Duration**: Credit doesn't expire

### Paid Account (Production Ready)
- **SMS to India**: ~₹1.5 per message
- **SMS to US/Canada**: ~$0.0075 per message
- **Monthly cost**: ~₹1,500 for 100 alerts/day
- **Benefits**: Send to any number, no verification needed

---

## 🎉 **Step 7: Production Deployment**

### 7.1 Upgrade Account (When Ready)
1. Twilio Console → **Billing**
2. Add payment method
3. Remove trial restrictions
4. SMS alerts now work for any phone number!

### 7.2 Set Realistic Alert Thresholds
Update user alert thresholds to reasonable values:
- **High sensitivity**: 75-100 AQI
- **Normal sensitivity**: 100-150 AQI  
- **Low sensitivity**: 150-200 AQI

### 7.3 Monitor Usage
- Check Twilio Console → **Usage & Records**
- Set up billing alerts to avoid surprises
- Consider implementing rate limiting (1 alert per 6 hours per user)

---

## ✅ **Final Checklist**

Before going live, ensure:

- [ ] Twilio Account SID added to Railway
- [ ] Twilio Auth Token added to Railway
- [ ] Twilio phone number added to Railway
- [ ] Test SMS received successfully
- [ ] Railway logs show successful delivery
- [ ] Supabase alerts_log table populated
- [ ] Trial phone numbers verified (if using trial)
- [ ] Rate limiting configured (optional but recommended)

---

## 🆘 **Getting Help**

### Twilio Support Resources
- **Documentation**: https://www.twilio.com/docs/sms
- **Support**: https://www.twilio.com/help
- **Console**: https://console.twilio.com/

### Pranarakshak Specific Issues
- Check `ALERT_SETUP.md` for general alert troubleshooting
- Review Railway logs for specific error messages
- Use the `/test-alert/{user_id}` endpoint for debugging

### Common Commands for Testing

```bash
# Test health endpoint
curl https://pranarakshak-production.up.railway.app/health

# Register user (replace with your details)
curl -X POST "https://pranarakshak-production.up.railway.app/register" \
  -H "Content-Type: application/json" \
  -d '{"name":"John Doe","phone":"+919876543210","email":"john@example.com","password":"test123","condition":"asthma","alert_threshold":50}'

# Test alerts (replace USER_ID)
curl "https://pranarakshak-production.up.railway.app/test-alert/USER_ID_HERE"

# Trigger prediction alert  
curl -X POST "https://pranarakshak-production.up.railway.app/predict" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"USER_ID_HERE","lat":28.6139,"lon":77.2090,"condition":"asthma","severity":"severe"}'
```

---

## 🎯 **Next Steps**

After SMS is working:

1. **Set up SendGrid Email alerts** (see `ALERT_SETUP.md`)
2. **Deploy the worker service** for automated monitoring
3. **Test with real users** and gather feedback
4. **Monitor costs** and optimize as needed
5. **Add rate limiting** to prevent spam
6. **Upgrade to paid Twilio** for production use

---

**Congratulations! 🎉** Your Pranarakshak SMS alert system is now fully operational. Users will receive personalized air quality alerts based on their health conditions and location!
