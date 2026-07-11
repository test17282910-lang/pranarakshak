-- ══════════════════════════════════════════════════════════════════════════════
-- Migration: Add Features 3, 4, 8 Tables
-- Features: Medication Reminders, Family Groups, Emergency Contacts
-- Date: 2026-01-11
-- Run this in: Supabase Dashboard → SQL Editor
-- ══════════════════════════════════════════════════════════════════════════════

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ══════════════════════════════════════════════════════════════════════════════
-- FEATURE 3: MEDICATION REMINDERS
-- ══════════════════════════════════════════════════════════════════════════════

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

COMMENT ON TABLE medications IS 'Store user medications with AQI-based trigger thresholds';
COMMENT ON COLUMN medications.medication_type IS 'rescue_inhaler, preventer_inhaler, nebulizer, oral, other';
COMMENT ON COLUMN medications.frequency IS 'as_needed, daily, twice_daily, thrice_daily, custom';
COMMENT ON COLUMN medications.aqi_trigger IS 'AQI threshold to trigger reminder (e.g., 100)';

-- TABLE: medication_reminders (log of sent reminders)
CREATE TABLE IF NOT EXISTS medication_reminders (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    medication_id    UUID REFERENCES medications(id) ON DELETE CASCADE,
    user_id          UUID REFERENCES users(id) ON DELETE CASCADE,
    reminder_type    VARCHAR(30) NOT NULL,
    aqi_at_time      INTEGER,
    message_sent     TEXT,
    channel          VARCHAR(20) NOT NULL,
    status           VARCHAR(20) DEFAULT 'sent',
    sent_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_med_reminders_user ON medication_reminders (user_id, sent_at DESC);
CREATE INDEX IF NOT EXISTS idx_med_reminders_medication ON medication_reminders (medication_id);

COMMENT ON TABLE medication_reminders IS 'Log of all medication reminder notifications sent';
COMMENT ON COLUMN medication_reminders.reminder_type IS 'scheduled, aqi_triggered, emergency';

-- ══════════════════════════════════════════════════════════════════════════════
-- FEATURE 4: FAMILY GROUP ALERTS
-- ══════════════════════════════════════════════════════════════════════════════

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

COMMENT ON TABLE family_groups IS 'Family groups for shared health monitoring';
COMMENT ON COLUMN family_groups.emergency_mode IS 'Enable automatic emergency alerts to all members';

-- TABLE: family_group_members
CREATE TABLE IF NOT EXISTS family_group_members (
    id                     UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    group_id               UUID REFERENCES family_groups(id) ON DELETE CASCADE,
    user_id                UUID REFERENCES users(id) ON DELETE CASCADE,
    role                   VARCHAR(30) DEFAULT 'member',
    joined_at              TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    notifications_enabled  BOOLEAN DEFAULT TRUE,
    emergency_priority     INTEGER DEFAULT 3
);

CREATE INDEX IF NOT EXISTS idx_family_members_group ON family_group_members (group_id);
CREATE INDEX IF NOT EXISTS idx_family_members_user ON family_group_members (user_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_family_members_unique ON family_group_members (group_id, user_id);

COMMENT ON TABLE family_group_members IS 'Many-to-many relationship: users in family groups';
COMMENT ON COLUMN family_group_members.role IS 'admin, member, guardian';

-- TABLE: family_alerts (log of family group notifications)
CREATE TABLE IF NOT EXISTS family_alerts (
    id                 UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    group_id           UUID REFERENCES family_groups(id) ON DELETE CASCADE,
    triggered_by_user  UUID REFERENCES users(id) ON DELETE CASCADE,
    alert_type         VARCHAR(30) NOT NULL,
    message            TEXT,
    aqi_value          INTEGER,
    location_lat       DECIMAL(9, 6),
    location_lon       DECIMAL(9, 6),
    members_notified   INTEGER DEFAULT 0,
    sent_at            TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_family_alerts_group ON family_alerts (group_id, sent_at DESC);
CREATE INDEX IF NOT EXISTS idx_family_alerts_user ON family_alerts (triggered_by_user);

COMMENT ON TABLE family_alerts IS 'Log of all family group notifications sent';
COMMENT ON COLUMN family_alerts.alert_type IS 'critical_aqi, high_aqi, emergency_contact, location_update';

-- ══════════════════════════════════════════════════════════════════════════════
-- FEATURE 8: EMERGENCY CONTACT AUTO-ALERT
-- ══════════════════════════════════════════════════════════════════════════════

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

COMMENT ON TABLE emergency_contacts IS 'Emergency contacts for critical AQI auto-alerts';
COMMENT ON COLUMN emergency_contacts.relationship IS 'spouse, parent, child, sibling, friend, doctor, caregiver';
COMMENT ON COLUMN emergency_contacts.priority IS '1=highest priority, 5=lowest priority';

-- ══════════════════════════════════════════════════════════════════════════════
-- ROW LEVEL SECURITY (RLS)
-- ══════════════════════════════════════════════════════════════════════════════

-- Enable RLS on all new tables
ALTER TABLE medications ENABLE ROW LEVEL SECURITY;
ALTER TABLE medication_reminders ENABLE ROW LEVEL SECURITY;
ALTER TABLE family_groups ENABLE ROW LEVEL SECURITY;
ALTER TABLE family_group_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE family_alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE emergency_contacts ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if they exist (for re-running migration)
DROP POLICY IF EXISTS "service_role_all_medications" ON medications;
DROP POLICY IF EXISTS "service_role_all_medication_reminders" ON medication_reminders;
DROP POLICY IF EXISTS "service_role_all_family_groups" ON family_groups;
DROP POLICY IF EXISTS "service_role_all_family_members" ON family_group_members;
DROP POLICY IF EXISTS "service_role_all_family_alerts" ON family_alerts;
DROP POLICY IF EXISTS "service_role_all_emergency_contacts" ON emergency_contacts;

DROP POLICY IF EXISTS "users_read_own_medications" ON medications;
DROP POLICY IF EXISTS "users_read_own_medication_reminders" ON medication_reminders;
DROP POLICY IF EXISTS "users_read_family_groups" ON family_groups;
DROP POLICY IF EXISTS "users_read_family_members" ON family_group_members;
DROP POLICY IF EXISTS "users_read_family_alerts" ON family_alerts;
DROP POLICY IF EXISTS "users_read_own_emergency_contacts" ON emergency_contacts;

-- Service role: full access (backend uses service_role key — bypasses RLS)
CREATE POLICY "service_role_all_medications" ON medications FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "service_role_all_medication_reminders" ON medication_reminders FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "service_role_all_family_groups" ON family_groups FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "service_role_all_family_members" ON family_group_members FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "service_role_all_family_alerts" ON family_alerts FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "service_role_all_emergency_contacts" ON emergency_contacts FOR ALL USING (auth.role() = 'service_role');

-- User policies (read their own data)
CREATE POLICY "users_read_own_medications" ON medications FOR SELECT USING (
    user_id IN (SELECT id FROM users WHERE auth_user_id IS NOT NULL AND auth_user_id = auth.uid())
);

CREATE POLICY "users_read_own_medication_reminders" ON medication_reminders FOR SELECT USING (
    user_id IN (SELECT id FROM users WHERE auth_user_id IS NOT NULL AND auth_user_id = auth.uid())
);

CREATE POLICY "users_read_family_groups" ON family_groups FOR SELECT USING (
    id IN (SELECT group_id FROM family_group_members WHERE user_id IN (
        SELECT id FROM users WHERE auth_user_id IS NOT NULL AND auth_user_id = auth.uid()
    ))
);

CREATE POLICY "users_read_family_members" ON family_group_members FOR SELECT USING (
    user_id IN (SELECT id FROM users WHERE auth_user_id IS NOT NULL AND auth_user_id = auth.uid())
    OR group_id IN (SELECT group_id FROM family_group_members WHERE user_id IN (
        SELECT id FROM users WHERE auth_user_id IS NOT NULL AND auth_user_id = auth.uid()
    ))
);

CREATE POLICY "users_read_family_alerts" ON family_alerts FOR SELECT USING (
    group_id IN (SELECT group_id FROM family_group_members WHERE user_id IN (
        SELECT id FROM users WHERE auth_user_id IS NOT NULL AND auth_user_id = auth.uid()
    ))
);

CREATE POLICY "users_read_own_emergency_contacts" ON emergency_contacts FOR SELECT USING (
    user_id IN (SELECT id FROM users WHERE auth_user_id IS NOT NULL AND auth_user_id = auth.uid())
);

-- ══════════════════════════════════════════════════════════════════════════════
-- TRIGGERS FOR AUTOMATIC TIMESTAMP UPDATES
-- ══════════════════════════════════════════════════════════════════════════════

-- Create trigger function if it doesn't exist
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Add triggers to new tables
DROP TRIGGER IF EXISTS medications_updated_at ON medications;
DROP TRIGGER IF EXISTS family_groups_updated_at ON family_groups;
DROP TRIGGER IF EXISTS emergency_contacts_updated_at ON emergency_contacts;

CREATE TRIGGER medications_updated_at
    BEFORE UPDATE ON medications
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER family_groups_updated_at
    BEFORE UPDATE ON family_groups
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER emergency_contacts_updated_at
    BEFORE UPDATE ON emergency_contacts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ══════════════════════════════════════════════════════════════════════════════
-- VERIFICATION QUERIES (Run these to verify tables were created)
-- ══════════════════════════════════════════════════════════════════════════════

-- Check if all tables exist
SELECT 
    'medications' as table_name, 
    COUNT(*) as row_count 
FROM medications
UNION ALL
SELECT 'medication_reminders', COUNT(*) FROM medication_reminders
UNION ALL
SELECT 'family_groups', COUNT(*) FROM family_groups
UNION ALL
SELECT 'family_group_members', COUNT(*) FROM family_group_members
UNION ALL
SELECT 'family_alerts', COUNT(*) FROM family_alerts
UNION ALL
SELECT 'emergency_contacts', COUNT(*) FROM emergency_contacts;

-- ══════════════════════════════════════════════════════════════════════════════
-- MIGRATION COMPLETE ✅
-- ══════════════════════════════════════════════════════════════════════════════

-- Next steps:
-- 1. Verify all 6 tables were created successfully
-- 2. Check RLS policies are in place
-- 3. Deploy backend to Railway (should auto-deploy from GitHub)
-- 4. Test API endpoints at: https://your-backend.railway.app/docs
-- 5. Build frontend UI for medication/family/emergency management

SELECT 'Migration 001_add_features_3_4_8 completed successfully! ✅' as status;
