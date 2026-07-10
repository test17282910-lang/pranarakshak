# Pranarakshak Alert System Setup Guide

This guide will help you set up SMS alerts via Twilio and email alerts via SendGrid.

---

## 🚀 Quick Start

Your alert system is already coded and ready! You just need to add credentials.

**Current Status:**
- ✅ Alert system code (`alerts.py`) is complete
- ✅ Dependencies (`twilio`, `sendgrid`) are installed
- ✅ Mock mode enabled for testing without credentials
- ⏳ **Need**: Real Twilio and SendGrid credentials

---

## 📱 Step 1: Twilio SMS Setup (15 minutes)

### 1.1 Create Twilio Account
1. Go to https://www.twilio.com/try-twilio
2. Sign up for a free trial account
3. Verify your email and phone number

### 1.2 Get Your Credentials
After signup, you'll see your **Twilio Console Dashboard**:

1. **Account SID**: Found on dashboard homepage
   - Looks like: `ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`
   
2. **Auth Token**: Click "Show" next to Auth Token
   - Looks like: `xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

3. **Phone Number**: 
   - Click "Get a Trial Number" (free)
   - Or go to Phone Numbers → Manage → Buy a number
   - Format: `+1234567890`

### 1.3 Add to Railway Environment Variables

Go to Railway → Your Service → Variables → Add these:

```
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_FROM_NUMBER=+1234567890
```

### 1.4 Trial Account Limitations
⚠️ **Free trial accounts can only send to verified phone numbers**

To verify a number:
1. Go to Twilio Console → Phone Numbers → Verified Caller IDs
2. Click "+" to add your phone number
3. Enter the verification code sent via SMS

**For production**: Upgrade to a paid account (~$20/month) to send to any number.

---

## 📧 Step 2: SendGrid Email Setup (15 minutes)

### 2.1 Create SendGrid Account
1. Go to https://signup.sendgrid.com/
2. Sign up for a free account (100 emails/day free forever)
3. Verify your email address

### 2.2 Create API Key
1. Log in to SendGrid
2. Go to **Settings** → **API Keys**
3. Click **"Create API Key"**
4. Name it: `Pranarakshak-Production`
5. Choose **"Full Access"** (or "Restricted Access" with Mail Send enabled)
6. Click **"Create & View"**
7. **COPY THE KEY NOW** (you can't see it again!)
   - Looks like: `SG.xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

### 2.3 Verify Sender Email
SendGrid requires you to verify the "from" email address:

**Option A: Single Sender Verification (Easiest)**
1. Go to **Settings** → **Sender Authentication**
2. Click **"Verify a Single Sender"**
3. Fill in:
   - **From Email**: Your email (e.g., `alerts@yourdomain.com` or your Gmail)
   - **From Name**: `Pranarakshak`
   - **Reply To**: Same email
   - **Company details**: Fill in your info
4. Click **"Create"**
5. Check your email inbox and click the verification link

**Option B: Domain Authentication (For custom domains)**
- Only if you own a domain (e.g., `pranarakshak.com`)
- Follow SendGrid's domain authentication wizard
- Requires adding DNS records

### 2.4 Add to Railway Environment Variables

Go to Railway → Your Service → Variables → Add these:

```
SENDGRID_API_KEY=SG.xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
SENDGRID_FROM_EMAIL=alerts@yourdomain.com
```

⚠️ **Important**: The `SENDGRID_FROM_EMAIL` MUST match the verified sender email from Step 2.3!

---

## 🧪 Step 3: Test the Alert System

### 3.1 Test Locally (Optional)

If you want to test before deploying:

```bash
cd backend
python -c "
from alerts import send_sms, send_email

# Test SMS
status, sid = send_sms('+919999999999', 'Test SMS from Pranarakshak')
print(f'SMS Status: {status}, ID: {sid}')

# Test Email
status, msg_id = send_email(
    'your@email.com',
    'Test Alert from Pranarakshak',
    '<h1>AQI Alert</h1><p>This is a test email</p>'
)
print(f'Email Status: {status}, ID: {msg_id}')
"
```

### 3.2 Test via API

Once deployed to Railway:

```bash
# Register a test user (use your real phone/email)
curl -X POST https://pranarakshak-production.up.railway.app/register \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test User",
    "email": "your@email.com",
    "phone": "+919999999999",
    "password": "testpass123",
    "condition": "asthma",
    "severity": "moderate",
    "lat": 28.6139,
    "lon": 77.2090
  }'

# Trigger a prediction (will send alert if AQI is high)
curl -X POST https://pranarakshak-production.up.railway.app/predict \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "your_user_id_here",
    "lat": 28.6139,
    "lon": 77.2090,
    "condition": "asthma",
    "severity": "moderate"
  }'
```

---

## 🔄 Step 4: Set Up Automated Monitoring (Worker)

Currently, users only get alerts when they manually check the dashboard. Let's add automated monitoring!

### 4.1 Review worker.py

The `worker.py` file periodically checks all users and sends alerts:

```python
# Runs every 4 hours by default
# Checks each user's location
# Sends alerts if AQI becomes dangerous
```

### 4.2 Deploy Worker to Railway

**Option A: Separate Worker Service**
1. Railway Dashboard → New Service
2. Connect same GitHub repo
3. Settings:
   - **Root Directory**: `backend`
   - **Start Command**: `python worker.py`
   - **Environment Variables**: Copy all from main service

**Option B: Background Task in Main Service**
- Add to your Procfile:
  ```
  web: uvicorn app:app --host 0.0.0.0 --port $PORT
  worker: python worker.py
  ```

### 4.3 Configure Worker Schedule

Edit `worker.py` to adjust frequency:

```python
# Check every 2 hours (more frequent)
POLLING_INTERVAL = 2 * 60 * 60

# Or every 6 hours (less frequent, fewer API calls)
POLLING_INTERVAL = 6 * 60 * 60
```

---

## 📊 Step 5: Monitoring & Logs

### 5.1 Check Railway Logs

Railway → Your Service → Logs

Look for:
```
✓ SMS alert successfully sent to +91... via Twilio
✓ Email alert successfully sent to user@... via SendGrid
```

Or for mock mode:
```
📬 [MOCK SMS] to +91...: AQI Alert message
📬 [MOCK EMAIL] to user@...: Subject: AQI Alert
```

### 5.2 View Alert History in Database

Check Supabase → Table Editor → `alerts_log`:
- Shows all sent alerts
- Status: `sent`, `failed`, `suppressed`
- Includes Twilio SID / SendGrid message ID

---

## 💰 Cost Estimates

### Twilio Pricing
- **Trial**: Free (verified numbers only)
- **Production**: 
  - US/Canada: $0.0075 per SMS
  - India: ~$0.02 per SMS
  - If you send 100 alerts/day: ~$60/month

### SendGrid Pricing
- **Free**: 100 emails/day forever
- **Essentials**: $19.95/month for 50K emails
- If you send 100 alerts/day: Free tier is enough!

### Estimated Total Monthly Cost
- **Development**: $0 (mock mode)
- **Small scale** (<100 users): ~$20-40/month
- **Medium scale** (500 users): ~$100-150/month

---

## 🐛 Troubleshooting

### SMS Not Sending

**"Unable to create record" error:**
- ✅ Check if phone number is verified (trial accounts)
- ✅ Verify TWILIO_FROM_NUMBER format: `+1234567890`
- ✅ Check Twilio Console → Messaging → Logs for details

**"Authentication Error":**
- ✅ Double-check TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN
- ✅ Make sure there are no extra spaces

### Email Not Sending

**"Sender email not verified":**
- ✅ Go to SendGrid → Sender Authentication
- ✅ Verify SENDGRID_FROM_EMAIL matches verified sender

**"403 Forbidden":**
- ✅ Check API key has "Mail Send" permission
- ✅ Regenerate API key if needed

**Email goes to spam:**
- ✅ Set up domain authentication (SPF, DKIM)
- ✅ Add unsubscribe link in email template
- ✅ Use verified sender identity

### Mock Mode Stuck

If you've added credentials but still seeing `[MOCK SMS]`:
- ✅ Check Railway environment variables are set
- ✅ Restart the Railway service
- ✅ Verify credentials don't contain placeholder text like "your_twilio_sid"

---

## ✅ Final Checklist

Before going live:

- [ ] Twilio Account SID added to Railway
- [ ] Twilio Auth Token added to Railway
- [ ] Twilio phone number added to Railway
- [ ] SendGrid API Key added to Railway
- [ ] SendGrid sender email verified
- [ ] SendGrid sender email added to Railway
- [ ] Tested SMS alert (received real SMS)
- [ ] Tested email alert (received real email)
- [ ] Worker deployed (optional but recommended)
- [ ] Checked Railway logs for errors
- [ ] Verified alerts appear in Supabase `alerts_log` table

---

## 🚀 Next Steps After Setup

1. **Test with Real Users**: 
   - Register with your real phone/email
   - Wait for AQI to change (or manually trigger)
   - Verify you receive alerts

2. **Add Rate Limiting**:
   - Prevent spam by limiting 1 alert per 6 hours per user
   - Already implemented in code!

3. **Customize Alert Messages**:
   - Edit `app.py` prediction endpoint
   - Personalize SMS/email content
   - Add user's name, condition-specific advice

4. **Monitor Costs**:
   - Check Twilio/SendGrid usage monthly
   - Adjust worker frequency if needed
   - Consider upgrading if hitting free tier limits

---

## 📞 Support

If you run into issues:

1. Check Railway logs for error messages
2. Verify all environment variables are set correctly
3. Test credentials using Twilio/SendGrid consoles
4. Review `alerts.py` code for any issues

**Twilio Support**: https://www.twilio.com/help
**SendGrid Support**: https://sendgrid.com/support/

---

Good luck! Your alert system is production-ready once you add the credentials. 🎉
