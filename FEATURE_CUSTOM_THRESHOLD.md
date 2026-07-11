# Custom AQI Alert Threshold Feature

## Overview
Users can now set their own "unsafe AQI" threshold. When AQI crosses this custom value, they will receive SMS and email alerts, regardless of the calculated health risk tier.

---

## ✨ Features Implemented

### 1. **Registration Form Update**
- ✅ New input field: "Your Unsafe AQI Level"
- ✅ Default value: 100 (Satisfactory level)
- ✅ Range: 50-500 AQI
- ✅ Helper text with suggestions:
  - High sensitivity: 50 (Good)
  - Standard: 100 (Satisfactory)
  - Low sensitivity: 150 (Moderate)

### 2. **Database Schema**
- ✅ Column already exists: `users.alert_threshold` (INTEGER, default 100)
- ✅ Stored in Supabase for each user

### 3. **Alert Logic Update**
Alerts are now triggered when **EITHER**:
- **Option A**: AQI crosses user's custom threshold
- **Option B**: Calculated health risk is "High Risk" or "Critical"

This means:
- User with threshold=50 gets alerts much earlier
- User with threshold=200 only gets alerts at very high AQI
- Health-based risk calculation still applies

### 4. **SMS Alert Message**
Now includes reason for alert:
```
🚨 Pranarakshak Alert

AQI 125 crossed your threshold (100)

Your personal health risk is Caution...

Top precaution: Stay indoors
```

---

## 📝 User Experience

### Registration Flow:
1. User fills basic info (name, email, phone, password)
2. Selects health condition (Asthma, COPD, Both, Other)
3. Selects severity (Mild, Moderate, Severe)
4. **NEW**: Sets custom AQI threshold (e.g., 80)
5. Shares GPS location
6. Submits registration

### Alert Flow:
1. User checks dashboard OR worker runs periodic check
2. System fetches current/predicted AQI
3. Checks if AQI >= user's threshold
4. If yes → Send SMS + Email alert
5. Log alert in `alerts_log` table

---

## 🧪 Testing

### Test Case 1: Low Threshold (High Sensitivity)
```bash
# Register with threshold=50
{
  "name": "Sensitive User",
  "phone": "+919999999999",
  "email": "test@example.com",
  "password": "test123",
  "condition": "asthma",
  "severity": "severe",
  "alert_threshold": 50,  # <-- Low threshold
  "lat": 28.6,
  "lon": 77.2
}

# Expected: Alert triggers when AQI > 50 (even if health risk is "Safe")
```

### Test Case 2: Standard Threshold
```bash
# Register with threshold=100 (default)
{
  "alert_threshold": 100
}

# Expected: Alert triggers when AQI > 100
```

### Test Case 3: High Threshold (Low Sensitivity)
```bash
# Register with threshold=200
{
  "alert_threshold": 200
}

# Expected: Only alerts at very high AQI (200+)
```

---

## 💡 Use Cases

### High Sensitivity Users:
- **Severe COPD/Asthma patients**
- Threshold: 50-80
- Gets alerts even when air quality is "Satisfactory"
- Maximizes safety but may get more frequent alerts

### Standard Users:
- **Moderate respiratory conditions**
- Threshold: 100-120
- Balanced approach
- Alerts when air quality becomes concerning

### Low Sensitivity Users:
- **Mild conditions or general monitoring**
- Threshold: 150-200
- Only alerts at significantly poor air quality
- Fewer alerts, less interruption

---

## 🔧 API Changes

### Registration Endpoint (`POST /register`)
**New Field:**
```json
{
  "alert_threshold": 100  // Optional, defaults to 100
}
```

### Predict Endpoint (`POST /predict`)
**Updated Logic:**
- Checks user's `alert_threshold` from database
- Compares against `predicted_aqi_adjusted`
- Triggers alert if threshold crossed

---

## 📊 Database

### Table: `users`
```sql
alert_threshold INTEGER DEFAULT 100
```

**Existing Values:**
- Users registered before this feature: Default to 100
- New users: Can set custom value (50-500)

**To update existing user:**
```sql
UPDATE users 
SET alert_threshold = 80 
WHERE id = 'user_id_here';
```

---

## 🚀 Benefits

1. **Personalized Control**: Users decide what's "unsafe" for them
2. **Flexibility**: Can adjust based on their condition severity
3. **Reduced Alert Fatigue**: High-threshold users get fewer alerts
4. **Early Warning**: Low-threshold users get advance notice
5. **Compliance**: Meets accessibility needs for varying sensitivity levels

---

## 📱 UI Example

**Registration Form:**
```
╔════════════════════════════════════════╗
║ Your Unsafe AQI Level                  ║
║ (Alert me when AQI crosses this)       ║
║                                        ║
║ [     100     ] ← Number input         ║
║                                        ║
║ Standard: 100 (Satisfactory)           ║
║ High sensitivity: 50 (Good)            ║
║ Low sensitivity: 150 (Moderate)        ║
╚════════════════════════════════════════╝
```

---

## 🔄 Future Enhancements

1. **Dashboard Settings**: Allow users to update threshold after registration
2. **Smart Suggestions**: AI-recommended threshold based on condition + severity
3. **Time-based Thresholds**: Different thresholds for day vs night
4. **Location-based**: Different thresholds for home vs outdoor activities
5. **Historical Analysis**: Show how many alerts user would have received with different thresholds

---

## ✅ Deployment Checklist

- [x] Database column exists (`alert_threshold`)
- [x] Frontend form field added
- [x] Backend API accepts new field
- [x] Alert logic updated
- [x] SMS message includes threshold info
- [x] Tested locally
- [ ] Test on production with real Twilio
- [ ] Verify existing users default to 100
- [ ] Monitor alert frequency

---

## 🎉 Status: LIVE

The feature is now deployed and available for all new registrations!

**Next Steps:**
1. Test with Twilio credentials
2. Register a test user with low threshold (50)
3. Verify alert is sent when AQI > 50
4. Add dashboard UI to update threshold later

