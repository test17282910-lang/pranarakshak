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
}

export default function SmartIndoorRecommendations({ userId, currentAqi }: SmartIndoorRecommendationsProps) {
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

  // ── Full render ────────────────────────────────────────────────────────────
  const { window_advice, purifier_advice, activity_advice } = recommendations.recommendations;

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
