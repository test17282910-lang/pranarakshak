-- ============================================================
-- AQI Health Alert System — Supabase PostgreSQL Schema
-- Safe to re-run on an existing database.
-- Run in: Supabase Dashboard → SQL Editor → New Query
-- ============================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";


-- ══════════════════════════════════════════════════════════════
-- MIGRATE existing `users` table — add new columns if missing
-- These ALTER TABLE statements are safe to run even if the
-- columns already exist (DO $$ blocks catch the duplicate error).
-- ══════════════════════════════════════════════════════════════
DO $$
BEGIN
    -- auth_user_id: link to Supabase auth (NULL for password-only users)
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name   = 'users'
          AND column_name  = 'auth_user_id'
    ) THEN
        ALTER TABLE public.users
            ADD COLUMN auth_user_id UUID UNIQUE REFERENCES auth.users(id) ON DELETE SET NULL;
    END IF;

    -- password_hash: bcrypt hash, NULL for users not yet migrated
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name   = 'users'
          AND column_name  = 'password_hash'
    ) THEN
        ALTER TABLE public.users ADD COLUMN password_hash TEXT;
    END IF;

    -- location_city: human-readable city name
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name   = 'users'
          AND column_name  = 'location_city'
    ) THEN
        ALTER TABLE public.users ADD COLUMN location_city VARCHAR(100);
    END IF;

    -- severity
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name   = 'users'
          AND column_name  = 'severity'
    ) THEN
        ALTER TABLE public.users ADD COLUMN severity VARCHAR(20) DEFAULT 'moderate';
    END IF;

    -- symptoms
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name   = 'users'
          AND column_name  = 'symptoms'
    ) THEN
        ALTER TABLE public.users ADD COLUMN symptoms VARCHAR(50)[] DEFAULT '{}';
    END IF;

    -- personalized_issue
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name   = 'users'
          AND column_name  = 'personalized_issue'
    ) THEN
        ALTER TABLE public.users ADD COLUMN personalized_issue TEXT;
    END IF;

    -- sms_alerts_enabled
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name   = 'users'
          AND column_name  = 'sms_alerts_enabled'
    ) THEN
        ALTER TABLE public.users ADD COLUMN sms_alerts_enabled BOOLEAN DEFAULT TRUE;
    END IF;

    -- email_alerts_enabled
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name   = 'users'
          AND column_name  = 'email_alerts_enabled'
    ) THEN
        ALTER TABLE public.users ADD COLUMN email_alerts_enabled BOOLEAN DEFAULT TRUE;
    END IF;

    -- alert_threshold
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name   = 'users'
          AND column_name  = 'alert_threshold'
    ) THEN
        ALTER TABLE public.users ADD COLUMN alert_threshold INTEGER DEFAULT 100;
    END IF;

    -- nearest_station_id
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name   = 'users'
          AND column_name  = 'nearest_station_id'
    ) THEN
        ALTER TABLE public.users ADD COLUMN nearest_station_id VARCHAR(100);
    END IF;

    -- nearest_station_name
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name   = 'users'
          AND column_name  = 'nearest_station_name'
    ) THEN
        ALTER TABLE public.users ADD COLUMN nearest_station_name VARCHAR(150);
    END IF;

    -- updated_at
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name   = 'users'
          AND column_name  = 'updated_at'
    ) THEN
        ALTER TABLE public.users
            ADD COLUMN updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
    END IF;
END $$;

-- Add index on auth_user_id if it doesn't exist yet
CREATE INDEX IF NOT EXISTS idx_users_auth_user_id ON users (auth_user_id);


-- ══════════════════════════════════════════════════════════════
-- MIGRATE existing `predictions` table — add air_quality_tier
-- ══════════════════════════════════════════════════════════════
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name   = 'predictions'
          AND column_name  = 'air_quality_tier'
    ) THEN
        ALTER TABLE public.predictions ADD COLUMN air_quality_tier VARCHAR(30);
    END IF;
END $$;


-- ══════════════════════════════════════════════════════════════
-- TABLE: profiles
-- Linked 1:1 with Supabase auth.users via auth.uid()
-- ══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS profiles (
    id                   UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    display_name         VARCHAR(100),
    phone                VARCHAR(20) UNIQUE,
    avatar_url           TEXT,
    auth_provider        VARCHAR(30) DEFAULT 'email',
    onboarding_complete  BOOLEAN DEFAULT FALSE,
    active               BOOLEAN DEFAULT TRUE,
    created_at           TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at           TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_profiles_phone  ON profiles (phone);
CREATE INDEX IF NOT EXISTS idx_profiles_active ON profiles (active);


-- ══════════════════════════════════════════════════════════════
-- TABLE: users  (full definition — only created if not exists)
-- ══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS users (
    id                   UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    auth_user_id         UUID UNIQUE REFERENCES auth.users(id) ON DELETE SET NULL,
    name                 VARCHAR(100) NOT NULL,
    phone                VARCHAR(20) UNIQUE,
    email                VARCHAR(150) UNIQUE,
    password_hash        TEXT,
    condition            VARCHAR(50) NOT NULL,
    severity             VARCHAR(20) DEFAULT 'moderate',
    symptoms             VARCHAR(50)[] DEFAULT '{}',
    personalized_issue   TEXT,
    last_known_lat       DECIMAL(9, 6),
    last_known_lon       DECIMAL(9, 6),
    location_city        VARCHAR(100),
    location_updated_at  TIMESTAMP WITH TIME ZONE,
    location_consent     BOOLEAN DEFAULT FALSE,
    sms_alerts_enabled   BOOLEAN DEFAULT TRUE,
    email_alerts_enabled BOOLEAN DEFAULT TRUE,
    alert_threshold      INTEGER DEFAULT 100,
    nearest_station_id   VARCHAR(100),
    nearest_station_name VARCHAR(150),
    active               BOOLEAN DEFAULT TRUE,
    created_at           TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at           TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_active ON users (active);
CREATE INDEX IF NOT EXISTS idx_users_phone  ON users (phone);
CREATE INDEX IF NOT EXISTS idx_users_email  ON users (email);


-- ══════════════════════════════════════════════════════════════
-- TABLE: aqi_readings
-- ══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS aqi_readings (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID REFERENCES users(id) ON DELETE CASCADE,
    lat         DECIMAL(9, 6) NOT NULL,
    lon         DECIMAL(9, 6) NOT NULL,
    pm25        DECIMAL(8, 2),
    pm10        DECIMAL(8, 2),
    no2         DECIMAL(8, 2),
    o3          DECIMAL(8, 2),
    co          DECIMAL(8, 2),
    aqi         DECIMAL(6, 1) NOT NULL,
    temperature DECIMAL(5, 2),
    humidity    DECIMAL(5, 2),
    wind_speed  DECIMAL(5, 2),
    data_source VARCHAR(30) DEFAULT 'openaq',
    recorded_at TIMESTAMP WITH TIME ZONE NOT NULL,
    fetched_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_aqi_readings_user     ON aqi_readings (user_id, recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_aqi_readings_lat_lon  ON aqi_readings (lat, lon, recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_aqi_readings_recorded ON aqi_readings (recorded_at DESC);


-- ══════════════════════════════════════════════════════════════
-- TABLE: predictions
-- ══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS predictions (
    id                     UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id                UUID REFERENCES users(id) ON DELETE CASCADE,
    predicted_aqi_raw      DECIMAL(6, 1) NOT NULL,
    predicted_aqi_adjusted DECIMAL(6, 1) NOT NULL,
    rmse_buffer            DECIMAL(5, 2),
    prediction_confidence  DECIMAL(6, 3),
    prediction_source      VARCHAR(30) NOT NULL,
    alert_tier             VARCHAR(20) NOT NULL,
    air_quality_tier       VARCHAR(30),
    model_rmse_at_time     DECIMAL(6, 2),
    predicted_at           TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    forecast_for           TIMESTAMP WITH TIME ZONE NOT NULL,
    lat                    DECIMAL(9, 6),
    lon                    DECIMAL(9, 6)
);

CREATE INDEX IF NOT EXISTS idx_predictions_user ON predictions (user_id, predicted_at DESC);
CREATE INDEX IF NOT EXISTS idx_predictions_tier ON predictions (alert_tier, predicted_at DESC);


-- ══════════════════════════════════════════════════════════════
-- TABLE: alerts_log
-- ══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS alerts_log (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id           UUID REFERENCES users(id) ON DELETE CASCADE,
    prediction_id     UUID REFERENCES predictions(id) ON DELETE SET NULL,
    alert_tier        VARCHAR(20) NOT NULL,
    channel           VARCHAR(10) NOT NULL,
    status            VARCHAR(20) DEFAULT 'sent',
    suppressed_reason VARCHAR(100),
    alert_message     TEXT,
    precautions       TEXT,
    provider_id       VARCHAR(200),
    sent_at           TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_alerts_user_sent ON alerts_log (user_id, sent_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_tier      ON alerts_log (alert_tier, sent_at DESC);


-- View: last alert per user per channel (rate-limit helper for worker)
-- SECURITY INVOKER ensures the view respects the calling user's RLS policies,
-- not the view creator's permissions.
CREATE OR REPLACE VIEW last_alert_per_user
    WITH (security_invoker = true)
AS
SELECT DISTINCT ON (user_id, channel)
    user_id, channel, alert_tier, sent_at
FROM alerts_log
WHERE status = 'sent'
ORDER BY user_id, channel, sent_at DESC;


-- ══════════════════════════════════════════════════════════════
-- TABLE: model_versions
-- ══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS model_versions (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    version_tag    VARCHAR(50),
    rmse           DECIMAL(7, 4),
    r2             DECIMAL(7, 4),
    mae            DECIMAL(7, 4),
    n_samples      INTEGER,
    training_hours DECIMAL(5, 2),
    notes          TEXT,
    trained_at     TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_active      BOOLEAN DEFAULT TRUE
);


-- ══════════════════════════════════════════════════════════════
-- TABLE: password_reset_tokens
-- ══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT (NOW() + INTERVAL '1 hour'),
    used       BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reset_tokens_user    ON password_reset_tokens (user_id);
CREATE INDEX IF NOT EXISTS idx_reset_tokens_hash    ON password_reset_tokens (token_hash);
CREATE INDEX IF NOT EXISTS idx_reset_tokens_expires ON password_reset_tokens (expires_at);


-- ══════════════════════════════════════════════════════════════
-- TABLE: login_audit
-- ══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS login_audit (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    identifier   VARCHAR(200),
    user_id      UUID REFERENCES users(id) ON DELETE SET NULL,
    success      BOOLEAN NOT NULL,
    ip_address   INET,
    user_agent   TEXT,
    provider     VARCHAR(20) DEFAULT 'email',
    attempted_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_login_audit_identifier ON login_audit (identifier, attempted_at DESC);
CREATE INDEX IF NOT EXISTS idx_login_audit_user       ON login_audit (user_id, attempted_at DESC);
CREATE INDEX IF NOT EXISTS idx_login_audit_success    ON login_audit (success, attempted_at DESC);


-- ══════════════════════════════════════════════════════════════
-- ROW LEVEL SECURITY
-- Drop old policies first so re-runs don't fail on duplicates,
-- then recreate them cleanly.
-- ══════════════════════════════════════════════════════════════
ALTER TABLE profiles              ENABLE ROW LEVEL SECURITY;
ALTER TABLE users                 ENABLE ROW LEVEL SECURITY;
ALTER TABLE aqi_readings          ENABLE ROW LEVEL SECURITY;
ALTER TABLE predictions           ENABLE ROW LEVEL SECURITY;
ALTER TABLE alerts_log            ENABLE ROW LEVEL SECURITY;
ALTER TABLE password_reset_tokens ENABLE ROW LEVEL SECURITY;
ALTER TABLE login_audit           ENABLE ROW LEVEL SECURITY;

-- Drop all existing policies so this script is idempotent
DO $$ DECLARE r RECORD;
BEGIN
    FOR r IN SELECT policyname, tablename
             FROM pg_policies
             WHERE schemaname = 'public'
    LOOP
        EXECUTE format('DROP POLICY IF EXISTS %I ON %I', r.policyname, r.tablename);
    END LOOP;
END $$;

-- Service role: full access (backend uses service_role key — bypasses RLS)
CREATE POLICY "service_role_all_profiles"
    ON profiles FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "service_role_all_users"
    ON users FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "service_role_all_aqi_readings"
    ON aqi_readings FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "service_role_all_predictions"
    ON predictions FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "service_role_all_alerts"
    ON alerts_log FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "service_role_all_reset_tokens"
    ON password_reset_tokens FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "service_role_all_login_audit"
    ON login_audit FOR ALL USING (auth.role() = 'service_role');

-- Authenticated users: read/update only their own profile
CREATE POLICY "users_read_own_profile"
    ON profiles FOR SELECT USING (auth.uid() = id);

CREATE POLICY "users_update_own_profile"
    ON profiles FOR UPDATE USING (auth.uid() = id);

-- Authenticated users: read their own health row
-- auth_user_id is now guaranteed to exist (added by migration above)
CREATE POLICY "users_read_own_users_row"
    ON users FOR SELECT
    USING (auth_user_id IS NOT NULL AND auth.uid() = auth_user_id);

CREATE POLICY "users_read_own_aqi_readings"
    ON aqi_readings FOR SELECT USING (
        user_id IN (
            SELECT id FROM users
            WHERE auth_user_id IS NOT NULL
              AND auth_user_id = auth.uid()
        )
    );

CREATE POLICY "users_read_own_predictions"
    ON predictions FOR SELECT USING (
        user_id IN (
            SELECT id FROM users
            WHERE auth_user_id IS NOT NULL
              AND auth_user_id = auth.uid()
        )
    );

CREATE POLICY "users_read_own_alerts"
    ON alerts_log FOR SELECT USING (
        user_id IN (
            SELECT id FROM users
            WHERE auth_user_id IS NOT NULL
              AND auth_user_id = auth.uid()
        )
    );


-- ══════════════════════════════════════════════════════════════
-- TRIGGERS
-- ══════════════════════════════════════════════════════════════

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS users_updated_at    ON users;
DROP TRIGGER IF EXISTS profiles_updated_at ON profiles;

CREATE TRIGGER users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER profiles_updated_at
    BEFORE UPDATE ON profiles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();


-- ══════════════════════════════════════════════════════════════
-- HELPER FUNCTIONS
-- ══════════════════════════════════════════════════════════════

-- Purge expired password reset tokens (run daily via pg_cron or n8n)
CREATE OR REPLACE FUNCTION purge_expired_reset_tokens()
RETURNS INTEGER AS $$
DECLARE deleted_count INTEGER;
BEGIN
    DELETE FROM password_reset_tokens WHERE expires_at < NOW() OR used = TRUE;
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;


-- ══════════════════════════════════════════════════════════════
-- NEW FEATURE TABLES: Medication Reminders, Family Groups, Emergency Contacts
-- ══════════════════════════════════════════════════════════════

-- TABLE: medications
CREATE TABLE IF NOT EXISTS medications (
    id                   UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id              UUID REFERENCES users(id) ON DELETE CASCADE,
    medication_name      VARCHAR(200) NOT NULL,
    medication_type      VARCHAR(50) NOT NULL,
    dosage               VARCHAR(100) NOT NULL,
    frequency            VARCHAR(30) NOT NULL,
    custom_schedule      VARCHAR(20)[] DEFAULT '{}',
    aqi_trigger          INTEGER,
    condition_specific   BOOLEAN DEFAULT TRUE,
    active               BOOLEAN DEFAULT TRUE,
    created_at           TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at           TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_medications_user ON medications (user_id, active);
CREATE INDEX IF NOT EXISTS idx_medications_aqi_trigger ON medications (aqi_trigger);

-- TABLE: family_groups  
CREATE TABLE IF NOT EXISTS family_groups (
    id                     UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    group_name             VARCHAR(100) NOT NULL,
    creator_user_id        UUID REFERENCES users(id) ON DELETE CASCADE,
    description            TEXT,
    shared_alert_threshold INTEGER DEFAULT 100,
    auto_share_location    BOOLEAN DEFAULT TRUE,
    emergency_mode         BOOLEAN DEFAULT TRUE,
    active                 BOOLEAN DEFAULT TRUE,
    created_at             TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at             TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_family_groups_creator ON family_groups (creator_user_id);
CREATE INDEX IF NOT EXISTS idx_family_groups_active ON family_groups (active);

-- TABLE: family_group_members
CREATE TABLE IF NOT EXISTS family_group_members (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    group_id         UUID REFERENCES family_groups(id) ON DELETE CASCADE,
    user_id          UUID REFERENCES users(id) ON DELETE CASCADE,
    role             VARCHAR(30) DEFAULT 'member', -- 'admin', 'member', 'guardian'
    joined_at        TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    notifications_enabled BOOLEAN DEFAULT TRUE,
    emergency_priority INTEGER DEFAULT 3
);

CREATE INDEX IF NOT EXISTS idx_family_members_group ON family_group_members (group_id);
CREATE INDEX IF NOT EXISTS idx_family_members_user ON family_group_members (user_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_family_members_unique ON family_group_members (group_id, user_id);

-- TABLE: emergency_contacts
CREATE TABLE IF NOT EXISTS emergency_contacts (
    id                       UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id                  UUID REFERENCES users(id) ON DELETE CASCADE,
    contact_name             VARCHAR(100) NOT NULL,
    relationship             VARCHAR(30) NOT NULL,
    phone                    VARCHAR(20),
    email                    VARCHAR(150),
    priority                 INTEGER DEFAULT 1,
    notify_on_critical       BOOLEAN DEFAULT TRUE,
    notify_on_missed_checkin BOOLEAN DEFAULT FALSE,
    active                   BOOLEAN DEFAULT TRUE,
    created_at               TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at               TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_emergency_contacts_user ON emergency_contacts (user_id, priority);
CREATE INDEX IF NOT EXISTS idx_emergency_contacts_active ON emergency_contacts (active);

-- TABLE: medication_reminders (log of sent reminders)
CREATE TABLE IF NOT EXISTS medication_reminders (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    medication_id    UUID REFERENCES medications(id) ON DELETE CASCADE,
    user_id          UUID REFERENCES users(id) ON DELETE CASCADE,
    reminder_type    VARCHAR(30) NOT NULL, -- 'scheduled', 'aqi_triggered', 'emergency'
    aqi_at_time      INTEGER,
    message_sent     TEXT,
    channel          VARCHAR(20) NOT NULL, -- 'whatsapp', 'sms', 'email'
    status           VARCHAR(20) DEFAULT 'sent',
    sent_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_med_reminders_user ON medication_reminders (user_id, sent_at DESC);
CREATE INDEX IF NOT EXISTS idx_med_reminders_medication ON medication_reminders (medication_id);

-- TABLE: family_alerts (log of family group notifications)
CREATE TABLE IF NOT EXISTS family_alerts (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    group_id         UUID REFERENCES family_groups(id) ON DELETE CASCADE,
    triggered_by_user UUID REFERENCES users(id) ON DELETE CASCADE,
    alert_type       VARCHAR(30) NOT NULL, -- 'critical_aqi', 'emergency_contact', 'location_update'
    message          TEXT,
    aqi_value        INTEGER,
    location_lat     DECIMAL(9, 6),
    location_lon     DECIMAL(9, 6),
    members_notified INTEGER DEFAULT 0,
    sent_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_family_alerts_group ON family_alerts (group_id, sent_at DESC);
CREATE INDEX IF NOT EXISTS idx_family_alerts_user ON family_alerts (triggered_by_user);

-- Add RLS for new tables
ALTER TABLE medications ENABLE ROW LEVEL SECURITY;
ALTER TABLE family_groups ENABLE ROW LEVEL SECURITY;
ALTER TABLE family_group_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE emergency_contacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE medication_reminders ENABLE ROW LEVEL SECURITY;
ALTER TABLE family_alerts ENABLE ROW LEVEL SECURITY;

-- Service role policies
CREATE POLICY "service_role_all_medications" ON medications FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "service_role_all_family_groups" ON family_groups FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "service_role_all_family_members" ON family_group_members FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "service_role_all_emergency_contacts" ON emergency_contacts FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "service_role_all_medication_reminders" ON medication_reminders FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "service_role_all_family_alerts" ON family_alerts FOR ALL USING (auth.role() = 'service_role');

-- User policies (read their own data)
CREATE POLICY "users_read_own_medications" ON medications FOR SELECT USING (
    user_id IN (SELECT id FROM users WHERE auth_user_id IS NOT NULL AND auth_user_id = auth.uid())
);

CREATE POLICY "users_read_own_emergency_contacts" ON emergency_contacts FOR SELECT USING (
    user_id IN (SELECT id FROM users WHERE auth_user_id IS NOT NULL AND auth_user_id = auth.uid())
);

CREATE POLICY "users_read_family_groups" ON family_groups FOR SELECT USING (
    id IN (SELECT group_id FROM family_group_members WHERE user_id IN (
        SELECT id FROM users WHERE auth_user_id IS NOT NULL AND auth_user_id = auth.uid()
    ))
);


-- ══════════════════════════════════════════════════════════════
-- SEED: test user for local development — remove before go-live
-- ══════════════════════════════════════════════════════════════
INSERT INTO users (
    name, phone, email, password_hash,
    condition, severity,
    last_known_lat, last_known_lon, location_city,
    location_updated_at, location_consent,
    sms_alerts_enabled, email_alerts_enabled,
    alert_threshold, active
) VALUES (
    'Test Patient',
    '+919999999999',
    'test@example.com',
    crypt('TestPass123!', gen_salt('bf', 12)),
    'COPD', 'moderate',
    17.385044, 78.486671, 'Hyderabad',
    NOW(), TRUE,
    TRUE, TRUE, 100, TRUE
) ON CONFLICT DO NOTHING;
