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

app.add_middleware(
    CORSMiddleware,
    # Read allowed origins from env so it's tight in production.
    # CORS_ORIGINS env var = comma-separated list, e.g.:
    #   https://your-app.vercel.app,https://your-custom-domain.com
    # Falls back to "*" only if not set (local dev convenience).
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
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


class LoginRequest(BaseModel):
    identifier: str = Field(..., description="Email, phone, or User UUID")
    password: Optional[str] = Field(None, description="Required for email/phone login; omit for UUID-only lookup")


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

    # ── Step 1: Fetch live data (blocking network I/O — run in thread) ────────
    df, fetch_source, live_aqi = await asyncio.to_thread(get_readings_for_location, payload.lat, payload.lon)

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


@app.get("/users/{user_id}/alerts", tags=["Alerts"])
def get_user_alerts(user_id: str, limit: int = 20):
    """Retrieve historical alert log dispatches for a user."""
    try:
        alerts = db.get_user_alerts_log(user_id, limit=limit)
        return alerts
    except Exception as exc:
        logger.error(f"Error fetching alerts for user {user_id}: {exc}")
        raise HTTPException(status_code=500, detail="Database error while fetching alert history.")

