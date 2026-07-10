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


# ─── Singleton ────────────────────────────────────────────────────────────────

db = Database()
