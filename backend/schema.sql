-- ============================================================
-- AQI Health Alert System — Supabase PostgreSQL Schema
-- Run this in: Supabase Dashboard → SQL Editor → New Query
-- ============================================================

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";


-- ──────────────────────────────────────────────────────────────
-- TABLE: users
-- Stores patient profiles with GPS coordinates and health info
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id                   UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name                 VARCHAR(100) NOT NULL,
    phone                VARCHAR(20) UNIQUE,          -- for SMS alerts via Twilio
    email                VARCHAR(150) UNIQUE,          -- for email alerts via SendGrid
    condition            VARCHAR(50) NOT NULL,          -- 'COPD', 'Asthma', 'Both', 'Other'
    severity             VARCHAR(20) DEFAULT 'moderate', -- 'mild', 'moderate', 'severe'
    symptoms             VARCHAR(50)[] DEFAULT '{}',     -- array of symptoms e.g. Wheezing, Cough
    personalized_issue   TEXT,                           -- patient-specific triggers or notes

    -- GPS location (captured via browser GPS or manual pincode entry)
    last_known_lat       DECIMAL(9, 6),
    last_known_lon       DECIMAL(9, 6),
    location_city        VARCHAR(100),                  -- human-readable city name
    location_updated_at  TIMESTAMP WITH TIME ZONE,

    -- Consent and preferences
    location_consent     BOOLEAN DEFAULT FALSE,         -- GDPR-style consent flag
    sms_alerts_enabled   BOOLEAN DEFAULT TRUE,
    email_alerts_enabled BOOLEAN DEFAULT TRUE,
    alert_threshold      INTEGER DEFAULT 100,           -- AQI level to trigger alerts

    -- Nearest cached station (avoids repeated station-lookup API calls)
    nearest_station_id   VARCHAR(100),
    nearest_station_name VARCHAR(150),

    -- Account state
    active               BOOLEAN DEFAULT TRUE,
    created_at           TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at           TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for fast GPS-based lookups (n8n reads all active users per schedule)
CREATE INDEX IF NOT EXISTS idx_users_active ON users (active);
CREATE INDEX IF NOT EXISTS idx_users_phone ON users (phone);
CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);


-- ──────────────────────────────────────────────────────────────
-- TABLE: aqi_readings
-- Raw AQI readings cached from OpenAQ / OWM per user location
-- Keeps a rolling 7-day window per location
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS aqi_readings (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id       UUID REFERENCES users(id) ON DELETE CASCADE,
    lat           DECIMAL(9, 6) NOT NULL,
    lon           DECIMAL(9, 6) NOT NULL,

    -- Pollutant readings (µg/m³)
    pm25          DECIMAL(8, 2),
    pm10          DECIMAL(8, 2),
    no2           DECIMAL(8, 2),
    o3            DECIMAL(8, 2),
    co            DECIMAL(8, 2),
    aqi           DECIMAL(6, 1) NOT NULL,

    -- Meteorological data
    temperature   DECIMAL(5, 2),
    humidity      DECIMAL(5, 2),
    wind_speed    DECIMAL(5, 2),

    data_source   VARCHAR(30) DEFAULT 'openaq',        -- 'openaq', 'owm', 'synthetic'
    recorded_at   TIMESTAMP WITH TIME ZONE NOT NULL,
    fetched_at    TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_aqi_readings_user ON aqi_readings (user_id, recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_aqi_readings_lat_lon ON aqi_readings (lat, lon, recorded_at DESC);


-- ──────────────────────────────────────────────────────────────
-- TABLE: predictions
-- LSTM model predictions per user per run
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS predictions (
    id                     UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id                UUID REFERENCES users(id) ON DELETE CASCADE,

    -- Raw model output
    predicted_aqi_raw      DECIMAL(6, 1) NOT NULL,
    predicted_aqi_adjusted DECIMAL(6, 1) NOT NULL,   -- p90 + RMSE safety buffer
    rmse_buffer            DECIMAL(5, 2),
    prediction_confidence  DECIMAL(6, 3),              -- std dev of MC Dropout passes

    -- Provenance and trust
    prediction_source      VARCHAR(30) NOT NULL,       -- 'openaq', 'owm', 'interpolated', 'historical_fallback'
    alert_tier             VARCHAR(20) NOT NULL,       -- 'good', 'satisfactory', 'moderate', 'poor', 'very_poor', 'severe'
    model_rmse_at_time     DECIMAL(6, 2),              -- snapshot of model RMSE when prediction was made

    -- Forecast window
    predicted_at           TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    forecast_for           TIMESTAMP WITH TIME ZONE NOT NULL,  -- the future time this predicts

    -- GPS at time of prediction
    lat                    DECIMAL(9, 6),
    lon                    DECIMAL(9, 6)
);

CREATE INDEX IF NOT EXISTS idx_predictions_user ON predictions (user_id, predicted_at DESC);
CREATE INDEX IF NOT EXISTS idx_predictions_tier ON predictions (alert_tier, predicted_at DESC);


-- ──────────────────────────────────────────────────────────────
-- TABLE: alerts_log
-- Every dispatched notification (SMS/Email) with rate-limit tracking
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS alerts_log (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID REFERENCES users(id) ON DELETE CASCADE,
    prediction_id   UUID REFERENCES predictions(id) ON DELETE SET NULL,

    alert_tier      VARCHAR(20) NOT NULL,
    channel         VARCHAR(10) NOT NULL,             -- 'sms', 'email'
    status          VARCHAR(20) DEFAULT 'sent',       -- 'sent', 'failed', 'suppressed'
    suppressed_reason VARCHAR(100),                   -- why alert was rate-limited (if suppressed)

    -- Message content snapshot
    alert_message   TEXT,
    precautions     TEXT,                              -- JSON array stored as text

    -- Delivery metadata
    provider_id     VARCHAR(200),                     -- Twilio SID or SendGrid message ID
    sent_at         TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_alerts_user_sent ON alerts_log (user_id, sent_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_tier ON alerts_log (alert_tier, sent_at DESC);

-- View: last alert sent per user per channel (for rate limiting in n8n)
CREATE OR REPLACE VIEW last_alert_per_user AS
SELECT DISTINCT ON (user_id, channel)
    user_id,
    channel,
    alert_tier,
    sent_at
FROM alerts_log
WHERE status = 'sent'
ORDER BY user_id, channel, sent_at DESC;


-- ──────────────────────────────────────────────────────────────
-- TABLE: model_versions
-- Tracks each training run for model governance / audit
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS model_versions (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    version_tag    VARCHAR(50),                        -- e.g. 'v1.0.0', 'v1.1.0'
    rmse           DECIMAL(7, 4),
    r2             DECIMAL(7, 4),
    mae            DECIMAL(7, 4),
    n_samples      INTEGER,
    training_hours DECIMAL(5, 2),
    notes          TEXT,
    trained_at     TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_active      BOOLEAN DEFAULT TRUE
);


-- ──────────────────────────────────────────────────────────────
-- ROW LEVEL SECURITY (Supabase-specific)
-- Users can only read their own data
-- ──────────────────────────────────────────────────────────────
ALTER TABLE users        ENABLE ROW LEVEL SECURITY;
ALTER TABLE aqi_readings ENABLE ROW LEVEL SECURITY;
ALTER TABLE predictions  ENABLE ROW LEVEL SECURITY;
ALTER TABLE alerts_log   ENABLE ROW LEVEL SECURITY;

-- Service role (backend) bypasses RLS — only anon/public is restricted
-- These policies allow the backend (service_role key) full access
-- while blocking direct public API access to raw patient data

CREATE POLICY "Service role full access - users"
    ON users FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Service role full access - aqi_readings"
    ON aqi_readings FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Service role full access - predictions"
    ON predictions FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Service role full access - alerts_log"
    ON alerts_log FOR ALL USING (auth.role() = 'service_role');


-- ──────────────────────────────────────────────────────────────
-- AUTO-UPDATE updated_at on users table
-- ──────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();


-- ──────────────────────────────────────────────────────────────
-- SEED: Insert a test user for local development
-- (Delete before production!)
-- ──────────────────────────────────────────────────────────────
INSERT INTO users (
    name, phone, email, condition, severity,
    last_known_lat, last_known_lon, location_city,
    location_updated_at, location_consent,
    sms_alerts_enabled, email_alerts_enabled,
    alert_threshold, active
) VALUES (
    'Test Patient', '+919999999999', 'test@example.com',
    'COPD', 'moderate',
    17.385044, 78.486671, 'Hyderabad',
    NOW(), TRUE,
    TRUE, TRUE,
    100, TRUE
) ON CONFLICT DO NOTHING;
