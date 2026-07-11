"""
db.py — Supabase Database Client
Centralised database access layer for the AQI Health Alert System.
Uses the Supabase Python SDK (supabase-py) with the service_role key
so it bypasses Row Level Security — never expose this key to the frontend.

Usage:
    from db import db
    users = db.get_active_users()
    db.save_prediction(user_id, prediction_data)
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")  # Never expose publicly


# ─── Supabase Client ──────────────────────────────────────────────────────────

def _get_client():
    """Lazily initialise the Supabase client (avoids import-time failures)."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in environment variables."
        )
    from supabase import create_client
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


# ─── Database Access Layer ────────────────────────────────────────────────────

class Database:
    """
    Thin abstraction over Supabase client.
    All methods are synchronous — wrap in asyncio.to_thread() for async FastAPI routes.
    """

    def __init__(self):
        self._client = None

    @property
    def client(self):
        if self._client is None:
            self._client = _get_client()
        return self._client

    # ── Users ──────────────────────────────────────────────────────────────────

    def get_user_by_id(self, user_id: str) -> Optional[dict]:
        response = (
            self.client.table("users")
            .select("*")
            .eq("id", user_id)
            .maybe_single()
            .execute()
        )
        return response.data

    def get_active_users(self) -> list[dict]:
        """Return all active users with valid GPS coordinates."""
        response = (
            self.client.table("users")
            .select("*")
            .eq("active", True)
            .not_.is_("last_known_lat", "null")
            .not_.is_("last_known_lon", "null")
            .execute()
        )
        return response.data or []

    def get_user_by_phone(self, phone: str) -> Optional[dict]:
        response = (
            self.client.table("users")
            .select("*")
            .eq("phone", phone)
            .maybe_single()
            .execute()
        )
        return response.data

    def get_user_by_email(self, email: str) -> Optional[dict]:
        response = (
            self.client.table("users")
            .select("*")
            .eq("email", email)
            .maybe_single()
            .execute()
        )
        return response.data

    def create_user(self, user_data: dict) -> dict:
        """Register a new user. Returns the created user record."""
        response = self.client.table("users").insert(user_data).execute()
        return response.data[0] if response.data else {}

    def update_user_location(
        self,
        user_id: str,
        lat: float,
        lon: float,
        city: Optional[str] = None,
    ) -> None:
        """Update GPS coordinates and consent timestamp."""
        payload: dict[str, Any] = {
            "last_known_lat": lat,
            "last_known_lon": lon,
            "location_updated_at": datetime.now(timezone.utc).isoformat(),
            "location_consent": True,
        }
        if city:
            payload["location_city"] = city

        self.client.table("users").update(payload).eq("id", user_id).execute()

    # ── AQI Readings ───────────────────────────────────────────────────────────

    def save_aqi_reading(self, reading: dict) -> None:
        """Persist a single AQI reading to the cache table."""
        self.client.table("aqi_readings").insert(reading).execute()

    def get_recent_readings(
        self,
        user_id: str,
        limit: int = 48,
    ) -> list[dict]:
        """Fetch the most recent N hourly readings for a user."""
        response = (
            self.client.table("aqi_readings")
            .select("*")
            .eq("user_id", user_id)
            .order("recorded_at", desc=True)
            .limit(limit)
            .execute()
        )
        return list(reversed(response.data or []))  # chronological order

    # ── Predictions ────────────────────────────────────────────────────────────

    def save_prediction(self, prediction: dict) -> str:
        """Persist a prediction record. Returns the new prediction ID."""
        response = self.client.table("predictions").insert(prediction).execute()
        return response.data[0]["id"] if response.data else ""

    def get_latest_prediction(self, user_id: str) -> Optional[dict]:
        response = (
            self.client.table("predictions")
            .select("*")
            .eq("user_id", user_id)
            .order("predicted_at", desc=True)
            .limit(1)
            .maybe_single()
            .execute()
        )
        return response.data

    # ── Alerts Log ─────────────────────────────────────────────────────────────

    def log_alert(self, alert: dict) -> None:
        """Record a dispatched (or suppressed) alert."""
        self.client.table("alerts_log").insert(alert).execute()

    def get_last_alert_sent(
        self,
        user_id: str,
        channel: str,
    ) -> Optional[dict]:
        """
        Return the most recent successfully sent alert for a user+channel.
        Used by n8n / alert dispatch logic to enforce rate limiting.
        """
        response = (
            self.client.table("alerts_log")
            .select("sent_at, alert_tier")
            .eq("user_id", user_id)
            .eq("channel", channel)
            .eq("status", "sent")
            .order("sent_at", desc=True)
            .limit(1)
            .maybe_single()
            .execute()
        )
        return response.data if response else None

    def should_send_alert(
        self,
        user_id: str,
        channel: str,
        alert_tier: str,
        cooldown_hours: int = 6,
    ) -> tuple[bool, str]:
        """
        Rate-limiting gate.
        - Severe alerts: always send (no rate limit).
        - Other tiers: suppress if last alert was within cooldown_hours.

        Returns (should_send: bool, reason: str)
        """
        if alert_tier == "severe":
            return True, "severe_always_send"

        last = self.get_last_alert_sent(user_id, channel)
        if last is None:
            return True, "first_alert"

        from datetime import timedelta
        last_sent = datetime.fromisoformat(last["sent_at"])
        if last_sent.tzinfo is None:
            last_sent = last_sent.replace(tzinfo=timezone.utc)

        elapsed = datetime.now(timezone.utc) - last_sent
        if elapsed < timedelta(hours=cooldown_hours):
            remaining = cooldown_hours - (elapsed.total_seconds() / 3600)
            return False, f"rate_limited_{remaining:.1f}h_remaining"

        return True, "cooldown_expired"

    def get_user_alerts_log(self, user_id: str, limit: int = 20) -> list[dict]:
        """Fetch historical alert notifications sent to a user."""
        response = (
            self.client.table("alerts_log")
            .select("*")
            .eq("user_id", user_id)
            .order("sent_at", desc=True)
            .limit(limit)
            .execute()
        )
        return response.data or []

    # ── Model Versions ─────────────────────────────────────────────────────────

    def save_model_version(self, metadata: dict) -> None:
        """Record a training run in model_versions for audit/governance."""
        # Deactivate previous active version
        self.client.table("model_versions").update({"is_active": False}).eq(
            "is_active", True
        ).execute()

        self.client.table("model_versions").insert({
            "rmse": metadata.get("rmse"),
            "r2": metadata.get("r2"),
            "mae": metadata.get("mae"),
            "n_samples": metadata.get("n_samples_train"),
            "trained_at": metadata.get("trained_at"),
            "is_active": True,
        }).execute()

    # ═══════════════════════════════════════════════════════════════════════════
    # NEW FEATURES: Medications, Family Groups, Emergency Contacts
    # ═══════════════════════════════════════════════════════════════════════════

    # ── Medications ────────────────────────────────────────────────────────────

    def add_medication(
        self,
        user_id: str,
        medication_name: str,
        medication_type: str,
        dosage: str,
        frequency: str,
        custom_schedule: list[str],
        aqi_trigger: Optional[int],
        condition_specific: bool,
    ) -> str:
        """Add a medication for a user. Returns medication ID."""
        medication_data = {
            "user_id": user_id,
            "medication_name": medication_name,
            "medication_type": medication_type,
            "dosage": dosage,
            "frequency": frequency,
            "custom_schedule": custom_schedule,
            "aqi_trigger": aqi_trigger,
            "condition_specific": condition_specific,
            "active": True,
        }
        response = self.client.table("medications").insert(medication_data).execute()
        return response.data[0]["id"] if response.data else ""

    def get_user_medications(self, user_id: str) -> list[dict]:
        """Get all active medications for a user."""
        response = (
            self.client.table("medications")
            .select("*")
            .eq("user_id", user_id)
            .eq("active", True)
            .order("created_at", desc=True)
            .execute()
        )
        return response.data or []

    def update_medication(
        self,
        medication_id: str,
        medication_name: str,
        medication_type: str,
        dosage: str,
        frequency: str,
        custom_schedule: list[str],
        aqi_trigger: Optional[int],
        condition_specific: bool,
    ) -> bool:
        """Update a medication. Returns True if successful."""
        try:
            medication_data = {
                "medication_name": medication_name,
                "medication_type": medication_type,
                "dosage": dosage,
                "frequency": frequency,
                "custom_schedule": custom_schedule,
                "aqi_trigger": aqi_trigger,
                "condition_specific": condition_specific,
            }
            response = (
                self.client.table("medications")
                .update(medication_data)
                .eq("id", medication_id)
                .execute()
            )
            return len(response.data) > 0
        except Exception:
            return False

    def delete_medication(self, medication_id: str) -> bool:
        """Delete (deactivate) a medication. Returns True if successful."""
        try:
            response = (
                self.client.table("medications")
                .update({"active": False})
                .eq("id", medication_id)
                .execute()
            )
            return len(response.data) > 0
        except Exception:
            return False

    def check_recent_medication_reminder(self, medication_id: str, hours: int = 6) -> bool:
        """Check if a medication reminder was sent recently."""
        from datetime import timedelta
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        response = (
            self.client.table("medication_reminders")
            .select("id")
            .eq("medication_id", medication_id)
            .eq("status", "sent")
            .gte("sent_at", cutoff_time.isoformat())
            .limit(1)
            .execute()
        )
        return len(response.data or []) > 0

    def log_medication_reminder(
        self,
        medication_id: str,
        user_id: str,
        reminder_type: str,
        aqi_at_time: int,
        message_sent: str,
        channel: str,
        status: str,
    ) -> None:
        """Log a medication reminder."""
        reminder_data = {
            "medication_id": medication_id,
            "user_id": user_id,
            "reminder_type": reminder_type,
            "aqi_at_time": aqi_at_time,
            "message_sent": message_sent,
            "channel": channel,
            "status": status,
        }
        self.client.table("medication_reminders").insert(reminder_data).execute()

    # ── Family Groups ──────────────────────────────────────────────────────────

    def create_family_group(
        self,
        group_name: str,
        creator_user_id: str,
        description: Optional[str],
        shared_alert_threshold: int,
        auto_share_location: bool,
        emergency_mode: bool,
    ) -> str:
        """Create a family group. Returns group ID."""
        group_data = {
            "group_name": group_name,
            "creator_user_id": creator_user_id,
            "description": description,
            "shared_alert_threshold": shared_alert_threshold,
            "auto_share_location": auto_share_location,
            "emergency_mode": emergency_mode,
            "active": True,
        }
        response = self.client.table("family_groups").insert(group_data).execute()
        return response.data[0]["id"] if response.data else ""

    def get_family_group(self, group_id: str) -> Optional[dict]:
        """Get family group details."""
        response = (
            self.client.table("family_groups")
            .select("*")
            .eq("id", group_id)
            .eq("active", True)
            .maybe_single()
            .execute()
        )
        return response.data

    def add_family_member(self, group_id: str, user_id: str, role: str = "member") -> bool:
        """Add a member to a family group. Returns True if successful."""
        try:
            member_data = {
                "group_id": group_id,
                "user_id": user_id,
                "role": role,
                "notifications_enabled": True,
            }
            response = self.client.table("family_group_members").insert(member_data).execute()
            return len(response.data) > 0
        except Exception:
            return False  # Likely duplicate member

    def get_user_family_groups(self, user_id: str) -> list[dict]:
        """Get all family groups for a user."""
        response = (
            self.client.table("family_group_members")
            .select("*, family_groups(*)")
            .eq("user_id", user_id)
            .execute()
        )
        
        groups = []
        for member in response.data or []:
            if member.get("family_groups"):
                group = member["family_groups"]
                group["user_role"] = member["role"]
                group["notifications_enabled"] = member["notifications_enabled"]
                groups.append(group)
        
        return groups

    def get_family_group_members(self, group_id: str) -> list[dict]:
        """Get all members of a family group."""
        response = (
            self.client.table("family_group_members")
            .select("*, users(id, name, email, phone, condition, severity)")
            .eq("group_id", group_id)
            .execute()
        )
        
        members = []
        for member in response.data or []:
            if member.get("users"):
                user_data = member["users"]
                user_data["role"] = member["role"]
                user_data["notifications_enabled"] = member["notifications_enabled"]
                user_data["joined_at"] = member["joined_at"]
                members.append(user_data)
        
        return members

    def log_family_alert(
        self,
        group_id: str,
        triggered_by_user: str,
        alert_type: str,
        message: str,
        members_notified: int,
    ) -> None:
        """Log a family alert."""
        alert_data = {
            "group_id": group_id,
            "triggered_by_user": triggered_by_user,
            "alert_type": alert_type,
            "message": message,
            "members_notified": members_notified,
        }
        self.client.table("family_alerts").insert(alert_data).execute()

    # ── Emergency Contacts ─────────────────────────────────────────────────────

    def add_emergency_contact(
        self,
        user_id: str,
        contact_name: str,
        relationship: str,
        phone: Optional[str],
        email: Optional[str],
        priority: int,
        notify_on_critical: bool,
        notify_on_missed_checkin: bool,
    ) -> str:
        """Add an emergency contact for a user. Returns contact ID."""
        contact_data = {
            "user_id": user_id,
            "contact_name": contact_name,
            "relationship": relationship,
            "phone": phone,
            "email": email,
            "priority": priority,
            "notify_on_critical": notify_on_critical,
            "notify_on_missed_checkin": notify_on_missed_checkin,
            "active": True,
        }
        response = self.client.table("emergency_contacts").insert(contact_data).execute()
        return response.data[0]["id"] if response.data else ""

    def get_user_emergency_contacts(self, user_id: str) -> list[dict]:
        """Get all active emergency contacts for a user."""
        response = (
            self.client.table("emergency_contacts")
            .select("*")
            .eq("user_id", user_id)
            .eq("active", True)
            .order("priority", desc=False)  # Lower priority number = higher priority
            .execute()
        )
        return response.data or []

    def update_emergency_contact(
        self,
        contact_id: str,
        contact_name: str,
        relationship: str,
        phone: Optional[str],
        email: Optional[str],
        priority: int,
        notify_on_critical: bool,
        notify_on_missed_checkin: bool,
    ) -> bool:
        """Update an emergency contact. Returns True if successful."""
        try:
            contact_data = {
                "contact_name": contact_name,
                "relationship": relationship,
                "phone": phone,
                "email": email,
                "priority": priority,
                "notify_on_critical": notify_on_critical,
                "notify_on_missed_checkin": notify_on_missed_checkin,
            }
            response = (
                self.client.table("emergency_contacts")
                .update(contact_data)
                .eq("id", contact_id)
                .execute()
            )
            return len(response.data) > 0
        except Exception:
            return False

    def delete_emergency_contact(self, contact_id: str) -> bool:
        """Delete (deactivate) an emergency contact. Returns True if successful."""
        try:
            response = (
                self.client.table("emergency_contacts")
                .update({"active": False})
                .eq("id", contact_id)
                .execute()
            )
            return len(response.data) > 0
        except Exception:
            return False


# ─── Singleton ────────────────────────────────────────────────────────────────

db = Database()
