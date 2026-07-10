"""
train.py — AQI LSTM Training Script (Hybrid Multi-Source)
Trains a sequence-to-point LSTM to predict AQI 24 hours ahead.

Data Sources (priority order):
  1. city_hour.csv       — Primary: 700K+ hourly rows, multi-city (2015–2020)
  2. delhi-weather-aqi-2025.csv — Weather-enriched: temp, humidity, wind + AQI
  3. *_combined.csv      — City-specific supplements
  4. Synthetic generator — Augmentation for rare extreme events (~20% mix-in)

Outputs:
  aqi_lstm.h5, scaler.pkl, model_metadata.json, seasonal_baseline.json

Run:
  python train.py
  python train.py --data-dir "C:\\Users\\Admin\\OneDrive\\Desktop\\aqidata"
"""

import argparse
import json
import logging
import os
from datetime import datetime, timedelta
from glob import glob

import joblib
import numpy as np
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

# ─── Config ──────────────────────────────────────────────────────────────────
WINDOW = 48              # hours of history fed into LSTM
FORECAST_HORIZON = 24   # predict AQI this many hours ahead
EPOCHS = 25             # max epochs — EarlyStopping will cut short if no improvement
BATCH_SIZE = 32
VALIDATION_SPLIT = 0.2
SYNTHETIC_FRACTION = 0.20   # 20% synthetic augmentation mixed into real data

MODEL_PATH = os.getenv("MODEL_PATH", "aqi_lstm.h5")
SCALER_PATH = os.getenv("SCALER_PATH", "scaler.pkl")
METADATA_PATH = os.getenv("METADATA_PATH", "model_metadata.json")
BASELINE_PATH = os.getenv("BASELINE_PATH", "seasonal_baseline.json")

FEATURES = [
    "pm25", "pm10", "no2", "o3", "co",
    "temperature", "humidity", "wind_speed",
    "hour_sin", "hour_cos", "day_sin", "day_cos",
    "pm25_lag1", "pm25_lag6", "pm25_lag24",
    "pm25_rolling6", "pm25_rolling24",
]
TARGET = "aqi"
ALL_COLS = FEATURES + [TARGET]

# ─── India NAQI Breakpoints ───────────────────────────────────────────────────

def _bp_aqi(c: float, bp: list) -> float:
    for cl, ch, il, ih in bp:
        if cl <= c <= ch:
            return ((ih - il) / (ch - cl)) * (c - cl) + il
    return 500.0


def calculate_india_aqi(pm25: float, pm10: float) -> float:
    pm25_bp = [
        (0, 30, 0, 50), (30, 60, 51, 100), (60, 90, 101, 200),
        (90, 120, 201, 300), (120, 250, 301, 400), (250, 500, 401, 500),
    ]
    pm10_bp = [
        (0, 50, 0, 50), (50, 100, 51, 100), (100, 250, 101, 200),
        (250, 350, 201, 300), (350, 430, 301, 400), (430, 600, 401, 500),
    ]
    return max(_bp_aqi(max(0.0, pm25), pm25_bp), _bp_aqi(max(0.0, pm10), pm10_bp))


# ─── Data Loaders ─────────────────────────────────────────────────────────────

def load_city_hour(path: str, cities: list = None) -> pd.DataFrame:
    """
    Load city_hour.csv (Kaggle India AQI 2015–2020 dataset).
    Retains 'City' column so sequences can be built per-city.
    """
    logger.info(f"Loading city_hour.csv from {path}...")
    df = pd.read_csv(path, low_memory=False)

    df = df.rename(columns={
        "Datetime": "timestamp",
        "PM2.5": "pm25",
        "PM10": "pm10",
        "NO2": "no2",
        "CO": "co",
        "O3": "o3",
        "SO2": "so2",
        "AQI": "aqi",
    })

    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["timestamp"])

    if cities and "City" in df.columns:
        df = df[df["City"].isin(cities)]
        logger.info(f"  Filtered to cities: {cities} → {len(df):,} rows")

    keep = ["City", "timestamp", "pm25", "pm10", "no2", "co", "o3"]
    if "aqi" in df.columns:
        keep.append("aqi")
    df = df[[c for c in keep if c in df.columns]].copy()
    df = df.rename(columns={"City": "city"})

    if "aqi" not in df.columns or df["aqi"].isna().mean() > 0.5:
        df["aqi"] = df.apply(
            lambda r: calculate_india_aqi(r.get("pm25", 0) or 0, r.get("pm10", 0) or 0),
            axis=1,
        )

    # Simulate weather from seasonal patterns (city_hour has no weather cols)
    df["doy"] = df["timestamp"].dt.dayofyear
    df["hour"] = df["timestamp"].dt.hour
    df["temperature"] = (26.0
                         + 8 * np.sin((df["hour"] - 6) * np.pi / 12)
                         + 5 * np.cos(df["doy"] * 2 * np.pi / 365))
    df["humidity"] = (60.0 - 18 * np.sin((df["hour"] - 6) * np.pi / 12)).clip(0, 100)
    rng = np.random.default_rng(42)
    df["wind_speed"] = np.abs(rng.normal(8, 2, len(df)))
    df = df.drop(columns=["doy", "hour"])

    logger.info(f"  city_hour.csv loaded: {len(df):,} rows")
    return df


def load_delhi_weather(path: str) -> pd.DataFrame:
    """
    Load delhi-weather-aqi-2025.csv — has weather + AQI + lat/lon.
    Retains 'location' as city identifier.
    """
    logger.info(f"Loading delhi-weather-aqi-2025.csv from {path}...")
    df = pd.read_csv(path, low_memory=False)

    df["timestamp"] = pd.to_datetime(
        df["date_ist"] + " " + df["time_ist"].astype(str),
        dayfirst=True, errors="coerce",
    )
    df = df.dropna(subset=["timestamp"])

    df = df.rename(columns={
        "pm2_5": "pm25",
        "temp_c": "temperature",
        "windspeed_kph": "wind_speed",
        "aqi_index": "aqi",
        "no2": "no2",
        "co": "co",
        "location": "city",
    })

    if "wind_speed" in df.columns:
        df["wind_speed"] = df["wind_speed"] / 3.6   # kph → m/s
    if "co" in df.columns:
        df["co"] = df["co"] / 1000.0                 # µg/m³ → mg/m³
    if "pm10" not in df.columns:
        df["pm10"] = df.get("pm25", pd.Series(dtype=float)) * 1.8

    keep = ["city", "timestamp", "pm25", "pm10", "no2", "co", "aqi",
            "temperature", "humidity", "wind_speed"]
    df = df[[c for c in keep if c in df.columns]].copy()

    logger.info(f"  delhi-weather-aqi-2025.csv loaded: {len(df):,} rows")
    return df


def load_city_combined(paths: list) -> pd.DataFrame:
    """Load *_combined.csv files with city tag."""
    frames = []
    for path in paths:
        try:
            df = pd.read_csv(path, low_memory=False)
            df = df.rename(columns={
                "Timestamp": "timestamp", "PM2.5": "pm25",
                "PM10": "pm10", "NO2": "no2", "CO": "co", "O3": "o3",
            })
            df["timestamp"] = pd.to_datetime(df["timestamp"], dayfirst=True, errors="coerce")
            df = df.dropna(subset=["timestamp"])
            df["city"] = os.path.basename(path).replace("_combined.csv", "").title()
            if "aqi" not in df.columns:
                df["aqi"] = df.apply(
                    lambda r: calculate_india_aqi(r.get("pm25", 0) or 0, r.get("pm10", 0) or 0),
                    axis=1,
                )
            df["temperature"] = 26.0
            df["humidity"] = 60.0
            df["wind_speed"] = 8.0
            keep = ["city", "timestamp", "pm25", "pm10", "no2", "co", "o3",
                    "aqi", "temperature", "humidity", "wind_speed"]
            df = df[[c for c in keep if c in df.columns]]
            frames.append(df)
            logger.info(f"  Loaded {os.path.basename(path)}: {len(df):,} rows")
        except Exception as e:
            logger.warning(f"  Could not load {path}: {e}")
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


# ─── Synthetic Data Generator ────────────────────────────────────────────────

def generate_synthetic_data(n_days: int = 365) -> pd.DataFrame:
    """
    Generate realistic synthetic AQI time-series for augmentation.
    Captures rush-hour cycles, seasonal winter peaks, and weekend dips.
    """
    logger.info(f"Generating {n_days} days of synthetic augmentation data...")
    np.random.seed(99)

    n_hours = n_days * 24
    timestamps = [datetime(2024, 6, 1) + timedelta(hours=i) for i in range(n_hours)]
    records = []

    for ts in timestamps:
        h, dow, doy = ts.hour, ts.weekday(), ts.timetuple().tm_yday

        rush = (
            1.5 * np.exp(-((h - 8.5) ** 2) / 2.0)
            + 1.2 * np.exp(-((h - 19.0) ** 2) / 2.0)
            + 0.5
        )
        season = 1.0 + 0.45 * np.cos((doy - 15) * 2 * np.pi / 365)
        weekend = 0.82 if dow >= 5 else 1.0

        pm25 = max(5.0, 48.0 * rush * season * weekend + np.random.normal(0, 9))
        pm10 = pm25 * np.random.uniform(1.5, 2.2)
        no2 = max(0.0, pm25 * np.random.uniform(0.3, 0.6) + np.random.normal(0, 5))
        o3 = max(0.0, 30 + 20 * np.sin(h * np.pi / 12) + np.random.normal(0, 5))
        co = max(0.0, pm25 * np.random.uniform(0.08, 0.25) + np.random.normal(0, 2))
        temperature = (26 + 8 * np.sin((h - 6) * np.pi / 12)
                       + 5 * np.cos(doy * 2 * np.pi / 365) + np.random.normal(0, 2))
        humidity = min(100, max(0, 62 - 18 * np.sin((h - 6) * np.pi / 12) + np.random.normal(0, 5)))
        wind_speed = abs(np.random.normal(7, 3.5))

        records.append({
            "timestamp": ts,
            "pm25": round(pm25, 2), "pm10": round(pm10, 2),
            "no2": round(no2, 2), "o3": round(o3, 2), "co": round(co, 2),
            "temperature": round(temperature, 2),
            "humidity": round(humidity, 2),
            "wind_speed": round(wind_speed, 2),
            "aqi": round(calculate_india_aqi(pm25, pm10), 1),
        })

    return pd.DataFrame(records)


# ─── Data Combiner ────────────────────────────────────────────────────────────

def combine_sources(*frames: pd.DataFrame, synthetic_fraction: float = 0.20) -> pd.DataFrame:
    """
    Combine DataFrames from different sources WITHOUT cross-city timestamp deduplication.

    KEY FIX: Previously we deduplicated by timestamp across all cities, which
    collapsed Delhi AQI at 01:00 and Hyderabad AQI at 01:00 into one record,
    destroying the temporal signal. Now we deduplicate WITHIN each city only,
    preserving each city's independent time series for proper LSTM sequence building.
    """
    valid = [f for f in frames if f is not None and len(f) > 0]
    if not valid:
        logger.warning("No real data loaded — falling back to pure synthetic")
        return generate_synthetic_data(n_days=365)

    combined = pd.concat(valid, ignore_index=True)
    combined["timestamp"] = pd.to_datetime(combined["timestamp"])
    combined["timestamp"] = combined["timestamp"].dt.round("h")

    # Deduplicate WITHIN each city (not across cities)
    if "city" in combined.columns:
        combined = (
            combined.sort_values("timestamp")
            .drop_duplicates(subset=["city", "timestamp"], keep="last")
        )
        logger.info(f"Combined real data (raw): {len(combined):,} rows across "
                    f"{combined['city'].nunique()} cities")
    else:
        combined["city"] = "unknown"
        combined = combined.sort_values("timestamp").drop_duplicates(subset=["timestamp"], keep="last")
        logger.info(f"Combined real data (raw): {len(combined):,} rows")

    # Ensure all numeric columns exist
    for col in ["pm25", "pm10", "no2", "o3", "co", "temperature", "humidity", "wind_speed", "aqi"]:
        if col not in combined.columns:
            combined[col] = np.nan

    # ── Data Quality Fixes ────────────────────────────────────────────────
    mask_bad_aqi = combined["aqi"].isna() | (combined["aqi"] <= 0)
    combined.loc[mask_bad_aqi, "aqi"] = combined.loc[mask_bad_aqi].apply(
        lambda r: calculate_india_aqi(r.get("pm25", 0) or 0, r.get("pm10", 0) or 0),
        axis=1,
    )

    before = len(combined)
    combined = combined[
        (combined["aqi"] > 0) &
        (combined["aqi"] <= 500) &
        (~(combined["pm25"].isna() & combined["pm10"].isna()))
    ]
    logger.info(f"Dropped {before - len(combined):,} invalid rows (AQI=0/NaN/out-of-range)")

    # Fill remaining gaps per city to preserve temporal continuity
    numeric_cols = ["pm25", "pm10", "no2", "o3", "co", "temperature", "humidity", "wind_speed", "aqi"]
    combined = combined.sort_values(["city", "timestamp"]).reset_index(drop=True)
    combined[numeric_cols] = (
        combined.groupby("city")[numeric_cols]
        .transform(lambda x: x.ffill().bfill())
    )
    for col in numeric_cols:
        med = combined[col].median()
        combined[col] = combined[col].fillna(med)
    combined[numeric_cols] = combined[numeric_cols].clip(lower=0)
    combined["aqi"] = combined["aqi"].clip(upper=500)

    logger.info(f"Clean data: {len(combined):,} rows across {combined['city'].nunique()} cities")

    # Add synthetic augmentation
    n_synth = int(len(combined) * synthetic_fraction)
    synth_days = max(30, n_synth // 24)
    synth_df = generate_synthetic_data(n_days=synth_days)
    synth_df["city"] = "synthetic"

    full = pd.concat([combined, synth_df], ignore_index=True)
    full = full.sort_values(["city", "timestamp"]).reset_index(drop=True)
    logger.info(f"Final dataset: {len(full):,} rows ({len(combined):,} real + {len(synth_df):,} synthetic)")
    return full


# ─── Feature Engineering ─────────────────────────────────────────────────────

def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add cyclic time encodings and lag/rolling features."""
    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)

    df["hour_sin"] = np.sin(2 * np.pi * df["timestamp"].dt.hour / 24)
    df["hour_cos"] = np.cos(2 * np.pi * df["timestamp"].dt.hour / 24)
    df["day_sin"] = np.sin(2 * np.pi * df["timestamp"].dt.dayofweek / 7)
    df["day_cos"] = np.cos(2 * np.pi * df["timestamp"].dt.dayofweek / 7)

    df["pm25_lag1"] = df["pm25"].shift(1)
    df["pm25_lag6"] = df["pm25"].shift(6)
    df["pm25_lag24"] = df["pm25"].shift(24)
    df["pm25_rolling6"] = df["pm25"].rolling(6, min_periods=1).mean()
    df["pm25_rolling24"] = df["pm25"].rolling(24, min_periods=1).mean()

    df = df.dropna(subset=["pm25_lag24"]).reset_index(drop=True)
    return df


# ─── Sequence Builder ────────────────────────────────────────────────────────

def build_sequences(df: pd.DataFrame):
    """
    Build (X, y) LSTM sequences per city, then combine.

    KEY FIX: Building sequences per-city preserves temporal coherence.
    Each city's AQI time series is continuous within itself.
    Mixing across cities at the sequence level (not the row level) is correct.
    """
    from sklearn.preprocessing import MinMaxScaler

    scaler = MinMaxScaler()
    # Fit scaler on ALL data so scale is consistent
    scaler.fit(df[ALL_COLS].values)

    n_features = len(FEATURES)
    X_all, y_all = [], []

    cities = df["city"].unique() if "city" in df.columns else ["all"]

    for city in cities:
        city_df = df[df["city"] == city].sort_values("timestamp") if "city" in df.columns else df
        city_df = city_df.reset_index(drop=True)

        if len(city_df) < WINDOW + FORECAST_HORIZON + 1:
            logger.warning(f"  Skipping {city}: only {len(city_df)} rows (need {WINDOW + FORECAST_HORIZON + 1}+)")
            continue

        scaled = scaler.transform(city_df[ALL_COLS].values)

        for i in range(WINDOW, len(scaled) - FORECAST_HORIZON):
            X_all.append(scaled[i - WINDOW: i, :n_features])
            y_all.append(scaled[i + FORECAST_HORIZON - 1, -1])

        logger.info(f"  {city}: {len(city_df):,} rows → {len(scaled) - WINDOW - FORECAST_HORIZON:,} sequences")

    X = np.array(X_all)
    y = np.array(y_all)
    logger.info(f"Total sequences: X={X.shape}, y={y.shape}")
    return X, y, scaler


# ─── Model ───────────────────────────────────────────────────────────────────

def build_model(n_features: int):
    from tensorflow.keras.layers import BatchNormalization, Dense, Dropout, LSTM
    from tensorflow.keras.models import Sequential
    from tensorflow.keras.optimizers import Adam

    model = Sequential([
        LSTM(128, return_sequences=True, input_shape=(WINDOW, n_features)),
        Dropout(0.3),
        LSTM(64, return_sequences=False),
        Dropout(0.3),
        BatchNormalization(),
        Dense(32, activation="relu"),
        Dropout(0.2),
        Dense(1, activation="linear"),
    ], name="aqi_lstm")

    model.compile(optimizer=Adam(learning_rate=0.001), loss="mse", metrics=["mae"])
    return model


# ─── Seasonal Baseline ────────────────────────────────────────────────────────

def save_seasonal_baseline(df: pd.DataFrame) -> None:
    tmp = df.copy()
    tmp["dow"] = tmp["timestamp"].dt.dayofweek
    tmp["hour"] = tmp["timestamp"].dt.hour
    baseline = tmp.groupby(["dow", "hour"])["aqi"].mean().to_dict()
    serialized = {f"{k[0]}_{k[1]}": float(v) for k, v in baseline.items()}
    with open(BASELINE_PATH, "w") as f:
        json.dump(serialized, f, indent=2)
    logger.info(f"Seasonal baseline saved → {BASELINE_PATH} ({len(serialized)} buckets)")


# ─── Main Training Pipeline ───────────────────────────────────────────────────

def train(data_dir: str = None) -> dict:
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
    from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau

    data_dir = data_dir or r"C:\Users\Admin\OneDrive\Desktop\aqidata"

    # ── 1. Load All Real Data Sources ────────────────────────────────────────
    frames = []

    # Source A: city_hour.csv (best primary — multi-city hourly)
    city_hour_path = os.path.join(data_dir, "city_hour.csv")
    if os.path.exists(city_hour_path):
        cities = ["Hyderabad", "Delhi", "Mumbai", "Bengaluru", "Chennai",
                  "Kolkata", "Jaipur", "Lucknow"]
        frames.append(load_city_hour(city_hour_path, cities=cities))
    else:
        logger.warning(f"city_hour.csv not found at {city_hour_path}")

    # Source B: delhi-weather-aqi-2025.csv (weather-enriched, most recent)
    delhi_weather_path = os.path.join(data_dir, "delhi-weather-aqi-2025.csv")
    if os.path.exists(delhi_weather_path):
        frames.append(load_delhi_weather(delhi_weather_path))
    else:
        logger.warning(f"delhi-weather-aqi-2025.csv not found at {delhi_weather_path}")

    # Source C: City-specific combined CSVs (supplements)
    combined_paths = glob(os.path.join(data_dir, "*_combined.csv"))
    if combined_paths:
        frames.append(load_city_combined(combined_paths))

    # ── 2. Combine + Augment with Synthetic ───────────────────────────────────
    df = combine_sources(*frames, synthetic_fraction=SYNTHETIC_FRACTION)

    # ── 3. Feature Engineering ────────────────────────────────────────────────
    df = engineer_features(df)
    logger.info(f"Post-engineering: {len(df):,} rows")

    # ── 4. Save Seasonal Baseline ─────────────────────────────────────────────
    save_seasonal_baseline(df)

    # ── 5. Build Sequences ────────────────────────────────────────────────────
    X, y, scaler = build_sequences(df)
    logger.info(f"Sequences: X={X.shape}, y={y.shape}")

    # ── 6. Chronological Train/Test Split ────────────────────────────────────
    split = int(len(X) * (1 - VALIDATION_SPLIT))
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]

    # ── 7. Build and Train Model ──────────────────────────────────────────────
    model = build_model(n_features=len(FEATURES))
    model.summary()

    callbacks = [
        EarlyStopping(patience=10, restore_best_weights=True, verbose=1),
        ReduceLROnPlateau(patience=5, factor=0.5, min_lr=1e-5, verbose=1),
    ]

    model.fit(
        X_train, y_train,
        validation_data=(X_test, y_test),
        epochs=EPOCHS,
        batch_size=BATCH_SIZE,
        callbacks=callbacks,
        verbose=1,
    )

    # ── 8. Evaluate ───────────────────────────────────────────────────────────
    preds_scaled = model.predict(X_test, verbose=0).flatten()
    n_all = len(ALL_COLS)

    dummy_pred = np.zeros((len(preds_scaled), n_all))
    dummy_pred[:, -1] = preds_scaled
    preds = scaler.inverse_transform(dummy_pred)[:, -1]

    dummy_true = np.zeros((len(y_test), n_all))
    dummy_true[:, -1] = y_test
    actuals = scaler.inverse_transform(dummy_true)[:, -1]

    rmse = float(np.sqrt(mean_squared_error(actuals, preds)))
    r2 = float(r2_score(actuals, preds))
    mae = float(mean_absolute_error(actuals, preds))

    logger.info(f"Evaluation → RMSE: {rmse:.2f} | R²: {r2:.4f} | MAE: {mae:.2f}")

    # ── 9. Save Artifacts ─────────────────────────────────────────────────────
    model.save(MODEL_PATH)
    joblib.dump(scaler, SCALER_PATH)

    metadata = {
        "rmse": rmse, "r2": r2, "mae": mae,
        "window": WINDOW,
        "forecast_horizon": FORECAST_HORIZON,
        "features": FEATURES,
        "n_samples_train": int(split),
        "n_samples_test": int(len(X) - split),
        "data_sources": ["city_hour.csv", "delhi-weather-aqi-2025.csv",
                         "*_combined.csv", "synthetic_augmentation"],
        "trained_at": datetime.utcnow().isoformat() + "Z",
    }
    with open(METADATA_PATH, "w") as f:
        json.dump(metadata, f, indent=2)

    logger.info(f"Model saved    → {MODEL_PATH}")
    logger.info(f"Scaler saved   → {SCALER_PATH}")
    logger.info(f"Metadata saved → {METADATA_PATH}")
    logger.info("Training complete ✓")
    return metadata


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data-dir",
        default=r"C:\Users\Admin\OneDrive\Desktop\aqidata",
        help="Path to directory containing AQI CSV files",
    )
    args = parser.parse_args()
    train(data_dir=args.data_dir)
