"use client";

import { useEffect, useState } from "react";

interface IndoorRecommendation {
  action: string;
  message: string;
  duration?: string;
}

interface IndoorRecommendationsData {
  user_id: string;
  current_aqi: number;
  recommendations: {
    window_advice: IndoorRecommendation;
    purifier_advice: IndoorRecommendation & { setting: string; runtime: string };
    activity_advice: {
      exercise: string;
      cooking: string;
      cleaning: string;
    };
  };
  hourly_forecast: Array<{
    hour: string;
    predicted_aqi: number;
    window_action: string;
    purifier_setting: string;
    is_optimal_ventilation: boolean;
  }>;
  optimal_ventilation_times: string[];
  generated_at: string;
}

interface SmartIndoorRecommendationsProps {
  userId: string;
  currentAqi: number;
  // FIX: Pass personalized risk tier and effective AQI from prediction
  alertTier?: string;        // "Safe" | "Caution" | "High Risk" | "Critical"
  effectiveAqi?: number;     // personalized effective AQI (includes condition shift + symptom penalty)
}

// FIX: All indoor guidelines now evaluate personalized risk tier, NOT raw AQI
function getPersonalizedActivityAdvice(alertTier: string, effectiveAqi: number): {
  exercise: string; cooking: string; cleaning: string;
} {
  const tier = alertTier?.toLowerCase();

  if (tier === "critical" || effectiveAqi > 200) {
    return {
      exercise: "🚫 Skip ALL workouts today — even light yoga near windows is unsafe for your condition.",
      cooking: "🍽️ Avoid high-heat cooking. Keep kitchen sealed. Use exhaust fans at max speed.",
      cleaning: "🧹 Do NOT vacuum or sweep — this stirs up indoor particulates. Postpone all cleaning."
    };
  }
  if (tier === "high risk" || effectiveAqi > 100) {
    return {
      exercise: "⚠️ No cardio workouts. Light stretching in a sealed room only — avoid windows.",
      cooking: "🍳 Use lids while cooking. Run exhaust fan. Avoid frying or high-heat methods.",
      cleaning: "🫧 Damp-wipe surfaces only. Avoid dry dusting. Postpone vacuuming if possible."
    };
  }
  if (tier === "caution" || effectiveAqi > 50) {
    return {
      exercise: "🏃 Light indoor exercise OK. Keep windows closed during workout.",
      cooking: "👨‍🍳 Normal cooking fine. Open kitchen window briefly if needed.",
      cleaning: "🧽 Regular cleaning OK. Use damp mop instead of dry broom."
    };
  }
  // Safe
  return {
    exercise: "💪 All indoor exercises safe! Great day for a full workout.",
    cooking: "🥗 No restrictions. Cook freely — air quality is good.",
    cleaning: "🏠 Perfect day for deep cleaning — open windows while you clean!"
  };
}

// FIX: Window advice also based on personalized risk, not just raw AQI
function getPersonalizedWindowAdvice(alertTier: string, currentAqi: number): IndoorRecommendation {
  const tier = alertTier?.toLowerCase();

  if (tier === "critical") {
    return {
      action: "keep_closed",
      message: "🚫 Keep ALL windows and doors sealed. Your condition makes outdoor air dangerous even at moderate AQI levels.",
      duration: "Stay indoors until your risk tier drops to Caution or below."
    };
  }
  if (tier === "high risk") {
    return {
      action: "keep_closed",
      message: "🔒 Keep windows closed. Outdoor AQI is above your personalized safe threshold.",
      duration: "Ventilate only during optimal windows shown below."
    };
  }
  if (currentAqi < 50) {
    return {
      action: "open_windows",
      message: "🌬️ Outdoor air is clean. Open windows for 15–30 minutes to refresh indoor air.",
      duration: "Safe to ventilate freely."
    };
  }
  if (currentAqi < 100) {
    return {
      action: "selective_ventilation",
      message: "🪟 Brief ventilation OK. 5–10 minutes only — avoid prolonged exposure.",
      duration: "Short bursts only."
    };
  }
  return {
    action: "keep_closed",
    message: "🚫 Keep windows sealed. Outdoor air quality is poor.",
    duration: "Wait for AQI to drop below 100."
  };
}

export default function SmartIndoorRecommendations({
  userId,
  currentAqi,
  alertTier = "Safe",
  effectiveAqi,
}: SmartIndoorRecommendationsProps) {
  const [recommendations, setRecommendations] = useState<IndoorRecommendationsData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Use NEXT_PUBLIC_API_URL to match .env.local
  const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  useEffect(() => {
    if (userId) fetchRecommendations();
  }, [userId]);

  const fetchRecommendations = async () => {
    if (!userId) return;
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE_URL}/indoor-recommendations/${userId}`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      setRecommendations(data);
    } catch (err: any) {
      setError(err.message || "Failed to load");
    } finally {
      setLoading(false);
    }
  };

  const getActionIcon = (action: string) => {
    if (action.includes("open")) return "🌬️";
    if (action.includes("selective")) return "🪟";
    if (action.includes("closed") || action.includes("keep")) return "🚫";
    if (action.includes("max")) return "💨";
    if (action.includes("high")) return "🔄";
    if (action.includes("medium")) return "⚙️";
    if (action.includes("low") || action.includes("off")) return "✨";
    return "💡";
  };

  const getActionBorderColor = (action: string) => {
    if (action.includes("open") || action.includes("low") || action.includes("off"))
      return "oklch(0.75 0.11 162 / 0.35)";
    if (action.includes("selective") || action.includes("medium"))
      return "oklch(0.82 0.11 95 / 0.35)";
    return "oklch(0.72 0.14 32 / 0.35)";
  };

  // ── Loading state ──────────────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="glass reveal" style={{ borderRadius: "1.5rem", padding: "1.5rem", transitionDelay: "240ms" }}>
        <div className="overline" style={{ marginBottom: "1rem" }}>
          <span className="overline-dash" />🏠 Smart Indoor Air Quality
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "1rem", minHeight: "120px" }}>
          <span className="loader-ring" />
          <span style={{ fontSize: "0.875rem", color: "var(--muted-foreground)" }}>
            Generating personalized indoor recommendations…
          </span>
        </div>
      </div>
    );
  }

  // ── Error state — still show the card with retry ───────────────────────────
  if (error || !recommendations) {
    return (
      <div className="glass reveal" style={{ borderRadius: "1.5rem", padding: "1.5rem", transitionDelay: "240ms" }}>
        <div className="overline" style={{ marginBottom: "1rem" }}>
          <span className="overline-dash" />🏠 Smart Indoor Air Quality
        </div>
        <div style={{ textAlign: "center", padding: "2rem 1rem" }}>
          <div style={{ fontSize: "2.5rem", marginBottom: "0.75rem" }}>🏠</div>
          <div style={{ fontSize: "0.875rem", color: "var(--muted-foreground)", marginBottom: "1.25rem" }}>
            {error
              ? `Could not load recommendations — ${error}`
              : "No recommendations available yet."}
          </div>
          <button
            onClick={fetchRecommendations}
            style={{
              background: "rgba(255,255,255,0.06)",
              border: "1px solid var(--border)",
              borderRadius: "0.5rem",
              padding: "0.5rem 1.25rem",
              fontSize: "0.8125rem",
              color: "var(--foreground)",
              cursor: "pointer",
            }}
          >
            🔄 Retry
          </button>
        </div>
      </div>
    );
  }

  // ── Full render — FIX: uses personalized risk tier, NOT raw AQI ──────────
  const personalizedWindowAdvice = getPersonalizedWindowAdvice(alertTier, currentAqi);
  const personalizedActivityAdvice = getPersonalizedActivityAdvice(alertTier, effectiveAqi ?? currentAqi);

  // Purifier setting still based on raw outdoor AQI (it filters outdoor air)
  const purifierAdvice = recommendations?.recommendations?.purifier_advice ?? {
    setting: currentAqi > 150 ? "max_speed" : currentAqi > 100 ? "high_speed" : currentAqi > 50 ? "medium_speed" : "low_or_off",
    message: currentAqi > 150 ? "💨 Run air purifier on HIGHEST setting continuously."
           : currentAqi > 100 ? "🔄 Run air purifier on HIGH setting, especially in bedroom."
           : currentAqi > 50  ? "⚙️ Run on MEDIUM during sleep and work hours."
           : "✨ Low or off — outdoor air is clean today.",
    runtime: currentAqi > 150 ? "24/7" : currentAqi > 100 ? "12+ hours/day" : currentAqi > 50 ? "8–10 hours/day" : "Optional"
  };

  const optimalTimes = recommendations?.optimal_ventilation_times ?? [];

  // Tier-based border color
  const tierBorderColor = 
    alertTier?.toLowerCase() === "critical"  ? "oklch(0.62 0.20 18 / 0.4)"  :
    alertTier?.toLowerCase() === "high risk" ? "oklch(0.78 0.14 36 / 0.4)"  :
    alertTier?.toLowerCase() === "caution"   ? "oklch(0.82 0.11 78 / 0.4)"  :
    "oklch(0.75 0.11 162 / 0.4)";

  const getActionIcon = (action: string) => {
    if (action.includes("open")) return "🌬️";
    if (action.includes("selective")) return "🪟";
    if (action.includes("closed") || action.includes("keep")) return "🚫";
    if (action.includes("max")) return "💨";
    if (action.includes("high")) return "🔄";
    if (action.includes("medium")) return "⚙️";
    return "✨";
  };

  return (
    <div className="glass reveal" style={{ borderRadius: "1.5rem", padding: "1.5rem", transitionDelay: "240ms" }}>
      <div className="overline" style={{ marginBottom: "0.75rem" }}>
        <span className="overline-dash" />🏠 Smart Indoor Air Quality
      </div>

      {/* Personalized context banner */}
      <div style={{
        padding: "0.625rem 0.875rem",
        borderRadius: "0.5rem",
        background: `${tierBorderColor.replace("0.4", "0.08")}`,
        border: `1px solid ${tierBorderColor}`,
        marginBottom: "1.25rem",
        fontSize: "0.75rem",
        lineHeight: 1.5
      }}>
        <strong>Personalized for your risk tier ({alertTier})</strong> — recommendations below are based on your effective AQI of {Math.round(effectiveAqi ?? currentAqi)}, not just the outdoor reading of {Math.round(currentAqi)}.
      </div>

      {/* Window + Purifier cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: "1rem", marginBottom: "1.5rem" }}>

        {/* Window advice — personalized */}
        <div style={{
          padding: "1rem", borderRadius: "0.75rem",
          background: "rgba(255,255,255,0.02)",
          border: `1px solid ${tierBorderColor}`,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.5rem" }}>
            <span style={{ fontSize: "1.25rem" }}>{getActionIcon(personalizedWindowAdvice.action)}</span>
            <span style={{ fontSize: "0.8125rem", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.08em" }}>
              Windows
            </span>
          </div>
          <p style={{ fontSize: "0.75rem", lineHeight: 1.55, marginBottom: "0.35rem" }}>
            {personalizedWindowAdvice.message}
          </p>
          {personalizedWindowAdvice.duration && (
            <p style={{ fontSize: "0.6875rem", color: "var(--muted-foreground)" }}>
              {personalizedWindowAdvice.duration}
            </p>
          )}
        </div>

        {/* Purifier advice */}
        <div style={{
          padding: "1rem", borderRadius: "0.75rem",
          background: "rgba(255,255,255,0.02)",
          border: "1px solid var(--border)",
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.5rem" }}>
            <span style={{ fontSize: "1.25rem" }}>{getActionIcon(purifierAdvice.setting)}</span>
            <span style={{ fontSize: "0.8125rem", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.08em" }}>
              Air Purifier
            </span>
          </div>
          <p style={{ fontSize: "0.75rem", lineHeight: 1.55, marginBottom: "0.35rem" }}>
            {purifierAdvice.message}
          </p>
          <p style={{ fontSize: "0.6875rem", color: "var(--muted-foreground)" }}>
            Runtime: {purifierAdvice.runtime}
          </p>
        </div>
      </div>

      {/* Activity guidelines — FIX: using personalized tier */}
      <div style={{ marginBottom: "1.5rem" }}>
        <h4 style={{ fontSize: "0.8125rem", fontWeight: 600, marginBottom: "0.75rem", textTransform: "uppercase", letterSpacing: "0.08em" }}>
          Indoor Activity Guidelines
          <span style={{ fontSize: "0.625rem", marginLeft: "0.5rem", color: "var(--accent)", fontWeight: 400 }}>
            (based on your {alertTier} risk level)
          </span>
        </h4>
        <div style={{ display: "grid", gap: "0.5rem" }}>
          {Object.entries(personalizedActivityAdvice).map(([activity, advice]) => (
            <div key={activity} style={{
              padding: "0.75rem", borderRadius: "0.5rem",
              background: "rgba(255,255,255,0.02)",
              border: "1px solid var(--border)",
              display: "flex", gap: "0.75rem"
            }}>
              <span style={{ fontSize: "0.6875rem", fontWeight: 700, textTransform: "uppercase", color: "var(--accent)", minWidth: "60px" }}>
                {activity}
              </span>
              <span style={{ fontSize: "0.75rem", lineHeight: 1.4 }}>{advice}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Optimal ventilation windows */}
      {optimalTimes.length > 0 && (
        <div style={{ marginBottom: "1.25rem" }}>
          <h4 style={{ fontSize: "0.8125rem", fontWeight: 600, marginBottom: "0.75rem", textTransform: "uppercase", letterSpacing: "0.08em" }}>
            🌿 Optimal Ventilation Windows
          </h4>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem" }}>
            {optimalTimes.map((t: string, i: number) => (
              <span key={i} style={{
                padding: "0.25rem 0.75rem", borderRadius: "9999px",
                background: "oklch(0.75 0.11 162 / 0.1)",
                border: "1px solid oklch(0.75 0.11 162 / 0.3)",
                color: "oklch(0.75 0.11 162)",
                fontSize: "0.75rem", fontFamily: "var(--font-mono)", fontWeight: 500,
              }}>
                {t}
              </span>
            ))}
          </div>
          <p style={{ fontSize: "0.6875rem", color: "var(--muted-foreground)", marginTop: "0.5rem" }}>
            Best hours for natural ventilation based on 24h AQI forecast.
          </p>
        </div>
      )}

      {/* Refresh */}
      <div style={{ paddingTop: "1rem", borderTop: "1px solid var(--border)" }}>
        <button
          onClick={fetchRecommendations}
          disabled={loading}
          style={{
            background: "rgba(255,255,255,0.05)",
            border: "1px solid var(--border)",
            borderRadius: "0.5rem",
            padding: "0.4rem 1rem",
            fontSize: "0.75rem",
            color: "var(--foreground)",
            cursor: loading ? "not-allowed" : "pointer",
          }}
        >
          {loading ? "Updating…" : "🔄 Refresh"}
        </button>
      </div>
    </div>
  );
}

  return (
    <div className="glass reveal" style={{ borderRadius: "1.5rem", padding: "1.5rem", transitionDelay: "240ms" }}>
      <div className="overline" style={{ marginBottom: "0.75rem" }}>
        <span className="overline-dash" />🏠 Smart Indoor Air Quality
      </div>

      <div style={{ fontSize: "0.75rem", color: "var(--muted-foreground)", marginBottom: "1.5rem", lineHeight: 1.5 }}>
        AI-powered recommendations based on current outdoor AQI and 24-hour forecast.
      </div>

      {/* Window + Purifier cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: "1rem", marginBottom: "1.5rem" }}>

        {/* Window advice */}
        <div style={{
          padding: "1rem", borderRadius: "0.75rem",
          background: "rgba(255,255,255,0.02)",
          border: `1px solid ${getActionBorderColor(window_advice.action)}`,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.5rem" }}>
            <span style={{ fontSize: "1.25rem" }}>{getActionIcon(window_advice.action)}</span>
            <span style={{ fontSize: "0.8125rem", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.08em" }}>
              Windows
            </span>
          </div>
          <p style={{ fontSize: "0.75rem", lineHeight: 1.55, marginBottom: "0.35rem" }}>
            {window_advice.message}
          </p>
          {window_advice.duration && (
            <p style={{ fontSize: "0.6875rem", color: "var(--muted-foreground)" }}>
              {window_advice.duration}
            </p>
          )}
        </div>

        {/* Purifier advice */}
        <div style={{
          padding: "1rem", borderRadius: "0.75rem",
          background: "rgba(255,255,255,0.02)",
          border: `1px solid ${getActionBorderColor(purifier_advice.setting)}`,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.5rem" }}>
            <span style={{ fontSize: "1.25rem" }}>{getActionIcon(purifier_advice.setting)}</span>
            <span style={{ fontSize: "0.8125rem", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.08em" }}>
              Air Purifier
            </span>
          </div>
          <p style={{ fontSize: "0.75rem", lineHeight: 1.55, marginBottom: "0.35rem" }}>
            {purifier_advice.message}
          </p>
          <p style={{ fontSize: "0.6875rem", color: "var(--muted-foreground)" }}>
            Runtime: {purifier_advice.runtime}
          </p>
        </div>
      </div>

      {/* Activity guidelines */}
      <div style={{ marginBottom: "1.5rem" }}>
        <h4 style={{ fontSize: "0.8125rem", fontWeight: 600, marginBottom: "0.75rem", textTransform: "uppercase", letterSpacing: "0.08em" }}>
          Indoor Activity Guidelines
        </h4>
        <div style={{ display: "grid", gap: "0.5rem" }}>
          {Object.entries(activity_advice).map(([activity, advice]) => (
            <div key={activity} style={{
              padding: "0.75rem", borderRadius: "0.5rem",
              background: "rgba(255,255,255,0.02)",
              border: "1px solid var(--border)",
              display: "flex", gap: "0.75rem"
            }}>
              <span style={{ fontSize: "0.6875rem", fontWeight: 700, textTransform: "uppercase", color: "var(--accent)", minWidth: "60px" }}>
                {activity}
              </span>
              <span style={{ fontSize: "0.75rem", lineHeight: 1.4 }}>{advice}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Optimal ventilation windows */}
      {recommendations.optimal_ventilation_times.length > 0 && (
        <div style={{ marginBottom: "1.25rem" }}>
          <h4 style={{ fontSize: "0.8125rem", fontWeight: 600, marginBottom: "0.75rem", textTransform: "uppercase", letterSpacing: "0.08em" }}>
            🌿 Optimal Ventilation Windows
          </h4>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem" }}>
            {recommendations.optimal_ventilation_times.map((t, i) => (
              <span key={i} style={{
                padding: "0.25rem 0.75rem", borderRadius: "9999px",
                background: "oklch(0.75 0.11 162 / 0.1)",
                border: "1px solid oklch(0.75 0.11 162 / 0.3)",
                color: "oklch(0.75 0.11 162)",
                fontSize: "0.75rem", fontFamily: "var(--font-mono)", fontWeight: 500,
              }}>
                {t}
              </span>
            ))}
          </div>
          <p style={{ fontSize: "0.6875rem", color: "var(--muted-foreground)", marginTop: "0.5rem" }}>
            Best hours for natural ventilation based on 24h AQI forecast.
          </p>
        </div>
      )}

      {/* Refresh */}
      <div style={{ paddingTop: "1rem", borderTop: "1px solid var(--border)" }}>
        <button
          onClick={fetchRecommendations}
          disabled={loading}
          style={{
            background: "rgba(255,255,255,0.05)",
            border: "1px solid var(--border)",
            borderRadius: "0.5rem",
            padding: "0.4rem 1rem",
            fontSize: "0.75rem",
            color: "var(--foreground)",
            cursor: loading ? "not-allowed" : "pointer",
          }}
        >
          {loading ? "Updating…" : "🔄 Refresh"}
        </button>
      </div>
    </div>
  );
}
