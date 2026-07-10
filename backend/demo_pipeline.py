"""
demo_pipeline.py — End-to-End Model Linking Demo
=================================================
Demonstrates the full pipeline:
  1. LSTM (train.py)           → Predicts AQI 24h ahead
  2. XGBoost (train_risk_model.py) → Classifies health risk from predicted AQI
  3. Personalised Alert        → Condition-specific advice for the user

Uses the pre-trained artifacts (aqi_lstm.h5, scaler.pkl, risk_model.pkl)
to run inference on synthetic recent data and print personalised alerts
for multiple sample user profiles.

Run:
  python demo_pipeline.py
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone

import joblib
import numpy as np
import pandas as pd

# ─── Paths to Pre-Trained Artifacts ──────────────────────────────────────────
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))

MODEL_PATH = os.path.join(BACKEND_DIR, "aqi_lstm.h5")
SCALER_PATH = os.path.join(BACKEND_DIR, "scaler.pkl")
METADATA_PATH = os.path.join(BACKEND_DIR, "model_metadata.json")
RISK_MODEL_PATH = os.path.join(BACKEND_DIR, "risk_model.pkl")
RISK_ENCODER_PATH = os.path.join(BACKEND_DIR, "risk_label_encoder.pkl")

# ─── LSTM Config (must match train.py) ───────────────────────────────────────
WINDOW = 48
FEATURES = [
    "pm25", "pm10", "no2", "o3", "co",
    "temperature", "humidity", "wind_speed",
    "hour_sin", "hour_cos", "day_sin", "day_cos",
    "pm25_lag1", "pm25_lag6", "pm25_lag24",
    "pm25_rolling6", "pm25_rolling24",
]
TARGET = "aqi"
ALL_COLS = FEATURES + [TARGET]

# ─── Risk Model Config (must match train_risk_model.py) ──────────────────────
RISK_FEATURES = [
    "aqi", "pm25", "pm10", "no2", "o3", "co", "temperature", "humidity",
    "cond_copd", "cond_asthma", "cond_both", "cond_other",
    "sev_mild", "sev_moderate", "sev_severe",
]
CLASS_NAMES = ["safe", "caution", "high_risk", "critical"]

# ─── Alert Templates ─────────────────────────────────────────────────────────
ALERT_TEMPLATES = {
    "safe": {
        "emoji": "✅",
        "label": "Good",
        "color": "\033[92m",     # green
        "base_message": "Air quality is Good. Safe for outdoor activity.",
        "base_precautions": [
            "Enjoy outdoor activities — no special precautions needed today.",
        ],
    },
    "caution": {
        "emoji": "🟡",
        "label": "Satisfactory",
        "color": "\033[93m",     # yellow
        "base_message": "Air quality is Satisfactory. Monitor your symptoms.",
        "base_precautions": [
            "Avoid prolonged strenuous outdoor activity.",
            "Keep your rescue inhaler accessible at all times.",
        ],
    },
    "high_risk": {
        "emoji": "🟠",
        "label": "Moderate",
        "color": "\033[33m",     # orange
        "base_message": "Moderate air quality. Extra caution advised.",
        "base_precautions": [
            "Reduce outdoor time, especially during peak hours (8–10 AM, 6–8 PM).",
            "Keep windows closed during peak pollution hours.",
            "Run air purifier indoors if available.",
            "Keep rescue inhaler accessible at all times.",
            "Watch for early symptoms: tightness, wheezing, shortness of breath.",
        ],
    },
    "critical": {
        "emoji": "🔴",
        "label": "Poor / Severe",
        "color": "\033[91m",     # red
        "base_message": "Poor air quality. Significant health risk.",
        "base_precautions": [
            "Avoid ALL outdoor activities. Stay strictly indoors.",
            "Keep all windows and doors closed.",
            "Wear N95/N99 mask if outdoor activity is unavoidable.",
            "Take prescribed preventive medication as advised by your doctor.",
            "Keep rescue inhaler and nebulizer ready and accessible.",
            "Monitor symptoms closely — contact your doctor if symptoms worsen.",
            "Alert your caregiver or a family member about today's air quality.",
        ],
    },
}

CONDITION_PRECAUTIONS = {
    "copd": [
        "Take your long-acting bronchodilator (LABA/LAMA) as prescribed.",
        "Keep supplemental oxygen accessible if prescribed.",
        "Avoid exertion — even mild activity increases oxygen demand.",
    ],
    "asthma": [
        "Ensure your preventer (ICS) inhaler is taken — do not skip doses.",
        "Use your peak flow meter and log readings.",
        "Identify and avoid any additional triggers (dust, pollen, smoke).",
    ],
    "both": [
        "Take your long-acting bronchodilator (LABA/LAMA) as prescribed.",
        "Keep supplemental oxygen accessible if prescribed.",
        "Ensure your preventer (ICS) inhaler is taken — do not skip doses.",
        "Use your peak flow meter and log readings.",
    ],
}

# ─── Sample User Profiles ───────────────────────────────────────────────────
SAMPLE_USERS = [
    {
        "name": "Priya Sharma",
        "age": 34,
        "condition": "asthma",
        "severity": "moderate",
        "city": "Delhi",
        "symptoms": ["wheezing at night", "chest tightness during exercise"],
    },
    {
        "name": "Rajesh Kumar",
        "age": 62,
        "condition": "copd",
        "severity": "severe",
        "city": "Delhi",
        "symptoms": ["chronic cough", "breathlessness on minimal exertion", "frequent hospital visits"],
    },
    {
        "name": "Ananya Patel",
        "age": 28,
        "condition": "other",
        "severity": "mild",
        "city": "Mumbai",
        "symptoms": ["occasional headache on high pollution days"],
    },
    {
        "name": "Mohammed Iqbal",
        "age": 55,
        "condition": "both",
        "severity": "severe",
        "city": "Lucknow",
        "symptoms": ["severe breathlessness", "nocturnal asthma attacks", "on supplemental O₂"],
    },
]

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"


# ─── Step 1: Load Pre-Trained Models ────────────────────────────────────────

def load_models():
    """Load the LSTM, scaler, and XGBoost risk classifier from disk."""
    print(f"\n{'═' * 72}")
    print(f"  📦  LOADING PRE-TRAINED MODEL ARTIFACTS")
    print(f"{'═' * 72}")

    # Suppress TF warnings
    os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
    import tensorflow as tf
    tf.get_logger().setLevel("ERROR")

    artifacts = {}

    # LSTM model
    if not os.path.exists(MODEL_PATH):
        print(f"  ❌  LSTM model not found at {MODEL_PATH}")
        print(f"      Run: python train.py")
        sys.exit(1)
    artifacts["lstm_model"] = tf.keras.models.load_model(MODEL_PATH, compile=False)
    print(f"  ✅  LSTM model loaded           ← aqi_lstm.h5")

    # Scaler
    if not os.path.exists(SCALER_PATH):
        print(f"  ❌  Scaler not found at {SCALER_PATH}")
        sys.exit(1)
    artifacts["scaler"] = joblib.load(SCALER_PATH)
    print(f"  ✅  MinMaxScaler loaded          ← scaler.pkl")

    # Metadata
    if os.path.exists(METADATA_PATH):
        with open(METADATA_PATH) as f:
            artifacts["metadata"] = json.load(f)
        rmse = artifacts["metadata"].get("rmse", "N/A")
        print(f"  ✅  LSTM metadata loaded         ← model_metadata.json (RMSE: {rmse:.2f})")
    else:
        artifacts["metadata"] = {"rmse": 15.0}
        print(f"  ⚠️  Metadata not found — using default RMSE=15.0")

    # XGBoost risk classifier
    if not os.path.exists(RISK_MODEL_PATH):
        print(f"  ❌  Risk model not found at {RISK_MODEL_PATH}")
        print(f"      Run: python train_risk_model.py")
        sys.exit(1)
    artifacts["risk_model"] = joblib.load(RISK_MODEL_PATH)
    print(f"  ✅  XGBoost risk classifier      ← risk_model.pkl")

    if os.path.exists(RISK_ENCODER_PATH):
        artifacts["risk_encoder"] = joblib.load(RISK_ENCODER_PATH)
        print(f"  ✅  Label encoder loaded         ← risk_label_encoder.pkl")

    print(f"{'─' * 72}")
    print(f"  All artifacts loaded. Pipeline ready.\n")
    return artifacts


# ─── Step 2: Simulate Recent AQI Data (48h window) ──────────────────────────

def simulate_recent_data(base_aqi: float = 180.0, city: str = "Delhi") -> pd.DataFrame:
    """
    Simulate 48 hours of recent sensor data to feed into the LSTM.
    In production, this comes from OpenAQ / OWM APIs via data_fetcher.py.
    """
    np.random.seed(42)
    now = datetime.now(timezone.utc)
    timestamps = [now - timedelta(hours=WINDOW - 1 - i) for i in range(WINDOW)]

    records = []
    for i, ts in enumerate(timestamps):
        h = ts.hour
        # Realistic diurnal pattern
        rush = (1.5 * np.exp(-((h - 8.5) ** 2) / 2.0)
                + 1.2 * np.exp(-((h - 19.0) ** 2) / 2.0) + 0.5)
        aqi = max(10, base_aqi * rush * 0.5 + np.random.normal(0, 12))
        pm25 = max(5, aqi * 0.6 + np.random.normal(0, 5))
        pm10 = max(10, pm25 * 1.8 + np.random.normal(0, 8))
        no2 = max(2, aqi * 0.25 + np.random.normal(0, 3))
        o3 = max(5, 35 + 20 * np.sin(h * np.pi / 12) + np.random.normal(0, 5))
        co = max(0.1, aqi * 0.08 + np.random.normal(0, 0.5))
        temp = 26 + 8 * np.sin((h - 6) * np.pi / 12) + np.random.normal(0, 2)
        humidity = min(100, max(10, 62 - 18 * np.sin((h - 6) * np.pi / 12) + np.random.normal(0, 5)))
        wind = abs(np.random.normal(7, 3))

        records.append({
            "timestamp": ts,
            "pm25": round(pm25, 2), "pm10": round(pm10, 2),
            "no2": round(no2, 2), "o3": round(o3, 2), "co": round(co, 2),
            "temperature": round(temp, 1), "humidity": round(humidity, 1),
            "wind_speed": round(wind, 1), "aqi": round(aqi, 1),
        })

    return pd.DataFrame(records)


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Apply the same feature engineering as train.py."""
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


# ─── Step 3: LSTM Prediction (AQI 24h Ahead) ────────────────────────────────

def predict_aqi_lstm(df: pd.DataFrame, artifacts: dict) -> dict:
    """
    Run the LSTM model on the 48-hour window to predict AQI 24 hours ahead.
    Uses Monte Carlo Dropout (5 passes for demo speed) for uncertainty.
    Returns predicted AQI (raw, adjusted) + pollutant context.
    """
    model = artifacts["lstm_model"]
    scaler = artifacts["scaler"]
    rmse = artifacts["metadata"].get("rmse", 15.0)

    df = engineer_features(df)

    for col in FEATURES:
        if col not in df.columns:
            df[col] = 0.0
    if TARGET not in df.columns:
        df[TARGET] = df.get("pm25", pd.Series([50.0])) * 1.5

    feature_data = df[ALL_COLS].values[-WINDOW:]
    if len(feature_data) < WINDOW:
        pad = np.tile(feature_data[0], (WINDOW - len(feature_data), 1))
        feature_data = np.vstack([pad, feature_data])

    scaled = scaler.transform(feature_data)
    X = np.expand_dims(scaled[:, :len(FEATURES)], axis=0)  # (1, 48, 17)

    # Monte Carlo Dropout — 5 forward passes with dropout active
    mc_samples = 5
    predictions_scaled = [
        float(model(X, training=True).numpy()[0][0]) for _ in range(mc_samples)
    ]

    p50 = float(np.median(predictions_scaled))
    p90 = float(np.percentile(predictions_scaled, 90))
    std = float(np.std(predictions_scaled))

    n_all = len(ALL_COLS)

    def inverse(val):
        dummy = np.zeros((1, n_all))
        dummy[0, -1] = val
        return float(scaler.inverse_transform(dummy)[0, -1])

    raw_aqi = inverse(p50)
    p90_aqi = inverse(p90)
    adjusted_aqi = max(0, p90_aqi + rmse)

    aqi_range = float(scaler.data_range_[-1]) if hasattr(scaler, "data_range_") else 400.0
    std_aqi = std * aqi_range

    # Extract latest pollutant context from the input data
    latest = df.iloc[-1]
    pollutant_context = {
        "pm25": float(latest.get("pm25", 0)),
        "pm10": float(latest.get("pm10", 0)),
        "no2": float(latest.get("no2", 0)),
        "o3": float(latest.get("o3", 0)),
        "co": float(latest.get("co", 0)),
        "temperature": float(latest.get("temperature", 25)),
        "humidity": float(latest.get("humidity", 60)),
    }

    return {
        "raw_aqi": round(raw_aqi, 1),
        "adjusted_aqi": round(adjusted_aqi, 1),
        "p90_aqi": round(p90_aqi, 1),
        "rmse_buffer": round(rmse, 1),
        "uncertainty_std": round(std_aqi, 1),
        "pollutant_context": pollutant_context,
    }


# ─── Step 4: XGBoost Health Risk Classification ─────────────────────────────

def classify_health_risk(
    predicted_aqi: float,
    pollutants: dict,
    condition: str,
    severity: str,
    risk_model,
) -> dict:
    """
    Feed the LSTM's predicted AQI + pollutant context + user profile
    into the XGBoost risk classifier to get a personalised risk class.
    """
    c = condition.lower().strip()
    s = severity.lower().strip()

    features = [
        predicted_aqi,
        float(pollutants.get("pm25", 0)),
        float(pollutants.get("pm10", 0)),
        float(pollutants.get("no2", 0)),
        float(pollutants.get("o3", 0)),
        float(pollutants.get("co", 0)),
        float(pollutants.get("temperature", 25)),
        float(pollutants.get("humidity", 60)),
        1 if c == "copd" else 0,      # cond_copd
        1 if c == "asthma" else 0,    # cond_asthma
        1 if c == "both" else 0,      # cond_both
        1 if c == "other" else 0,     # cond_other
        1 if s == "mild" else 0,      # sev_mild
        1 if s == "moderate" else 0,  # sev_moderate
        1 if s == "severe" else 0,    # sev_severe
    ]

    X_risk = np.array([features])
    pred_class = int(risk_model.predict(X_risk)[0])
    probabilities = risk_model.predict_proba(X_risk)[0]

    risk_label = CLASS_NAMES[pred_class]

    return {
        "risk_class": pred_class,
        "risk_label": risk_label,
        "probabilities": {CLASS_NAMES[i]: round(float(p), 4) for i, p in enumerate(probabilities)},
        "confidence": round(float(probabilities[pred_class]) * 100, 1),
    }


# ─── Step 5: Build Personalised Alert ───────────────────────────────────────

def build_personalised_alert(
    user: dict,
    aqi_result: dict,
    risk_result: dict,
) -> dict:
    """
    Combine LSTM prediction + XGBoost risk class + user profile
    into a complete personalised health alert.
    """
    risk_label = risk_result["risk_label"]
    template = ALERT_TEMPLATES[risk_label]
    condition = user["condition"]

    # Build personalised message
    cond_display = condition.upper() if condition != "other" else "general health"
    message = (
        f"{template['emoji']} {template['base_message']} "
        f"(Personalised for {user['name']}, {cond_display} — {user['severity']})"
    )

    # Build precaution list: base + condition-specific
    precautions = list(template["base_precautions"])
    if condition in CONDITION_PRECAUTIONS:
        precautions.extend(CONDITION_PRECAUTIONS[condition])

    # Add symptom-aware advice
    symptoms = user.get("symptoms", [])
    if any("night" in s.lower() or "nocturnal" in s.lower() for s in symptoms):
        precautions.append("Consider keeping bedroom windows sealed and running a HEPA filter at night.")
    if any("exercise" in s.lower() or "exertion" in s.lower() for s in symptoms):
        precautions.append("Postpone outdoor exercise until AQI drops below 50.")
    if any("hospital" in s.lower() or "oxygen" in s.lower() or "O₂" in s for s in symptoms):
        precautions.append("⚠️ URGENT: Keep emergency contacts and hospital info readily accessible.")

    forecast_time = datetime.now(timezone.utc) + timedelta(hours=24)

    return {
        "user_name": user["name"],
        "user_age": user["age"],
        "condition": condition,
        "severity": user["severity"],
        "symptoms": symptoms,
        "city": user.get("city", "Unknown"),
        "predicted_aqi_raw": aqi_result["raw_aqi"],
        "predicted_aqi_adjusted": aqi_result["adjusted_aqi"],
        "rmse_buffer": aqi_result["rmse_buffer"],
        "uncertainty": aqi_result["uncertainty_std"],
        "risk_class": risk_result["risk_label"],
        "risk_confidence": risk_result["confidence"],
        "risk_probabilities": risk_result["probabilities"],
        "alert_tier": template["label"],
        "alert_message": message,
        "precautions": precautions,
        "pollutant_snapshot": aqi_result["pollutant_context"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "forecast_for": forecast_time.isoformat(),
    }


# ─── Pretty Print ────────────────────────────────────────────────────────────

def print_alert(alert: dict, index: int):
    """Print a single user alert in a rich terminal format."""
    risk_label = alert["risk_class"]
    template = ALERT_TEMPLATES[risk_label]
    color = template["color"]

    print(f"\n{'━' * 72}")
    print(f"  {BOLD}👤 USER {index}: {alert['user_name']}{RESET}  "
          f"(Age {alert['user_age']}, {alert['city']})")
    print(f"  Condition: {alert['condition'].upper()} ({alert['severity']})")
    print(f"  Symptoms:  {', '.join(alert['symptoms'])}")
    print(f"{'─' * 72}")

    print(f"\n  {DIM}── STAGE 1: LSTM AQI Prediction (24h ahead) ──{RESET}")
    print(f"  Raw Predicted AQI:      {alert['predicted_aqi_raw']}")
    print(f"  RMSE Safety Buffer:     +{alert['rmse_buffer']}")
    print(f"  Adjusted AQI:           {BOLD}{alert['predicted_aqi_adjusted']}{RESET}")
    print(f"  Uncertainty (±σ):       ±{alert['uncertainty']}")

    poll = alert["pollutant_snapshot"]
    print(f"\n  {DIM}── Pollutant Context (latest readings) ──{RESET}")
    print(f"  PM2.5: {poll['pm25']:.1f} µg/m³  |  PM10: {poll['pm10']:.1f} µg/m³  |"
          f"  NO₂: {poll['no2']:.1f} ppb")
    print(f"  O₃: {poll['o3']:.1f} ppb     |  CO: {poll['co']:.2f} mg/m³   |"
          f"  Temp: {poll['temperature']:.1f}°C  |  Humidity: {poll['humidity']:.0f}%")

    print(f"\n  {DIM}── STAGE 2: XGBoost Health Risk Classification ──{RESET}")
    probs = alert["risk_probabilities"]
    print(f"  Risk Class:             {color}{BOLD}{risk_label.upper()}{RESET}")
    print(f"  Confidence:             {alert['risk_confidence']}%")
    print(f"  Probabilities:          safe={probs['safe']:.2%}  caution={probs['caution']:.2%}  "
          f"high_risk={probs['high_risk']:.2%}  critical={probs['critical']:.2%}")

    print(f"\n  {DIM}── STAGE 3: Personalised Health Alert ──{RESET}")
    print(f"  {color}{BOLD}{alert['alert_message']}{RESET}")
    print(f"\n  Precautions:")
    for i, p in enumerate(alert["precautions"], 1):
        print(f"    {i}. {p}")

    print(f"\n  Forecast for: {alert['forecast_for']}")
    print(f"{'━' * 72}")


# ─── Main Pipeline ───────────────────────────────────────────────────────────

def main():
    print(f"\n{'╔' + '═' * 70 + '╗'}")
    print(f"║{'AQI HEALTH ALERT — END-TO-END PIPELINE DEMO':^70}║")
    print(f"║{'LSTM (AQI) → XGBoost (Risk) → Personalised Alert':^70}║")
    print(f"{'╚' + '═' * 70 + '╝'}")

    # ── Load all pre-trained models ───────────────────────────────────────
    artifacts = load_models()

    # ── Simulate 48h of recent sensor data ────────────────────────────────
    print(f"\n{'═' * 72}")
    print(f"  📡  SIMULATING 48h OF RECENT SENSOR DATA")
    print(f"{'═' * 72}")
    # Use a moderate-to-high AQI scenario so the risk model shows variation
    df_recent = simulate_recent_data(base_aqi=210.0, city="Delhi")
    print(f"  Generated {len(df_recent)} hourly records")
    print(f"  Time range: {df_recent['timestamp'].min()} → {df_recent['timestamp'].max()}")
    print(f"  AQI range:  {df_recent['aqi'].min():.0f} – {df_recent['aqi'].max():.0f}")
    print(f"  Mean AQI:   {df_recent['aqi'].mean():.1f}")

    # ── Run LSTM to predict AQI 24h ahead ─────────────────────────────────
    print(f"\n{'═' * 72}")
    print(f"  🧠  STAGE 1: LSTM AQI PREDICTION")
    print(f"{'═' * 72}")
    print(f"  Input:  48-hour window of sensor data → LSTM → predicted AQI 24h ahead")

    aqi_result = predict_aqi_lstm(df_recent, artifacts)

    print(f"  Output:")
    print(f"    Raw predicted AQI (median):   {aqi_result['raw_aqi']}")
    print(f"    P90 AQI (safety bias):        {aqi_result['p90_aqi']}")
    print(f"    RMSE buffer added:            +{aqi_result['rmse_buffer']}")
    print(f"    Final adjusted AQI:           {BOLD}{aqi_result['adjusted_aqi']}{RESET}")
    print(f"    Prediction uncertainty (σ):   ±{aqi_result['uncertainty_std']}")

    # ── Run XGBoost for each user profile ─────────────────────────────────
    print(f"\n{'═' * 72}")
    print(f"  🏥  STAGE 2 + 3: PERSONALISED HEALTH RISK ALERTS")
    print(f"  {'─' * 68}")
    print(f"  The SAME predicted AQI ({aqi_result['adjusted_aqi']}) produces")
    print(f"  DIFFERENT risk levels based on each user's condition and severity.")
    print(f"{'═' * 72}")

    all_alerts = []
    for i, user in enumerate(SAMPLE_USERS, 1):
        risk_result = classify_health_risk(
            predicted_aqi=aqi_result["adjusted_aqi"],
            pollutants=aqi_result["pollutant_context"],
            condition=user["condition"],
            severity=user["severity"],
            risk_model=artifacts["risk_model"],
        )

        alert = build_personalised_alert(user, aqi_result, risk_result)
        all_alerts.append(alert)
        print_alert(alert, i)

    # ── Summary Table ─────────────────────────────────────────────────────
    print(f"\n{'═' * 72}")
    print(f"  📊  SUMMARY: Same AQI → Different Risk Levels (Personalisation)")
    print(f"{'═' * 72}")
    print(f"  {'User':<22} {'Condition':<12} {'Severity':<10} {'Risk Class':<12} {'Confidence'}")
    print(f"  {'─' * 68}")
    for alert in all_alerts:
        risk_color = ALERT_TEMPLATES[alert["risk_class"]]["color"]
        print(f"  {alert['user_name']:<22} "
              f"{alert['condition']:<12} "
              f"{alert['severity']:<10} "
              f"{risk_color}{alert['risk_class'].upper():<12}{RESET} "
              f"{alert['risk_confidence']}%")
    print(f"  {'─' * 68}")
    print(f"  Predicted AQI: {aqi_result['adjusted_aqi']}  |  Forecast: +24 hours")
    print(f"\n  ✅ Pipeline complete. Both models are linked and producing")
    print(f"     personalised alerts based on the user's health profile.\n")

    # ── Export as JSON ────────────────────────────────────────────────────
    output_path = os.path.join(BACKEND_DIR, "demo_pipeline_output.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_alerts, f, indent=2, default=str)
    print(f"  💾 Full output saved → {output_path}\n")


if __name__ == "__main__":
    main()
