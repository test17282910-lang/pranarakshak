# AQI Health Alert System — Full Implementation Plan

AI-powered predictive health alert system for COPD/Asthma patients. Monitors air quality by GPS location, predicts 24h AQI, and sends SMS/Email alerts with precautions.

---

## System Architecture

```
[User GPS / Browser]
        │
        ▼
[Registration Web Page]  ←── One-time browser GPS capture
        │
        ▼
[Database: Users, Alerts, AQI History]
        │
        ▼
[n8n Scheduler - Hourly]
        │
        ├── Read user lat/lon from DB
        ├── Call FastAPI /predict?lat=&lon=
        │
        ▼
[FastAPI AI Backend]
        ├── Fetch AQI from OpenAQ (primary)
        ├── Fallback → OpenWeatherMap
        ├── Data quality tiering (interpolate / seasonal fallback)
        ├── LSTM + Monte Carlo Dropout inference
        ├── RMSE safety buffer applied
        └── Return: adjusted_aqi, tier, precautions, source
        │
        ▼
[n8n Alert Router]
        ├── Tier: Good/Satisfactory → No alert
        ├── Tier: Moderate → Daily digest
        ├── Tier: Poor+ → Immediate SMS + Email
        └── Rate limiter (no repeat alerts < 6h for non-severe)
        │
        ▼
[User: SMS via Twilio + Email via SendGrid]
        │
        ▼
[Minimal Dashboard: /dashboard → View today + 24h forecast]
```

---

## Project Structure

```
New folder/
├── backend/
│   ├── app.py                # FastAPI server (GPS predict, MC Dropout, tiering)
│   ├── train.py              # LSTM training script + synthetic data generator
│   ├── data_fetcher.py       # OpenAQ + OWM GPS-based data fetching
│   ├── requirements.txt      # Python dependencies (tensorflow-cpu)
│   ├── Procfile              # Railway deployment command
│   └── .env.example          # Environment variable template
│
└── frontend/                 # (Built after backend — UI/UX phase)
    ├── index.html            # Registration page (GPS capture + form)
    └── dashboard.html        # Minimal AQI status card
```

---

## Phase 1: AI Backend (Building Now)

### [NEW] backend/requirements.txt
- `tensorflow-cpu` for Railway compatibility
- `fastapi`, `uvicorn`, `pandas`, `numpy`, `scikit-learn`, `httpx`, `pydantic`

### [NEW] backend/data_fetcher.py
- `fetch_openaq(lat, lon, radius_km)` — calls OpenAQ v3 `/measurements` by coordinates
- `fetch_owm(lat, lon)` — calls OWM Air Pollution API as secondary source
- `get_readings_for_location(lat, lon)` — tries OpenAQ first, falls back to OWM
- `calculate_india_aqi(pm25, pm10)` — India NAQI breakpoints

### [NEW] backend/train.py
- Synthetic data generator (365 days, realistic India AQI cycles) if no CSV found
- Feature engineering: cyclic time encoding, lag-1/6/24h, rolling 6h/24h means
- LSTM (128→64→Dense) with Dropout(0.3) for MC Dropout at inference
- Saves: `aqi_lstm.h5`, `scaler.pkl`, `model_metadata.json` (RMSE/R2/MAE), `seasonal_baseline.json`

### [NEW] backend/app.py
**Three endpoints:**
- `GET /health` — model status, RMSE, last trained at
- `POST /predict` — accepts `{lat, lon, user_id}`, full inference pipeline
- `POST /train` — background retraining trigger

**Inference pipeline:**
1. Fetch data by GPS (OpenAQ → OWM fallback)
2. Data quality tiering (live / interpolated / historical_fallback)
3. Feature engineering (same as training)
4. Monte Carlo Dropout (50 passes, 90th percentile)
5. RMSE safety buffer: `adjusted_aqi = p90_aqi + rmse`
6. India NAQI classification + precautions list
7. Return full `PredictionResponse` with `prediction_source` transparency

### [NEW] backend/Procfile
- `web: uvicorn app:app --host 0.0.0.0 --port $PORT`

---

## Phase 2: Frontend (UI/UX — After Backend)

### Registration Page (`/`)
- Name, Phone, Email, Condition (COPD/Asthma/Both)
- "Allow Location" button → browser GPS → stored as lat/lon
- Fallback: pincode/city input → geocoded via Nominatim
- `location_sharing_consent` checkbox

### Minimal Dashboard (`/dashboard`)
- Current AQI at user's location
- 24h forecast card (Good/Moderate/Poor/Severe)
- Precautions list
- Last updated timestamp + data source badge (Live / Interpolated / Historical)

---

## Phase 3: Database Schema

```sql
-- Users
CREATE TABLE users (
  id UUID PRIMARY KEY,
  name VARCHAR(100),
  phone VARCHAR(20) UNIQUE,
  email VARCHAR(100),
  condition VARCHAR(50),  -- COPD, Asthma, Both
  last_known_lat DECIMAL(9,6),
  last_known_lon DECIMAL(9,6),
  location_updated_at TIMESTAMP,
  location_consent BOOLEAN DEFAULT FALSE,
  active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP DEFAULT NOW()
);

-- Alerts Log
CREATE TABLE alerts_log (
  id UUID PRIMARY KEY,
  user_id UUID REFERENCES users(id),
  predicted_aqi_raw FLOAT,
  predicted_aqi_adjusted FLOAT,
  alert_tier VARCHAR(20),
  prediction_source VARCHAR(30),
  confidence_score FLOAT,
  alert_sent_at TIMESTAMP,
  channel VARCHAR(20)   -- sms, email
);
```

---

## Phase 4: Railway Deployment

1. Push `backend/` directory to GitHub
2. Railway: New Project → Deploy from GitHub
3. Set environment variables: `OPENAQ_API_KEY`, `OWM_API_KEY`
4. Add Volume mount for `/app/data` (model persistence)
5. Generate public domain → update n8n webhook URLs

---

## Verification Plan

### AI Layer
```bash
cd backend
python train.py                    # Verify artifacts created
uvicorn app:app --reload --port 8000
curl http://localhost:8000/health
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"lat": 17.385, "lon": 78.486, "user_id": "test-001"}'
```

### Expected Response
```json
{
  "predicted_aqi_raw": 142.3,
  "predicted_aqi_adjusted": 157.8,
  "rmse_buffer": 15.5,
  "prediction_confidence": 8.2,
  "prediction_source": "openaq",
  "alert_tier": "poor",
  "alert_message": "⚠️ Air quality is Poor. Health risk for COPD/Asthma patients.",
  "precautions": ["Avoid outdoor activities...", ...],
  "forecast_for": "2026-07-11T06:00:00Z"
}
```
