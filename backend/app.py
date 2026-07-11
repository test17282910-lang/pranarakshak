"""
app.py — AQI Health Alert System FastAPI Backend
GPS-based predictive AQI API with:
  - Monte Carlo Dropout uncertainty estimation
  - RMSE safety buffer (cost-sensitive threshold shifting)
  - Data quality tiering (live → interpolated → seasonal fallback)
  - India NAQI classification with condition-specific precautions
  - Full prediction provenance tracking (prediction_source field)

Endpoints:
  GET  /health   — service + model status
  POST /predict  — GPS-based AQI prediction
  POST /train    — background model retraining
"""

import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Optional

import joblib
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field

from db import db

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

# ─── Artifact Paths ───────────────────────────────────────────────────────────
MODEL_PATH = os.getenv("MODEL_PATH", "aqi_lstm.h5")
SCALER_PATH = os.getenv("SCALER_PATH", "scaler.pkl")
METADATA_PATH = os.getenv("METADATA_PATH", "model_metadata.json")
BASELINE_PATH = os.getenv("BASELINE_PATH", "seasonal_baseline.json")

# ─── Risk Model Artifact Paths ────────────────────────────────────────────────
RISK_MODEL_PATH = os.getenv("RISK_MODEL_PATH", "risk_model.pkl")
RISK_ENCODER_PATH = os.getenv("RISK_ENCODER_PATH", "risk_label_encoder.pkl")
RISK_METADATA_PATH = os.getenv("RISK_METADATA_PATH", "risk_model_metadata.json")

# ─── Inference Config ─────────────────────────────────────────────────────────
WINDOW = 48          # Must match train.py
MC_SAMPLES = 50      # Monte Carlo forward passes
MC_PERCENTILE = 90   # High percentile for safety bias under uncertainty

FEATURES = [
    "pm25", "pm10", "no2", "o3", "co",
    "temperature", "humidity", "wind_speed",
    "hour_sin", "hour_cos", "day_sin", "day_cos",
    "pm25_lag1", "pm25_lag6", "pm25_lag24",
    "pm25_rolling6", "pm25_rolling24",
]
TARGET = "aqi"

# ─── Shared App State ─────────────────────────────────────────────────────────
_state: dict = {
    "model": None,
    "scaler": None,
    "metadata": {},
    "baseline": {},
    "risk_model": None,
    "risk_encoder": None,
}


# ─── Artifact Loader ──────────────────────────────────────────────────────────

def _load_artifacts() -> None:
    """Load models, scalers, metadata, and baselines from disk into shared state."""
    import tensorflow as tf  # imported here so startup is fast even without TF

    if os.path.exists(MODEL_PATH):
        _state["model"] = tf.keras.models.load_model(MODEL_PATH, compile=False)
        logger.info(f"Model loaded ← {MODEL_PATH}")
    else:
        logger.warning(f"Model not found at {MODEL_PATH}. Run train.py first.")

    if os.path.exists(SCALER_PATH):
        _state["scaler"] = joblib.load(SCALER_PATH)
        logger.info(f"Scaler loaded ← {SCALER_PATH}")

    if os.path.exists(METADATA_PATH):
        with open(METADATA_PATH) as f:
            _state["metadata"] = json.load(f)
        logger.info(
            f"Metadata loaded — RMSE: {_state['metadata'].get('rmse', 'N/A'):.2f}"
            if isinstance(_state["metadata"].get("rmse"), float)
            else "Metadata loaded"
        )

    if os.path.exists(BASELINE_PATH):
        with open(BASELINE_PATH) as f:
            _state["baseline"] = json.load(f)
        logger.info(f"Seasonal baseline loaded ({len(_state['baseline'])} buckets)")

    # Load Health Risk Classifier Model
    if os.path.exists(RISK_MODEL_PATH) and os.path.exists(RISK_ENCODER_PATH):
        try:
            _state["risk_model"] = joblib.load(RISK_MODEL_PATH)
            _state["risk_encoder"] = joblib.load(RISK_ENCODER_PATH)
            logger.info("XGBoost health risk classifier and encoder loaded successfully.")
        except Exception as exc:
            logger.warning(f"Failed to load risk model from disk: {exc}")
    else:
        logger.warning("XGBoost health risk classifier not found. Falling back to rule-based shifts.")


# ─── App Lifespan ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    _load_artifacts()
    logger.info("AQI Health Alert API ready ✓")
    yield
    logger.info("Shutting down")


# ─── FastAPI App ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="AQI Health Alert System",
    description=(
        "Predictive AI for Air Quality Index health alerts. "
        "GPS-based, uncertainty-aware, with graceful degradation."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# Parse CORS origins from env, stripping whitespace
cors_origins_raw = os.getenv("CORS_ORIGINS", "*")
if cors_origins_raw == "*":
    allowed_origins = ["*"]
else:
    # Split by comma and strip whitespace from each origin
    allowed_origins = [origin.strip() for origin in cors_origins_raw.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods including OPTIONS
    allow_headers=["*"],  # Allow all headers
    expose_headers=["*"],  # Expose all response headers
    max_age=3600,  # Cache preflight requests for 1 hour
)


# ─── Pydantic Schemas ─────────────────────────────────────────────────────────

class PredictRequest(BaseModel):
    lat: float = Field(..., ge=-90, le=90, description="User latitude (from GPS)")
    lon: float = Field(..., ge=-180, le=180, description="User longitude (from GPS)")
    user_id: str = Field(..., description="User identifier")
    radius_km: int = Field(25, ge=1, le=100, description="Nearest station search radius (km)")
    condition: Optional[str] = Field(None, description="Health condition: 'copd', 'asthma', 'both', 'other'")
    severity: Optional[str] = Field(None, description="Condition severity: 'mild', 'moderate', 'severe'")


class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(None, min_length=8, description="Plaintext password — hashed before storage")
    condition: str = Field(..., description="Health condition: 'copd', 'asthma', 'both', 'other'")
    severity: str = Field("moderate", description="Condition severity: 'mild', 'moderate', 'severe'")
    lat: Optional[float] = Field(None, ge=-90, le=90)
    lon: Optional[float] = Field(None, ge=-180, le=180)
    symptoms: Optional[list[str]] = Field(default=[])
    personalized_issue: Optional[str] = Field(None)
    alert_threshold: Optional[int] = Field(100, ge=50, le=500, description="Custom AQI threshold for alerts")
    # Medication reminders
    medications: Optional[list[dict]] = Field(default=[], description="List of medications with schedules")
    emergency_contacts: Optional[list[dict]] = Field(default=[], description="Emergency contacts for critical alerts")
    family_group_id: Optional[str] = Field(None, description="Family group identifier for shared alerts")


class LoginRequest(BaseModel):
    identifier: str = Field(..., description="Email, phone, or User UUID")
    password: Optional[str] = Field(None, description="Required for email/phone login; omit for UUID-only lookup")


class MedicationRequest(BaseModel):
    user_id: str
    medication_name: str = Field(..., description="Name of medication (e.g., 'Salbutamol Inhaler', 'Budesonide')")
    medication_type: str = Field(..., description="Type: 'rescue_inhaler', 'preventer_inhaler', 'nebulizer', 'oral', 'other'")
    dosage: str = Field(..., description="Dosage instructions (e.g., '2 puffs', '100mcg')")
    frequency: str = Field(..., description="Frequency: 'as_needed', 'daily', 'twice_daily', 'thrice_daily', 'custom'")
    custom_schedule: Optional[list[str]] = Field(None, description="Custom times if frequency is 'custom' (e.g., ['08:00', '20:00'])")
    aqi_trigger: Optional[int] = Field(None, description="AQI threshold to trigger reminders (e.g., 100)")
    condition_specific: bool = Field(True, description="Whether to adjust reminders based on condition severity")


class EmergencyContactRequest(BaseModel):
    user_id: str
    contact_name: str = Field(..., min_length=2, max_length=100)
    relationship: str = Field(..., description="Relationship: 'spouse', 'parent', 'child', 'sibling', 'friend', 'doctor', 'caregiver'")
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[EmailStr] = None
    priority: int = Field(1, ge=1, le=5, description="Priority level (1=highest, 5=lowest)")
    notify_on_critical: bool = Field(True, description="Notify during critical AQI events")
    notify_on_missed_checkin: bool = Field(False, description="Notify if user doesn't check app during high AQI")


class FamilyGroupRequest(BaseModel):
    group_name: str = Field(..., min_length=2, max_length=100)
    creator_user_id: str
    description: Optional[str] = Field(None, max_length=500)
    shared_alert_threshold: int = Field(100, ge=50, le=500)
    auto_share_location: bool = Field(True, description="Share location updates with family")
    emergency_mode: bool = Field(True, description="Enable emergency cascading alerts")


class LocationUpdateRequest(BaseModel):
    user_id: str
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    city: Optional[str] = None


class PrecautionItem(BaseModel):
    category: str  # "general", "condition", "symptom", "trigger"
    text: str

class RiskExplanation(BaseModel):
    raw_aqi: float
    condition: str
    severity: str
    condition_shift: int
    symptom_count: int
    symptom_penalty: int
    effective_aqi: float
    threshold_crossed: str
    method: str  # "xgboost" or "rule_based"
    why_be_careful: Optional[str] = None

class PredictionResponse(BaseModel):
    user_id: str
    current_aqi: Optional[float] = None
    air_quality_tier: Optional[str] = None
    predicted_aqi_raw: float
    predicted_aqi_adjusted: float
    rmse_buffer: float
    prediction_confidence: float
    prediction_source: str
    alert_tier: str
    alert_message: str
    precautions: list[PrecautionItem]
    risk_explanation: Optional[RiskExplanation] = None
    safe_hours: Optional[list[str]] = None
    aqi_trend: Optional[str] = None  # "improving", "worsening", "stable"
    timestamp: str
    forecast_for: str


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    rmse: Optional[float] = None
    trained_at: Optional[str] = None


# ─── Condition-Specific Sensitivity Thresholds ───────────────────────────────

# Patients with respiratory conditions react to lower AQI levels.
# We shift the classification thresholds DOWN so alerts fire earlier.
# Shift = how many AQI points below the standard threshold to alert.
CONDITION_SHIFT = {
    # (condition, severity) → AQI points to subtract from standard thresholds
    ("copd",   "mild"):     15,
    ("copd",   "moderate"): 30,
    ("copd",   "severe"):   50,
    ("asthma", "mild"):     10,
    ("asthma", "moderate"): 25,
    ("asthma", "severe"):   40,
    ("both",   "mild"):     25,
    ("both",   "moderate"): 40,
    ("both",   "severe"):   60,
    ("other",  "mild"):     0,
    ("other",  "moderate"): 0,
    ("other",  "severe"):   10,
}


def get_condition_shift(condition: str, severity: str) -> int:
    """Return the AQI threshold shift for this patient's condition and severity."""
    key = (condition.lower(), severity.lower())
    return CONDITION_SHIFT.get(key, 0)


# ─── India NAQI Raw Air Quality Label ────────────────────────────────────────

def naqi_air_quality_tier(aqi: float) -> str:
    """
    Returns the official India NAQI air quality category based purely on
    the raw AQI number — completely separate from any health risk classification.
    Thresholds: https://cpcb.nic.in/national-air-quality-index/
    """
    if aqi <= 50:
        return "Good"
    elif aqi <= 100:
        return "Satisfactory"
    elif aqi <= 200:
        return "Moderate"
    elif aqi <= 300:
        return "Poor"
    elif aqi <= 400:
        return "Very Poor"
    else:
        return "Severe"


# ─── India NAQI Health Risk Classification ───────────────────────────────────

def classify_aqi(
    aqi: float,
    condition: str = "other",
    severity: str = "moderate",
    pollutants: Optional[dict] = None,
    symptoms: Optional[list] = None,
    personalized_issue: Optional[str] = None,
    patient_name: str = "Patient",
) -> tuple[str, str, list[dict], dict]:
    """
    Returns (tier, alert_message, structured_precautions, risk_explanation).

    structured_precautions: list of {"category": str, "text": str}
        category ∈ {"general", "condition", "symptom", "trigger"}

    risk_explanation: dict with full computation transparency and plain-English reasons
    """
    tier = None
    method = "rule_based"

    # Normalize inputs
    condition = (condition or "other").strip().lower()
    severity = (severity or "moderate").strip().lower()
    clean_symptoms = [s.strip() for s in (symptoms or []) if s and s.strip()]

    # Compute penalties
    symptom_penalty = len(clean_symptoms) * 4
    effective_aqi = aqi + symptom_penalty
    shift = get_condition_shift(condition, severity)

    # ── Option A: XGBoost Clinical Classifier ──────────────────────────────────
    if _state["risk_model"] is not None and pollutants is not None:
        try:
            cond_copd = 1 if condition == "copd" else 0
            cond_asthma = 1 if condition == "asthma" else 0
            cond_both = 1 if condition == "both" else 0
            cond_other = 1 if condition == "other" else 0

            sev_mild = 1 if severity == "mild" else 0
            sev_moderate = 1 if severity == "moderate" else 0
            sev_severe = 1 if severity == "severe" else 0

            features_list = [
                float(effective_aqi),
                float(pollutants.get("pm25", 0.0) or 0.0),
                float(pollutants.get("pm10", 0.0) or 0.0),
                float(pollutants.get("no2", 0.0) or 0.0),
                float(pollutants.get("o3", 0.0) or 0.0),
                float(pollutants.get("co", 0.0) or 0.0),
                float(pollutants.get("temperature", 25.0) or 25.0),
                float(pollutants.get("humidity", 60.0) or 60.0),
                cond_copd, cond_asthma, cond_both, cond_other,
                sev_mild, sev_moderate, sev_severe
            ]

            X_risk = np.array([features_list])
            pred_idx = int(_state["risk_model"].predict(X_risk)[0])

            class_names = ["safe", "caution", "high_risk", "critical"]
            tier = class_names[pred_idx]
            method = "xgboost"
            logger.info(f"Clinical risk classified via XGBoost: {tier} (Class {pred_idx})")
        except Exception as exc:
            logger.warning(f"XGBoost classification failed: {exc}. Falling back to rules.")

    # ── Option B: Rule-Based Fallback ──────────────────────────────────────────
    if tier is None:
        final_shifted_aqi = effective_aqi + shift

        if final_shifted_aqi <= 50:
            tier = "safe"
        elif final_shifted_aqi <= 100:
            tier = "caution"
        elif final_shifted_aqi <= 200:
            tier = "high_risk"
        else:
            tier = "critical"

    # ── Build threshold explanation string ─────────────────────────────────────
    threshold_map = {"safe": "≤50", "caution": "51–100", "high_risk": "101–200", "critical": ">200"}
    threshold_crossed = f"{tier} ({threshold_map.get(tier, '?')})"

    cond_label = condition.upper() if condition != "other" else "respiratory condition"

    # ── Dynamically Generate why_be_careful explanation ────────────────────────
    symptoms_str = ", ".join(clean_symptoms) if clean_symptoms else "none reported"
    
    if condition == "asthma":
        why_be_careful = (
            f"Dear {patient_name}, Asthma causes chronic bronchial hyper-responsiveness. "
            f"At an AQI of {round(aqi)}, fine respirable dust (PM2.5) enters the bronchioles, causing microscopic airway inflammation. "
            f"Since your asthma is clinically classified as {severity.upper()} and you have active symptoms ({symptoms_str}), "
            f"your lungs are highly vulnerable. This pollution level acts as an immediate trigger, risking a sudden bronchospasm or asthma attack."
        )
    elif condition == "copd":
        why_be_careful = (
            f"Dear {patient_name}, COPD causes permanent damage to the alveoli. "
            f"Elevated pollutants restrict your already compromised gas exchange capacity. "
            f"With your {severity.upper()} COPD classification, today's AQI of {round(aqi)} puts excess demand on your cardiovascular system to maintain oxygenation, "
            f"greatly increasing the chance of acute desaturation, fatigue, or a COPD exacerbation."
        )
    elif condition == "both":
        why_be_careful = (
            f"Dear {patient_name}, carrying both Asthma and COPD (ACO) multiplies your clinical risk. "
            f"Airborne particulates cause rapid mucosal swelling while compounding baseline airways blockages. "
            f"Given your active symptoms ({symptoms_str}), breathing today's air puts you in danger of a severe breathing episode."
        )
    else:
        why_be_careful = (
            f"Dear {patient_name}, even general respiratory systems are susceptible to irritation from ambient particulates today. "
            f"Inhaling this air can cause dry coughing, throat irritation, and chest discomfort."
        )

    # ── Risk Explanation ──────────────────────────────────────────────────────
    risk_explanation = {
        "raw_aqi": round(aqi, 1),
        "condition": condition,
        "severity": severity,
        "condition_shift": shift,
        "symptom_count": len(clean_symptoms),
        "symptom_penalty": symptom_penalty,
        "effective_aqi": round(effective_aqi + shift, 1),
        "threshold_crossed": threshold_crossed,
        "method": method,
        "why_be_careful": why_be_careful
    }

    # ═══════════════════════════════════════════════════════════════════════════
    # STRUCTURED PRECAUTIONS — highly personalized using patient details
    # ═══════════════════════════════════════════════════════════════════════════

    precautions: list[dict] = []

    # ── General precautions (based on risk tier) ──────────────────────────────
    if tier == "safe":
        precautions.append({"category": "general", "text": f"Hi {patient_name}, air quality matches your safety threshold. Feel free to engage in normal outdoor activities."})
    elif tier == "caution":
        precautions.extend([
            {"category": "general", "text": f"{patient_name}, please avoid prolonged or strenuous outdoor activities today."},
            {"category": "general", "text": "Keep your fast-acting rescue inhaler accessible at all times."},
        ])
    elif tier == "high_risk":
        precautions.extend([
            {"category": "general", "text": f"{patient_name}, cut outdoor time to a minimum, especially during morning and evening rush hours."},
            {"category": "general", "text": "Keep windows closed to prevent external particulates from settling indoors."},
            {"category": "general", "text": "Run your home air purifier in the main living space."},
            {"category": "general", "text": "Carry your rescue inhaler on your person when stepping outside."},
            {"category": "general", "text": "Watch for early warning signs: coughing, chest tightness, or wheezing."},
        ])
    else:  # critical
        precautions.extend([
            {"category": "general", "text": f"🚨 {patient_name}, avoid ALL outdoor activities today. Please stay strictly indoors."},
            {"category": "general", "text": "Seal all doors and windows to keep particulate concentration low."},
            {"category": "general", "text": "If you absolutely must step outside, wear a well-fitted N95 or N99 mask."},
            {"category": "general", "text": "Ensure you take your daily preventive/controller medication as scheduled."},
            {"category": "general", "text": "Keep your rescue inhaler and nebulizer plugged in and ready."},
            {"category": "general", "text": "Monitor your breathing patterns; contact your healthcare provider if symptoms worsen."},
            {"category": "general", "text": "Alert a caregiver or family member about your current health status."},
        ])

    # ── Condition-specific precautions ─────────────────────────────────────────
    if condition in ("copd", "both"):
        precautions.extend([
            {"category": "condition", "text": f"[{cond_label}] {patient_name}, because your COPD is classified as {severity.upper()}, make sure to take your long-acting bronchodilator (LABA/LAMA) exactly as prescribed."},
            {"category": "condition", "text": f"[{cond_label}] Keep supplemental oxygen canisters/concentrator fully charged and accessible."},
            {"category": "condition", "text": f"[{cond_label}] Avoid heavy physical tasks; even minor chores will place excessive load on your damaged alveoli today."},
        ])
    if condition in ("asthma", "both"):
        precautions.extend([
            {"category": "condition", "text": f"[{cond_label}] {patient_name}, since your asthma is {severity.upper()}, do not skip your preventer (ICS) inhaler doses today; it limits baseline airways hyper-responsiveness."},
            {"category": "condition", "text": f"[{cond_label}] Log peak flow meter readings twice today to detect early bronchoconstriction."},
            {"category": "condition", "text": f"[{cond_label}] Avoid other secondary triggers like active smoke, chemical vapors, or dust today."},
        ])

    # ── Symptom-specific precautions ───────────────────────────────────────────
    if clean_symptoms:
        sym_set = {s.lower().strip() for s in clean_symptoms}
        if "wheezing" in sym_set:
            precautions.append({"category": "symptom", "text": f"[Wheezing] {patient_name}, you reported active wheezing. Use your quick-relief bronchodilator immediately if you notice audible whistling sound during exhalation."})
        if "coughing" in sym_set or "cough" in sym_set:
            precautions.append({"category": "symptom", "text": f"[Coughing] {patient_name}, to ease your frequent cough, sip warm fluids regularly and avoid extremely dry air conditioning rooms."})
        if "chesttightness" in sym_set or "chest tightness" in sym_set:
            precautions.append({"category": "symptom", "text": f"[Chest Tightness] {patient_name}, chest tightness signals narrowed airways. Sit in a comfortable upright position, restrict movement, and use your relief inhaler."})
        if "shortnessofbreath" in sym_set or "shortness of breath" in sym_set:
            precautions.append({"category": "symptom", "text": f"[Shortness of Breath] {patient_name}, for shortness of breath, track your blood oxygen level (SpO2) and avoid any walking or climbing stairs."})
        if "nighttimesymptoms" in sym_set or "nighttime symptoms" in sym_set:
            precautions.append({"category": "symptom", "text": f"[Night Symptoms] {patient_name}, to avoid nocturnal coughing or gasping, run your air purifier in your bedroom on high speed tonight."})
        if "exerciseinduced" in sym_set or "exercise induced" in sym_set:
            precautions.append({"category": "symptom", "text": f"[Exercise-Induced] {patient_name}, please skip your workout session, jogs, or long walks today to prevent exercise-induced bronchial spasms."})

    # ── Trigger-specific precautions ───────────────────────────────────────────
    if personalized_issue:
        issue_lower = personalized_issue.lower()
        if "dust" in issue_lower:
            precautions.append({"category": "trigger", "text": f"[Dust Trigger] {patient_name}, dust is your custom trigger. With current pollution levels, keep your rooms damp-wiped and avoid sweeping with dry brooms."})
        if "pollen" in issue_lower or "grass" in issue_lower or "flower" in issue_lower:
            precautions.append({"category": "trigger", "text": f"[Pollen Trigger] {patient_name}, you are triggered by pollens. Shower and change clothes immediately if you return from outside to rinse away micro-allergens."})
        if "cold" in issue_lower or "winter" in issue_lower:
            precautions.append({"category": "trigger", "text": f"[Cold Air Trigger] {patient_name}, cover your face with a warm scarf when stepping out to prevent cold-air induced airway narrowing."})
        if "smoke" in issue_lower or "fire" in issue_lower:
            precautions.append({"category": "trigger", "text": f"[Smoke Trigger] {patient_name}, smoke triggers you. Avoid kitchen smoke, incense burners, and cigarette exposure today."})
        
        has_specific = any(kw in issue_lower for kw in ["dust", "pollen", "grass", "flower", "cold", "winter", "smoke", "fire"])
        if not has_specific:
            precautions.append({"category": "trigger", "text": f"[Custom Trigger] {patient_name}, take steps to minimize contact with your customized trigger: {personalized_issue}."})

    # ── Alert message ─────────────────────────────────────────────────────────
    tier_labels = {"safe": "Safe", "caution": "Caution", "high_risk": "High Risk", "critical": "Critical"}
    tier_icons = {"safe": "✅", "caution": "🟡", "high_risk": "🟠", "critical": "⚠️"}
    tier_display = tier_labels.get(tier, tier)
    icon = tier_icons.get(tier, "ℹ️")

    shift_parts = []
    if shift > 0:
        shift_parts.append(f"{condition} ({severity}) adds +{shift}")
    if symptom_penalty > 0:
        shift_parts.append(f"{len(clean_symptoms)} symptom{'s' if len(clean_symptoms) > 1 else ''} adds +{symptom_penalty}")
    shift_text = "; ".join(shift_parts)
    shift_clause = f" ({shift_text})" if shift_text else ""

    message = (
        f"{icon} Your personal health risk is {tier_display}. "
        f"AQI {round(aqi)} → effective {round(effective_aqi + shift)}{shift_clause}. "
        f"Personalised for {cond_label}."
    )

    return tier_display, message, precautions, risk_explanation


# ─── Feature Engineering ──────────────────────────────────────────────────────

def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Applies the exact same feature engineering as train.py.
    Must stay in sync at all times.
    """
    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)

    df["hour_sin"] = np.sin(2 * np.pi * df["timestamp"].dt.hour / 24)
    df["hour_cos"] = np.cos(2 * np.pi * df["timestamp"].dt.hour / 24)
    df["day_sin"] = np.sin(2 * np.pi * df["timestamp"].dt.dayofweek / 7)
    df["day_cos"] = np.cos(2 * np.pi * df["timestamp"].dt.dayofweek / 7)

    df["pm25_lag1"] = df["pm25"].shift(1).bfill()
    df["pm25_lag6"] = df["pm25"].shift(6).bfill()
    df["pm25_lag24"] = df["pm25"].shift(24).bfill()
    df["pm25_rolling6"] = df["pm25"].rolling(6, min_periods=1).mean()
    df["pm25_rolling24"] = df["pm25"].rolling(24, min_periods=1).mean()

    return df


# ─── Data Quality Tiering ─────────────────────────────────────────────────────

def assess_data_quality(
    df: Optional[pd.DataFrame],
) -> tuple[Optional[pd.DataFrame], str]:
    """
    Three-tier data quality assessment:
      Tier 0 — live:          >= WINDOW rows available
      Tier 1 — interpolated:  small gap (<= 3 missing), fill with linear interpolation
      Tier 2 — large_gap:     too many missing rows, caller must use seasonal fallback
    """
    if df is None or len(df) == 0:
        return None, "no_data"

    actual = len(df)

    # Tier 0: enough data for a full LSTM window
    if actual >= WINDOW:
        return df.tail(WINDOW).reset_index(drop=True), "live"

    missing = WINDOW - actual

    # Tier 1: small gap — interpolate linearly
    if missing <= 3 and actual >= 12:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = (
            df.set_index("timestamp")
            .resample("1h")
            .mean()
            .interpolate(method="linear")
            .reset_index()
        )
        return df.tail(WINDOW).reset_index(drop=True), "interpolated"

    # Tier 2: large gap — signal caller to use seasonal fallback
    return None, "large_gap"


# ─── Seasonal Fallback ────────────────────────────────────────────────────────

def get_seasonal_fallback(target_time: datetime) -> float:
    """Return historical mean AQI for the given day-of-week + hour bucket."""
    if not _state["baseline"]:
        logger.warning("Seasonal baseline not loaded — defaulting to AQI 100")
        return 100.0

    key = f"{target_time.weekday()}_{target_time.hour}"
    return _state["baseline"].get(key, 100.0)


def get_safe_hours(target_date: datetime) -> list[str]:
    """
    Computes time slots of the day where the seasonal baseline AQI is below 110
    representing optimal outdoor periods for high-susceptibility patients.
    """
    if not _state["baseline"]:
        return ["06:00 - 09:00", "18:00 - 21:00"]

    weekday = target_date.weekday()
    safe_slots = []
    
    hourly_aqis = []
    for h in range(24):
        key = f"{weekday}_{h}"
        aqi_val = _state["baseline"].get(key, 100.0)
        hourly_aqis.append((h, aqi_val))
        
    in_block = False
    start_hour = None
    
    for h, val in hourly_aqis:
        if val < 110:
            if not in_block:
                in_block = True
                start_hour = h
        else:
            if in_block:
                in_block = False
                safe_slots.append(f"{start_hour:02d}:00 - {h:02d}:00")
                
    if in_block:
        safe_slots.append(f"{start_hour:02d}:00 - 23:59")
        
    if not safe_slots:
        sorted_hours = sorted(hourly_aqis, key=lambda x: x[1])
        top_hours = sorted([x[0] for x in sorted_hours[:6]])
        blocks = []
        i = 0
        while i < len(top_hours):
            start = top_hours[i]
            end = start
            while i + 1 < len(top_hours) and top_hours[i+1] == end + 1:
                end = top_hours[i+1]
                i += 1
            blocks.append(f"{start:02d}:00 - {(end+1)%24:02d}:00")
            i += 1
        safe_slots = blocks
        
    return safe_slots[:3]


# ─── Monte Carlo Dropout Inference ───────────────────────────────────────────

def mc_predict(X: np.ndarray) -> tuple[float, float, float]:
    """
    Run MC_SAMPLES stochastic forward passes with training=True (dropout active).
    Returns (median_aqi, p90_aqi, std_aqi) in original AQI scale.

    p90_aqi is used as the prediction value to bias toward caution under uncertainty.
    std_aqi is reported as prediction_confidence (lower = more certain).
    """
    model = _state["model"]
    scaler = _state["scaler"]
    n_all = len(FEATURES) + 1  # features + target

    samples_scaled = [
        float(model(X, training=True).numpy()[0][0]) for _ in range(MC_SAMPLES)
    ]

    p50 = float(np.percentile(samples_scaled, 50))
    p90 = float(np.percentile(samples_scaled, MC_PERCENTILE))
    std = float(np.std(samples_scaled))

    def inverse(val: float) -> float:
        dummy = np.zeros((1, n_all))
        dummy[0, -1] = val
        return float(scaler.inverse_transform(dummy)[0, -1])

    raw_aqi = inverse(p50)
    p90_aqi = inverse(p90)

    # Convert std from scaled → AQI units
    aqi_range = float(scaler.data_range_[-1]) if hasattr(scaler, "data_range_") else 400.0
    std_aqi = std * aqi_range

    return raw_aqi, p90_aqi, std_aqi


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse, tags=["System"])
def health() -> HealthResponse:
    """Check service health and model status."""
    meta = _state["metadata"]
    return HealthResponse(
        status="ok" if _state["model"] is not None else "degraded_no_model",
        model_loaded=_state["model"] is not None,
        rmse=meta.get("rmse"),
        trained_at=meta.get("trained_at"),
    )


@app.get("/test-alert/{user_id}", tags=["System"])
async def test_alert(user_id: str):
    """
    TEST ENDPOINT: Force send WhatsApp and email alert to a user.
    Use this to debug Twilio/SendGrid configuration.
    """
    import asyncio
    from alerts import send_whatsapp, send_email
    
    # Get user
    user = await asyncio.to_thread(db.get_user_by_id, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    results = {"user_id": user_id, "whatsapp": None, "email": None}
    
    # Test WhatsApp
    phone = user.get("phone")
    if phone:
        whatsapp_text = f"🧪 TEST ALERT from Pranarakshak\n\nHello {user.get('name', 'User')}! This is a test WhatsApp message to verify Twilio WhatsApp sandbox is working correctly."
        status, msg_id = send_whatsapp(phone, whatsapp_text)
        results["whatsapp"] = {"status": status, "id": msg_id, "phone": phone}
        logger.info(f"Test WhatsApp sent to {phone}: {status} - {msg_id}")
    else:
        results["whatsapp"] = {"status": "skipped", "reason": "No phone number"}
    
    # Test Email
    email = user.get("email")
    if email:
        subject = "🧪 Test Alert from Pranarakshak"
        html = f"""
<html>
<body style="font-family: Arial; padding: 20px;">
<h2>✅ Test Alert Success!</h2>
<p>Hello {user.get('name', 'User')},</p>
<p>This is a <strong>test email</strong> to verify SendGrid is configured correctly.</p>
<p>If you're seeing this, your email alerts are working! 🎉</p>
<hr>
<p style="color: #666; font-size: 12px;">Pranarakshak Alert System</p>
</body>
</html>
"""
        status, msg_id = send_email(email, subject, html)
        results["email"] = {"status": status, "id": msg_id, "email": email}
        logger.info(f"Test email sent to {email}: {status} - {msg_id}")
    else:
        results["email"] = {"status": "skipped", "reason": "No email"}
    
    return results


@app.post("/predict", response_model=PredictionResponse, tags=["Prediction"])
async def predict(payload: PredictRequest) -> PredictionResponse:
    """
    GPS-based AQI prediction endpoint.

    Pipeline:
      1. Fetch AQI readings for user's coordinates (OpenAQ → OWM fallback)
      2. Assess data quality (live / interpolated / seasonal fallback)
      3. Feature engineering
      4. Monte Carlo Dropout inference (50 passes, 90th percentile)
      5. RMSE safety buffer: adjusted_aqi = p90_aqi + RMSE
      6. India NAQI classification + condition-specific precautions
    """
    if _state["model"] is None:
        raise HTTPException(
            status_code=503,
            detail="Model not loaded. Run train.py first or call POST /train.",
        )

    import asyncio
    from data_fetcher import get_readings_for_location

    # Fetch user from DB (sync Supabase call — run in thread to avoid blocking)
    user = await asyncio.to_thread(db.get_user_by_id, payload.user_id)
    condition = payload.condition
    severity = payload.severity
    symptoms = []
    personalized_issue = None

    if user:
        condition = condition or user.get("condition", "other")
        severity = severity or user.get("severity", "moderate")
        symptoms = user.get("symptoms", [])
        personalized_issue = user.get("personalized_issue", None)
    else:
        condition = condition or "other"
        severity = severity or "moderate"

    forecast_time = datetime.now(timezone.utc) + timedelta(hours=24)
    now_str = datetime.now(timezone.utc).isoformat()

    # ── Step 1: Fetch live data (improved accuracy system) ──────────────────
    from accurate_aqi import get_accurate_current_aqi
    try:
        # Get highly accurate current AQI from multiple sources
        accurate_current_aqi, accuracy_report = await asyncio.to_thread(get_accurate_current_aqi, payload.lat, payload.lon)
        logger.info(f"🎯 Accurate AQI: {accurate_current_aqi} (sources: {accuracy_report.get('accuracy_info', {}).get('reliable_sources', 0)})")
    except Exception as e:
        logger.warning(f"Accurate AQI failed, falling back to original system: {e}")
        accurate_current_aqi = None
        accuracy_report = None
    
    # Fallback to original data fetching for historical LSTM data
    df, fetch_source, fallback_live_aqi = await asyncio.to_thread(get_readings_for_location, payload.lat, payload.lon)
    
    # Use accurate AQI if available, otherwise fallback
    live_aqi = accurate_current_aqi if accurate_current_aqi is not None else fallback_live_aqi

    # ── Step 2: Data quality tiering ─────────────────────────────────────────
    df_ready, quality_tier = assess_data_quality(df)

    # ── Step 3: Seasonal fallback if data is insufficient ────────────────────
    if df_ready is None:
        fallback_aqi = get_seasonal_fallback(forecast_time)
        patient_name = user.get("name", "Patient") if user else "Patient"
        tier, message, precautions, risk_explanation = classify_aqi(
            fallback_aqi,
            condition=condition,
            severity=severity,
            symptoms=symptoms,
            personalized_issue=personalized_issue,
            patient_name=patient_name
        )

        notice = (
            " ⚠️ Live sensor data unavailable. Prediction based on seasonal baseline."
            if quality_tier == "no_data"
            else " ⚠️ Sensor data gap > 3 hours. Prediction based on seasonal baseline."
        )

        display_aqi = live_aqi if live_aqi is not None else fallback_aqi
        trend = "stable"
        if live_aqi is not None:
            if fallback_aqi > live_aqi + 15:
                trend = "worsening"
            elif fallback_aqi < live_aqi - 15:
                trend = "improving"

        return PredictionResponse(
            user_id=payload.user_id,
            current_aqi=round(live_aqi, 1) if live_aqi is not None else None,
            air_quality_tier=naqi_air_quality_tier(display_aqi),
            predicted_aqi_raw=round(fallback_aqi, 1),
            predicted_aqi_adjusted=round(fallback_aqi, 1),
            rmse_buffer=0.0,
            prediction_confidence=0.0,
            prediction_source="historical_fallback",
            alert_tier=tier,
            alert_message=message + notice,
            precautions=[PrecautionItem(**p) for p in precautions],
            risk_explanation=RiskExplanation(**risk_explanation),
            safe_hours=get_safe_hours(forecast_time),
            aqi_trend=trend,
            timestamp=now_str,
            forecast_for=forecast_time.isoformat(),
        )

    # ── Step 4: Feature engineering ───────────────────────────────────────────
    df_ready = engineer_features(df_ready)

    for col in FEATURES:
        if col not in df_ready.columns:
            df_ready[col] = 0.0
            
    if TARGET not in df_ready.columns:
        df_ready[TARGET] = df_ready.get("pm25", pd.Series([50.0])) * 1.5

    # Fill missing weather features with sensible defaults if NaN
    if "temperature" in df_ready.columns:
        df_ready["temperature"] = df_ready["temperature"].fillna(25.0)
    if "humidity" in df_ready.columns:
        df_ready["humidity"] = df_ready["humidity"].fillna(60.0)
    if "wind_speed" in df_ready.columns:
        df_ready["wind_speed"] = df_ready["wind_speed"].fillna(3.0)

    # Fill any remaining NaN values in the features and target with 0.0
    for col in FEATURES + [TARGET]:
        df_ready[col] = df_ready[col].fillna(0.0)

    # ── Step 5: Scale + prepare input tensor ──────────────────────────────────
    scaler = _state["scaler"]
    all_cols = FEATURES + [TARGET]
    feature_data = df_ready[all_cols].values[-WINDOW:]

    # Pad if still shorter than WINDOW after tiering
    if len(feature_data) < WINDOW:
        pad_rows = WINDOW - len(feature_data)
        pad = np.tile(feature_data[0], (pad_rows, 1))
        feature_data = np.vstack([pad, feature_data])

    scaled = scaler.transform(feature_data)
    X = np.expand_dims(scaled[:, : len(FEATURES)], axis=0)  # (1, WINDOW, n_features)

    # ── Step 6: Monte Carlo Dropout inference (CPU-heavy — run in thread) ──────
    raw_aqi, p90_aqi, std_aqi = await asyncio.to_thread(mc_predict, X)

    # ── Step 7: RMSE safety buffer ────────────────────────────────────────────
    rmse = _state["metadata"].get("rmse", 15.0)
    # Cap the buffer: when model RMSE is large (e.g. 83), adding it raw causes
    # severe over-prediction. Cap at 15.0 AQI points.
    rmse_buffer = min(rmse, 15.0)
    adjusted_aqi = raw_aqi + rmse_buffer  # use p50 (median) + capped buffer

    # Extract latest pollutant context for the XGBoost health classifier
    latest_pollutants = {}
    if df_ready is not None and not df_ready.empty:
        latest_row = df_ready.iloc[-1]
        latest_pollutants = {
            "pm25": latest_row.get("pm25", 0.0),
            "pm10": latest_row.get("pm10", 0.0),
            "no2": latest_row.get("no2", 0.0),
            "o3": latest_row.get("o3", 0.0),
            "co": latest_row.get("co", 0.0),
            "temperature": latest_row.get("temperature", 25.0),
            "humidity": latest_row.get("humidity", 60.0),
        }

    patient_name = user.get("name", "Patient") if user else "Patient"
    tier, message, precautions, risk_explanation = classify_aqi(
        adjusted_aqi,
        condition=condition,
        severity=severity,
        pollutants=latest_pollutants,
        symptoms=symptoms,
        personalized_issue=personalized_issue,
        patient_name=patient_name
    )

    # ── Send Alert if Risk is High/Critical OR Custom Threshold Crossed ──────
    should_alert = False
    alert_reason = ""
    
    # Check if user's custom threshold is crossed
    user_threshold = user.get("alert_threshold", 100) if user else 100
    if adjusted_aqi >= user_threshold:
        should_alert = True
        alert_reason = f"AQI {round(adjusted_aqi)} crossed your threshold ({user_threshold})"
    
    # Or if calculated risk tier is high/critical
    if tier.lower() in ["high risk", "critical"]:
        should_alert = True
        if not alert_reason:
            alert_reason = f"Health risk tier: {tier}"
    
    if should_alert and user:
        try:
            from alerts import send_whatsapp, send_email
            
            phone = user.get("phone")
            email = user.get("email")
            
            # Send WhatsApp if phone available
            if phone:
                whatsapp_text = f"🚨 Pranarakshak Alert\n\n{alert_reason}\n\n{message}\n\nTop precaution: {precautions[0]['text'] if precautions else 'Stay safe'}"
                whatsapp_status, whatsapp_id = send_whatsapp(phone, whatsapp_text)
                
                # Log to database
                await asyncio.to_thread(
                    db.supabase.table("alerts_log").insert({
                        "user_id": payload.user_id,
                        "alert_tier": tier,
                        "alert_message": message,
                        "aqi_value": round(adjusted_aqi, 1),
                        "channel": "whatsapp",
                        "recipient": phone,
                        "status": whatsapp_status,
                        "provider_message_id": whatsapp_id,
                    }).execute
                )
            
            # Send Email if email available
            if email:
                subject = f"🚨 AQI Alert: {tier}"
                html_body = f"""
<!DOCTYPE html>
<html>
<head><style>body{{font-family:Arial,sans-serif;}}h2{{color:#d32f2f;}}</style></head>
<body>
<h2>{tier} - AQI Alert</h2>
<p><strong>{message}</strong></p>
<h3>Precautions:</h3>
<ul>
{''.join(f"<li>{p['text']}</li>" for p in precautions[:5])}
</ul>
<p><a href="https://pranarakshak-six.vercel.app/dashboard?user_id={payload.user_id}">View Dashboard</a></p>
</body>
</html>
"""
                email_status, email_id = send_email(email, subject, html_body)
                
                # Log to database
                await asyncio.to_thread(
                    db.supabase.table("alerts_log").insert({
                        "user_id": payload.user_id,
                        "alert_tier": tier,
                        "alert_message": message,
                        "aqi_value": round(adjusted_aqi, 1),
                        "channel": "email",
                        "recipient": email,
                        "status": email_status,
                        "provider_message_id": email_id,
                    }).execute
                )
        except Exception as e:
            logger.error(f"Failed to send alert: {e}")
            # Don't fail the prediction if alert fails

    source_label = quality_tier if quality_tier != "live" else fetch_source
    display_aqi_for_tier = live_aqi if live_aqi is not None else adjusted_aqi
    
    trend = "stable"
    if live_aqi is not None:
        if adjusted_aqi > live_aqi + 15:
            trend = "worsening"
        elif adjusted_aqi < live_aqi - 15:
            trend = "improving"

    return PredictionResponse(
        user_id=payload.user_id,
        current_aqi=round(live_aqi, 1) if live_aqi is not None else None,
        air_quality_tier=naqi_air_quality_tier(display_aqi_for_tier),
        predicted_aqi_raw=round(raw_aqi, 1),
        predicted_aqi_adjusted=round(adjusted_aqi, 1),
        rmse_buffer=round(rmse_buffer, 1),
        prediction_confidence=round(std_aqi, 2),
        prediction_source=source_label,
        alert_tier=tier,
        alert_message=message,
        precautions=[PrecautionItem(**p) for p in precautions],
        risk_explanation=RiskExplanation(**risk_explanation),
        safe_hours=get_safe_hours(forecast_time),
        aqi_trend=trend,
        timestamp=now_str,
        forecast_for=forecast_time.isoformat(),
    )


@app.post("/train", tags=["System"])
def trigger_training(background_tasks: BackgroundTasks) -> dict:
    """
    Trigger model retraining in the background.
    The /health endpoint will reflect the new model once training completes.
    """

    def _run_training():
        try:
            import train as training_module
            training_module.train()
            _load_artifacts()
            logger.info("Background retraining complete — artifacts reloaded.")
        except Exception as exc:
            logger.error(f"Background training failed: {exc}")

    background_tasks.add_task(_run_training)
    return {
        "status": "training_started",
        "message": "Model retraining started in the background. Poll GET /health for updated RMSE.",
    }


@app.post("/register", tags=["Users"])
def register_user(payload: RegisterRequest):
    """Register a new user and store their profile in the database."""
    import bcrypt
    from postgrest.exceptions import APIError as PostgRESTError

    user_data = {
        "name": payload.name,
        "phone": payload.phone,
        "email": str(payload.email) if payload.email else None,
        "condition": payload.condition,
        "severity": payload.severity,
        "last_known_lat": payload.lat,
        "last_known_lon": payload.lon,
        "symptoms": payload.symptoms,
        "personalized_issue": payload.personalized_issue,
        "alert_threshold": payload.alert_threshold or 100,
        "active": True,
    }

    # Hash password before storage — never store plaintext
    if payload.password:
        user_data["password_hash"] = bcrypt.hashpw(
            payload.password.encode("utf-8"), bcrypt.gensalt(rounds=12)
        ).decode("utf-8")

    if payload.lat is not None and payload.lon is not None:
        user_data["location_consent"] = True
        user_data["location_updated_at"] = datetime.now(timezone.utc).isoformat()

    try:
        user = db.create_user(user_data)
        if not user:
            raise HTTPException(status_code=500, detail="Failed to create user record.")
        return {"message": "User registered successfully", "user_id": user["id"]}
    except PostgRESTError as exc:
        code = getattr(exc, "code", None)
        details = getattr(exc, "details", None)
        if code is None:
            error_info = exc.args[0] if exc.args else {}
            if isinstance(error_info, dict):
                code = error_info.get("code", "")
                details = error_info.get("details", "")
            else:
                exc_str = str(exc)
                code = "23505" if "23505" in exc_str else ""
                details = exc_str
        if str(code) == "23505":
            detail_str = str(details or str(exc))
            if "email" in detail_str:
                raise HTTPException(status_code=409, detail="This email address is already registered.")
            elif "phone" in detail_str:
                raise HTTPException(status_code=409, detail="This phone number is already registered.")
            else:
                raise HTTPException(status_code=409, detail="An account with these details already exists.")
        logger.error(f"PostgREST error registering user: {exc}")
        raise HTTPException(status_code=500, detail="Database error during registration.")
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error registering user: {exc}")
        raise HTTPException(status_code=500, detail="Database error during registration.")


@app.post("/login", tags=["Users"])
def login_user(payload: LoginRequest):
    """
    Authenticate a user by Email/Phone + password, or by bare UUID (legacy dashboard lookup).

    Flow:
      1. UUID  → no password needed — used by dashboard auto-load from localStorage
      2. Email → password required  — bcrypt.checkpw against stored hash
      3. Phone → password required  — same as email
    """
    import bcrypt

    identifier = payload.identifier.strip()
    user: Optional[dict] = None
    requires_password = True

    # ── 1. UUID lookup (no password required — used internally) ───────────────
    try:
        from uuid import UUID as _UUID
        _UUID(identifier)          # raises ValueError if not a valid UUID
        user = db.get_user_by_id(identifier)
        requires_password = False  # UUID lookup is trusted — no password gate
    except ValueError:
        pass

    # ── 2. Email lookup ────────────────────────────────────────────────────────
    if user is None and "@" in identifier:
        user = db.get_user_by_email(identifier)

    # ── 3. Phone lookup ────────────────────────────────────────────────────────
    if user is None:
        user = db.get_user_by_phone(identifier)

    # ── User not found ─────────────────────────────────────────────────────────
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid credentials.")

    # ── Password verification (email / phone flows) ────────────────────────────
    if requires_password:
        if not payload.password:
            raise HTTPException(status_code=422, detail="Password is required.")

        stored_hash = user.get("password_hash")
        if not stored_hash:
            # Account exists but has no password — likely OAuth-only registration
            raise HTTPException(
                status_code=400,
                detail="This account was created with Google. Please use 'Continue with Google'."
            )

        # Use constant-time comparison to prevent timing attacks
        password_ok = bcrypt.checkpw(
            payload.password.encode("utf-8"),
            stored_hash.encode("utf-8"),
        )
        if not password_ok:
            raise HTTPException(status_code=401, detail="Invalid credentials.")

    return {"message": "Login successful", "user_id": user["id"]}


@app.post("/update-location", tags=["Users"])
def update_location(payload: LocationUpdateRequest):
    """Update user's current GPS location."""
    try:
        db.update_user_location(
            user_id=payload.user_id,
            lat=payload.lat,
            lon=payload.lon,
            city=payload.city
        )
        return {"message": "Location updated successfully"}
    except Exception as exc:
        logger.error(f"Error updating location: {exc}")
        raise HTTPException(status_code=500, detail="Database error during location update.")


@app.get("/users/{user_id}", tags=["Users"])
def get_user(user_id: str):
    """Retrieve user profile by ID."""
    try:
        user = db.get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found.")
        return user
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error fetching user {user_id}: {exc}")
        raise HTTPException(status_code=500, detail="Database error while fetching user profile.")


@app.post("/alerts/check", tags=["Alerts"])
async def trigger_alerts_check(background_tasks: BackgroundTasks) -> dict:
    """Trigger the background alert check cycle for all active users."""
    from worker import run_alert_check_cycle
    background_tasks.add_task(run_alert_check_cycle)
    return {
        "status": "check_started",
        "message": "Vulnerability scanning loop has been triggered in the background."
    }


@app.get("/alerts/auto-check", tags=["Alerts"])
async def auto_alerts_check() -> dict:
    """
    Auto-trigger alert checks (designed for external cron services like cron-job.org).
    This endpoint runs the alert cycle and returns results immediately.
    """
    try:
        logger.info("🔔 Auto alert check triggered via GET endpoint")
        from worker import run_alert_check_cycle
        results = await run_alert_check_cycle()
        return {
            "status": "completed",
            "message": "Alert check cycle completed successfully",
            "results": results
        }
    except Exception as e:
        logger.error(f"Auto alert check failed: {e}")
        return {
            "status": "failed", 
            "message": f"Alert check failed: {str(e)}",
            "results": None
        }


@app.get("/debug/aqi-accuracy/{user_id}", tags=["Debug"])
async def debug_aqi_accuracy(user_id: str) -> dict:
    """
    🎯 AQI Accuracy Analyzer - See exactly which sources and stations are used.
    Shows all available AQI readings with reliability scores for troubleshooting.
    """
    try:
        import asyncio
        from accurate_aqi import get_accurate_current_aqi
        
        # Get user location
        user = await asyncio.to_thread(db.get_user_by_id, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        lat = float(user["last_known_lat"]) if user["last_known_lat"] is not None else 17.385044
        lon = float(user["last_known_lon"]) if user["last_known_lon"] is not None else 78.486671
        
        # Get accurate AQI with full transparency
        accurate_aqi, accuracy_report = await asyncio.to_thread(get_accurate_current_aqi, lat, lon)
        
        return {
            "user_location": {"lat": lat, "lon": lon, "is_default": user["last_known_lat"] is None},
            "accurate_aqi": accurate_aqi,
            "accuracy_report": accuracy_report,
            "recommendation": "Click 'Update Location' button to get AQI for your exact coordinates" if user["last_known_lat"] is None else "Location-specific AQI data"
        }
        
    except Exception as e:
        logger.error(f"AQI accuracy debug failed: {e}")
        raise HTTPException(status_code=500, detail=f"Debug failed: {str(e)}")


@app.get("/debug/data-sources/{user_id}", tags=["Debug"])
async def debug_data_sources(user_id: str) -> dict:
    """
    Debug endpoint to see exactly which AQI data sources and stations are being used.
    Shows station names, distances, and raw AQI values for troubleshooting accuracy.
    """
    try:
        import asyncio
        from data_fetcher import get_readings_for_location
        
        # Get user location
        user = await asyncio.to_thread(db.get_user_by_id, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        lat = float(user["last_known_lat"]) if user["last_known_lat"] is not None else 17.385044
        lon = float(user["last_known_lon"]) if user["last_known_lon"] is not None else 78.486671
        
        # Get data sources
        df, source, live_aqi = await asyncio.to_thread(get_readings_for_location, lat, lon)
        
        # Also test individual sources for comparison
        debug_info = {
            "user_coordinates": {"lat": lat, "lon": lon},
            "primary_source": source,
            "live_current_aqi": live_aqi,
            "data_available": df is not None,
            "rows_count": len(df) if df is not None else 0,
        }
        
        # Test WAQI directly for more details
        try:
            import httpx
            waqi_url = f"https://api.waqi.info/feed/geo:{lat};{lon}/"
            with httpx.Client(timeout=10) as client:
                resp = client.get(waqi_url, params={"token": os.getenv("WAQI_TOKEN")})
                if resp.status_code == 200:
                    waqi_data = resp.json()
                    if waqi_data.get("status") == "ok":
                        station = waqi_data["data"]
                        debug_info["waqi_station"] = {
                            "name": station.get("city", {}).get("name"),
                            "coordinates": station.get("city", {}).get("geo"),
                            "aqi": station.get("aqi"),
                            "pollution": {k: v.get("v") for k, v in station.get("iaqi", {}).items()},
                            "last_update": station.get("time", {}).get("s"),
                        }
        except Exception as e:
            debug_info["waqi_error"] = str(e)
        
        return debug_info
        
    except Exception as e:
        logger.error(f"Debug data sources failed: {e}")
        raise HTTPException(status_code=500, detail=f"Debug failed: {str(e)}")


@app.get("/indoor-recommendations/{user_id}", tags=["Smart Features"])
async def get_indoor_recommendations_api(user_id: str) -> dict:
    """
    🏠 Smart Indoor Air Quality Recommendations
    Provides personalized advice on when to open windows, run air purifiers, etc.
    """
    try:
        import asyncio
        from indoor_recommendations import get_indoor_recommendations, get_24h_indoor_forecast, get_optimal_ventilation_windows
        from data_fetcher import get_readings_for_location
        
        # Get user details
        user = await asyncio.to_thread(db.get_user_by_id, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Handle missing location gracefully - use default Hyderabad coordinates
        lat = float(user["last_known_lat"]) if user["last_known_lat"] is not None else 17.385044
        lon = float(user["last_known_lon"]) if user["last_known_lon"] is not None else 78.486671
        condition = user.get("condition", "other")
        severity = user.get("severity", "moderate")
        
        # Get current AQI
        df, _, current_aqi = await asyncio.to_thread(get_readings_for_location, lat, lon)
        current_aqi = current_aqi or 100
        
        # Generate recommendations
        recommendations = get_indoor_recommendations(current_aqi, current_aqi, condition, severity)
        
        # Get 24h forecast
        forecast = await get_24h_indoor_forecast(lat, lon)
        optimal_times = get_optimal_ventilation_windows(forecast)
        
        return {
            "user_id": user_id,
            "current_aqi": round(current_aqi, 1),
            "recommendations": recommendations,
            "hourly_forecast": forecast,
            "optimal_ventilation_times": optimal_times,
            "generated_at": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Indoor recommendations failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate recommendations: {str(e)}")


@app.get("/users/{user_id}/alerts", tags=["Alerts"])
def get_user_alerts(user_id: str, limit: int = 20):
    """Retrieve historical alert log dispatches for a user."""
    try:
        alerts = db.get_user_alerts_log(user_id, limit=limit)
        return alerts
    except Exception as exc:
        logger.error(f"Error fetching alerts for user {user_id}: {exc}")
        raise HTTPException(status_code=500, detail="Database error while fetching alert history.")


# ═══════════════════════════════════════════════════════════════════════════════
# FEATURE 3: MEDICATION REMINDER INTEGRATION
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/medications", tags=["Smart Features"])
def add_medication(payload: MedicationRequest):
    """Add a medication reminder for a user."""
    try:
        # Validate user exists
        user = db.get_user_by_id(payload.user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Insert medication
        medication_id = db.add_medication(
            user_id=payload.user_id,
            medication_name=payload.medication_name,
            medication_type=payload.medication_type,
            dosage=payload.dosage,
            frequency=payload.frequency,
            custom_schedule=payload.custom_schedule or [],
            aqi_trigger=payload.aqi_trigger,
            condition_specific=payload.condition_specific
        )
        
        logger.info(f"Medication added for user {payload.user_id}: {payload.medication_name}")
        return {
            "status": "success",
            "medication_id": medication_id,
            "message": f"Medication '{payload.medication_name}' added successfully"
        }
    except Exception as exc:
        logger.error(f"Error adding medication: {exc}")
        raise HTTPException(status_code=500, detail=f"Failed to add medication: {str(exc)}")


@app.get("/users/{user_id}/medications", tags=["Smart Features"])
def get_user_medications(user_id: str):
    """Get all medications for a user."""
    try:
        user = db.get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        medications = db.get_user_medications(user_id)
        return {
            "user_id": user_id,
            "medications": medications,
            "count": len(medications)
        }
    except Exception as exc:
        logger.error(f"Error fetching medications for user {user_id}: {exc}")
        raise HTTPException(status_code=500, detail="Failed to fetch medications")


@app.put("/medications/{medication_id}", tags=["Smart Features"])
def update_medication(medication_id: str, payload: MedicationRequest):
    """Update a medication."""
    try:
        success = db.update_medication(
            medication_id=medication_id,
            medication_name=payload.medication_name,
            medication_type=payload.medication_type,
            dosage=payload.dosage,
            frequency=payload.frequency,
            custom_schedule=payload.custom_schedule or [],
            aqi_trigger=payload.aqi_trigger,
            condition_specific=payload.condition_specific
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Medication not found")
        
        return {"status": "success", "message": "Medication updated successfully"}
    except Exception as exc:
        logger.error(f"Error updating medication {medication_id}: {exc}")
        raise HTTPException(status_code=500, detail="Failed to update medication")


@app.delete("/medications/{medication_id}", tags=["Smart Features"])
def delete_medication(medication_id: str):
    """Delete a medication."""
    try:
        success = db.delete_medication(medication_id)
        if not success:
            raise HTTPException(status_code=404, detail="Medication not found")
        
        return {"status": "success", "message": "Medication deleted successfully"}
    except Exception as exc:
        logger.error(f"Error deleting medication {medication_id}: {exc}")
        raise HTTPException(status_code=500, detail="Failed to delete medication")


@app.post("/medications/check-reminders/{user_id}", tags=["Smart Features"])
async def check_medication_reminders(user_id: str):
    """Check if medication reminders should be sent based on current AQI."""
    try:
        import asyncio
        
        user = await asyncio.to_thread(db.get_user_by_id, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get user's current location and AQI
        lat, lon = user.get("last_known_lat"), user.get("last_known_lon")
        if not lat or not lon:
            return {"status": "skipped", "reason": "No location available"}
        
        # Get current AQI using accurate system
        from accurate_aqi import get_accurate_current_aqi
        try:
            current_aqi, accuracy_report = await asyncio.to_thread(get_accurate_current_aqi, lat, lon)
        except Exception:
            # Fallback to prediction endpoint
            from data_fetcher import get_readings_for_location
            df, fetch_source, fallback_live_aqi = await asyncio.to_thread(get_readings_for_location, lat, lon)
            current_aqi = fallback_live_aqi or 100
        
        # Get user's medications
        medications = await asyncio.to_thread(db.get_user_medications, user_id)
        
        reminders_sent = []
        for med in medications:
            # Check if medication should trigger based on AQI
            aqi_trigger = med.get("aqi_trigger")
            if aqi_trigger and current_aqi >= aqi_trigger:
                # Check if reminder already sent recently (within 6 hours)
                recent_reminder = await asyncio.to_thread(
                    db.check_recent_medication_reminder, 
                    med["id"], hours=6
                )
                
                if not recent_reminder:
                    # Send medication reminder
                    reminder_sent = await send_medication_reminder(user, med, current_aqi)
                    if reminder_sent:
                        reminders_sent.append({
                            "medication": med["medication_name"],
                            "trigger_aqi": aqi_trigger,
                            "current_aqi": current_aqi
                        })
        
        return {
            "status": "completed",
            "user_id": user_id,
            "current_aqi": current_aqi,
            "reminders_sent": reminders_sent,
            "count": len(reminders_sent)
        }
        
    except Exception as exc:
        logger.error(f"Error checking medication reminders for {user_id}: {exc}")
        raise HTTPException(status_code=500, detail="Failed to check medication reminders")


# ═══════════════════════════════════════════════════════════════════════════════
# FEATURE 4: FAMILY GROUP ALERTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/family-groups", tags=["Smart Features"])
def create_family_group(payload: FamilyGroupRequest):
    """Create a new family group."""
    try:
        # Validate creator exists
        user = db.get_user_by_id(payload.creator_user_id)
        if not user:
            raise HTTPException(status_code=404, detail="Creator user not found")
        
        group_id = db.create_family_group(
            group_name=payload.group_name,
            creator_user_id=payload.creator_user_id,
            description=payload.description,
            shared_alert_threshold=payload.shared_alert_threshold,
            auto_share_location=payload.auto_share_location,
            emergency_mode=payload.emergency_mode
        )
        
        # Add creator as admin member
        db.add_family_member(group_id, payload.creator_user_id, role="admin")
        
        logger.info(f"Family group created: {payload.group_name} by user {payload.creator_user_id}")
        return {
            "status": "success",
            "group_id": group_id,
            "message": f"Family group '{payload.group_name}' created successfully"
        }
    except Exception as exc:
        logger.error(f"Error creating family group: {exc}")
        raise HTTPException(status_code=500, detail=f"Failed to create family group: {str(exc)}")


@app.post("/family-groups/{group_id}/members", tags=["Smart Features"])
def add_family_member(group_id: str, user_id: str, role: str = "member"):
    """Add a member to a family group."""
    try:
        # Validate group exists
        group = db.get_family_group(group_id)
        if not group:
            raise HTTPException(status_code=404, detail="Family group not found")
        
        # Validate user exists
        user = db.get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Add member
        success = db.add_family_member(group_id, user_id, role)
        if not success:
            raise HTTPException(status_code=400, detail="User is already a member of this group")
        
        return {
            "status": "success",
            "message": f"User added to family group as {role}"
        }
    except Exception as exc:
        logger.error(f"Error adding family member: {exc}")
        raise HTTPException(status_code=500, detail="Failed to add family member")


@app.get("/users/{user_id}/family-groups", tags=["Smart Features"])
def get_user_family_groups(user_id: str):
    """Get all family groups for a user."""
    try:
        user = db.get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        groups = db.get_user_family_groups(user_id)
        return {
            "user_id": user_id,
            "family_groups": groups,
            "count": len(groups)
        }
    except Exception as exc:
        logger.error(f"Error fetching family groups for user {user_id}: {exc}")
        raise HTTPException(status_code=500, detail="Failed to fetch family groups")


@app.get("/family-groups/{group_id}/members", tags=["Smart Features"])
def get_family_group_members(group_id: str):
    """Get all members of a family group."""
    try:
        group = db.get_family_group(group_id)
        if not group:
            raise HTTPException(status_code=404, detail="Family group not found")
        
        members = db.get_family_group_members(group_id)
        return {
            "group_id": group_id,
            "group_name": group["group_name"],
            "members": members,
            "count": len(members)
        }
    except Exception as exc:
        logger.error(f"Error fetching family group members for {group_id}: {exc}")
        raise HTTPException(status_code=500, detail="Failed to fetch family group members")


@app.post("/family-groups/{group_id}/alert", tags=["Smart Features"])
async def send_family_alert(group_id: str, triggered_by_user: str, alert_type: str, message: str):
    """Send alert to all family group members."""
    try:
        import asyncio
        
        # Validate group exists
        group = await asyncio.to_thread(db.get_family_group, group_id)
        if not group:
            raise HTTPException(status_code=404, detail="Family group not found")
        
        # Get all active members
        members = await asyncio.to_thread(db.get_family_group_members, group_id)
        
        notifications_sent = 0
        for member in members:
            if member["user_id"] != triggered_by_user and member["notifications_enabled"]:
                # Send notification to family member
                success = await send_family_notification(member, message, alert_type)
                if success:
                    notifications_sent += 1
        
        # Log the family alert
        await asyncio.to_thread(db.log_family_alert, 
                              group_id=group_id,
                              triggered_by_user=triggered_by_user,
                              alert_type=alert_type,
                              message=message,
                              members_notified=notifications_sent)
        
        return {
            "status": "success",
            "group_id": group_id,
            "alert_type": alert_type,
            "members_notified": notifications_sent,
            "message": "Family alert sent successfully"
        }
        
    except Exception as exc:
        logger.error(f"Error sending family alert: {exc}")
        raise HTTPException(status_code=500, detail="Failed to send family alert")


# ═══════════════════════════════════════════════════════════════════════════════
# FEATURE 8: EMERGENCY CONTACT AUTO-ALERT
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/emergency-contacts", tags=["Smart Features"])
def add_emergency_contact(payload: EmergencyContactRequest):
    """Add an emergency contact for a user."""
    try:
        # Validate user exists
        user = db.get_user_by_id(payload.user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        contact_id = db.add_emergency_contact(
            user_id=payload.user_id,
            contact_name=payload.contact_name,
            relationship=payload.relationship,
            phone=payload.phone,
            email=payload.email,
            priority=payload.priority,
            notify_on_critical=payload.notify_on_critical,
            notify_on_missed_checkin=payload.notify_on_missed_checkin
        )
        
        logger.info(f"Emergency contact added for user {payload.user_id}: {payload.contact_name}")
        return {
            "status": "success",
            "contact_id": contact_id,
            "message": f"Emergency contact '{payload.contact_name}' added successfully"
        }
    except Exception as exc:
        logger.error(f"Error adding emergency contact: {exc}")
        raise HTTPException(status_code=500, detail=f"Failed to add emergency contact: {str(exc)}")


@app.get("/users/{user_id}/emergency-contacts", tags=["Smart Features"])
def get_user_emergency_contacts(user_id: str):
    """Get all emergency contacts for a user."""
    try:
        user = db.get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        contacts = db.get_user_emergency_contacts(user_id)
        return {
            "user_id": user_id,
            "emergency_contacts": contacts,
            "count": len(contacts)
        }
    except Exception as exc:
        logger.error(f"Error fetching emergency contacts for user {user_id}: {exc}")
        raise HTTPException(status_code=500, detail="Failed to fetch emergency contacts")


@app.put("/emergency-contacts/{contact_id}", tags=["Smart Features"])
def update_emergency_contact(contact_id: str, payload: EmergencyContactRequest):
    """Update an emergency contact."""
    try:
        success = db.update_emergency_contact(
            contact_id=contact_id,
            contact_name=payload.contact_name,
            relationship=payload.relationship,
            phone=payload.phone,
            email=payload.email,
            priority=payload.priority,
            notify_on_critical=payload.notify_on_critical,
            notify_on_missed_checkin=payload.notify_on_missed_checkin
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Emergency contact not found")
        
        return {"status": "success", "message": "Emergency contact updated successfully"}
    except Exception as exc:
        logger.error(f"Error updating emergency contact {contact_id}: {exc}")
        raise HTTPException(status_code=500, detail="Failed to update emergency contact")


@app.delete("/emergency-contacts/{contact_id}", tags=["Smart Features"])
def delete_emergency_contact(contact_id: str):
    """Delete an emergency contact."""
    try:
        success = db.delete_emergency_contact(contact_id)
        if not success:
            raise HTTPException(status_code=404, detail="Emergency contact not found")
        
        return {"status": "success", "message": "Emergency contact deleted successfully"}
    except Exception as exc:
        logger.error(f"Error deleting emergency contact {contact_id}: {exc}")
        raise HTTPException(status_code=500, detail="Failed to delete emergency contact")


@app.post("/emergency-contacts/notify/{user_id}", tags=["Smart Features"])
async def trigger_emergency_notifications(user_id: str, alert_tier: str, current_aqi: int):
    """Trigger emergency contact notifications for critical AQI events."""
    try:
        import asyncio
        
        user = await asyncio.to_thread(db.get_user_by_id, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Only trigger for critical alerts
        if alert_tier.lower() != "critical":
            return {
                "status": "skipped", 
                "reason": f"Alert tier '{alert_tier}' is not critical"
            }
        
        # Get emergency contacts
        contacts = await asyncio.to_thread(db.get_user_emergency_contacts, user_id)
        
        notifications_sent = 0
        for contact in contacts:
            if contact["notify_on_critical"]:
                success = await send_emergency_notification(user, contact, current_aqi)
                if success:
                    notifications_sent += 1
        
        return {
            "status": "completed",
            "user_id": user_id,
            "alert_tier": alert_tier,
            "current_aqi": current_aqi,
            "notifications_sent": notifications_sent,
            "message": f"Emergency notifications sent to {notifications_sent} contacts"
        }
        
    except Exception as exc:
        logger.error(f"Error triggering emergency notifications for {user_id}: {exc}")
        raise HTTPException(status_code=500, detail="Failed to trigger emergency notifications")


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS FOR NEW FEATURES
# ═══════════════════════════════════════════════════════════════════════════════

async def send_medication_reminder(user: dict, medication: dict, current_aqi: int) -> bool:
    """Send medication reminder via WhatsApp/SMS."""
    try:
        from alerts import send_whatsapp
        
        phone = user.get("phone")
        if not phone:
            return False
        
        medication_name = medication["medication_name"]
        dosage = medication["dosage"]
        user_name = user.get("name", "Patient")
        
        message = f"""💊 MEDICATION REMINDER - Pranarakshak

Hello {user_name}!

High AQI Alert: {current_aqi} (Threshold: {medication['aqi_trigger']})

Please take your medication:
📋 {medication_name}
💉 Dosage: {dosage}

This will help protect your respiratory health during poor air quality conditions.

Take care and stay safe! 🌬️"""
        
        status, msg_id = send_whatsapp(phone, message)
        
        # Log the reminder
        if status == "sent":
            db.log_medication_reminder(
                medication_id=medication["id"],
                user_id=user["id"],
                reminder_type="aqi_triggered",
                aqi_at_time=current_aqi,
                message_sent=message,
                channel="whatsapp",
                status="sent"
            )
        
        logger.info(f"Medication reminder sent to {phone}: {status}")
        return status == "sent"
        
    except Exception as exc:
        logger.error(f"Error sending medication reminder: {exc}")
        return False


async def send_family_notification(member: dict, message: str, alert_type: str) -> bool:
    """Send notification to family group member."""
    try:
        from alerts import send_whatsapp
        
        # Get member's user details
        user = db.get_user_by_id(member["user_id"])
        if not user:
            return False
        
        phone = user.get("phone")
        if not phone:
            return False
        
        family_message = f"""👨‍👩‍👧‍👦 FAMILY ALERT - Pranarakshak

{message}

Alert Type: {alert_type.replace('_', ' ').title()}
Family Member: {user.get('name', 'Family Member')}

Please check on your family member and ensure they are safe.

Stay connected! 💙"""
        
        status, msg_id = send_whatsapp(phone, family_message)
        logger.info(f"Family notification sent to {phone}: {status}")
        return status == "sent"
        
    except Exception as exc:
        logger.error(f"Error sending family notification: {exc}")
        return False


async def send_emergency_notification(user: dict, contact: dict, current_aqi: int) -> bool:
    """Send emergency notification to emergency contact."""
    try:
        from alerts import send_whatsapp, send_email
        
        user_name = user.get("name", "Patient")
        contact_name = contact["contact_name"]
        relationship = contact["relationship"]
        
        emergency_message = f"""🚨 EMERGENCY ALERT - Pranarakshak

CRITICAL AIR QUALITY ALERT

Patient: {user_name}
Current AQI: {current_aqi} (CRITICAL LEVEL)

{user_name} is experiencing dangerous air quality conditions that pose immediate health risks for their respiratory condition.

As their emergency contact ({relationship}), please:
1. Check on {user_name} immediately
2. Ensure they are indoors with windows closed
3. Verify they have taken their rescue medications
4. Monitor for breathing difficulties

This is an automated emergency alert.

Emergency Contact: {contact_name}
Priority Level: {contact['priority']}

Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
        
        notifications_sent = False
        
        # Send WhatsApp if phone available
        if contact.get("phone"):
            status, msg_id = send_whatsapp(contact["phone"], emergency_message)
            if status == "sent":
                notifications_sent = True
        
        # Send Email if email available  
        if contact.get("email"):
            subject = f"🚨 EMERGENCY: Critical AQI Alert for {user_name}"
            html_message = emergency_message.replace('\n', '<br>')
            status, msg_id = send_email(contact["email"], subject, f"<html><body><pre>{html_message}</pre></body></html>")
            if status == "sent":
                notifications_sent = True
        
        logger.info(f"Emergency notification sent to {contact_name}: {notifications_sent}")
        return notifications_sent
        
    except Exception as exc:
        logger.error(f"Error sending emergency notification: {exc}")
        return False

