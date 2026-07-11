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

  const API_BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

  useEffect(() => {
    fetchRecommendations();
  }, [userId]);

  const fetchRecommendations = async () => {
    if (!userId) return;
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE_URL}/indoor-recommendations/${userId}`);
      if (!response.ok) {
        throw new Error('Failed to fetch indoor recommendations');
      }
      const data = await response.json();
      setRecommendations(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const getActionIcon = (action: string) => {
    switch (action) {
      case "open_windows": return "🌬️";
      case "selective_ventilation": return "🪟";
      case "keep_closed": return "🚫";
      case "max_speed": return "💨";
      case "high_speed": return "🔄";
      case "medium_speed": return "⚙️";
      case "low_or_off": return "✨";
      default: return "💡";
    }
  };

  const getActionColor = (action: string) => {
    if (action.includes("open") || action === "low_or_off") return "oklch(0.75 0.11 162)";
    if (action.includes("selective") || action.includes("medium")) return "oklch(0.82 0.11 95)";
    if (action.includes("closed") || action.includes("max")) return "oklch(0.72 0.14 32)";
    return "oklch(0.78 0.14 36)";
  };

  if (loading) {
    return (
      <div className="glass reveal" style={{ borderRadius: "1.5rem", padding: "1.5rem", transitionDelay: "240ms" }}>
        <div className="overline" style={{ marginBottom: "1rem" }}>
          <span className="overline-dash" />🏠 Smart Indoor Air Quality
        </div>
        <div style={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: "200px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
            <span className="loader-ring" />
            <span style={{ fontSize: "0.875rem", color: "var(--muted-foreground)" }}>
              Generating personalized indoor air quality recommendations...
            </span>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="glass reveal" style={{ borderRadius: "1.5rem", padding: "1.5rem", transitionDelay: "240ms" }}>
        <div className="overline" style={{ marginBottom: "1rem" }}>
          <span className="overline-dash" />🏠 Smart Indoor Air Quality
        </div>
        <div style={{ textAlign: "center", padding: "2rem" }}>
          <div style={{ fontSize: "2rem", marginBottom: "1rem" }}>🏠</div>
          <div style={{ color: "var(--muted-foreground)", fontSize: "0.875rem", marginBottom: "1rem" }}>
            Unable to load indoor recommendations: {error}
          </div>
          <button
            onClick={fetchRecommendations}
            style={{
              background: "rgba(255,255,255,0.05)",
              border: "1px solid var(--border)",
              borderRadius: "0.5rem",
              padding: "0.5rem 1rem",
              fontSize: "0.75rem",
              color: "var(--foreground)",
              cursor: "pointer",
              transition: "all 0.2s"
            }}
          >
            🔄 Try Again
          </button>
        </div>
      </div>
    );
  }

  if (!recommendations) {
    return null;
  }

  return (
    <div className="glass reveal" style={{ borderRadius: "1.5rem", padding: "1.5rem", transitionDelay: "240ms" }}>
      <div className="overline" style={{ marginBottom: "1rem" }}>
        <span className="overline-dash" />🏠 Smart Indoor Air Quality
      </div>
      
      <div style={{ fontSize: "0.75rem", color: "var(--muted-foreground)", marginBottom: "1.5rem", lineHeight: 1.5 }}>
        AI-powered recommendations for optimizing your indoor air quality based on current outdoor conditions and 24-hour forecasts.
      </div>

      {/* Quick Actions Grid */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "1rem", marginBottom: "1.5rem" }}>
        
        {/* Window Management */}
        <div style={{
          padding: "1rem",
          borderRadius: "0.75rem",
          background: "rgba(255,255,255,0.02)",
          border: `1px solid ${getActionColor(recommendations.recommendations.window_advice.action).replace(")", " / 0.3)")}`,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.5rem" }}>
            <span style={{ fontSize: "1.125rem" }}>{getActionIcon(recommendations.recommendations.window_advice.action)}</span>
            <span style={{ fontSize: "0.8125rem", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.1em" }}>
              Window Management
            </span>
          </div>
          <p style={{ fontSize: "0.75rem", lineHeight: 1.5, marginBottom: "0.5rem" }}>
            {recommendations.recommendations.window_advice.message}
          </p>
          {recommendations.recommendations.window_advice.duration && (
            <p style={{ fontSize: "0.6875rem", color: "var(--muted-foreground)" }}>
              {recommendations.recommendations.window_advice.duration}
            </p>
          )}
        </div>

        {/* Air Purifier Settings */}
        <div style={{
          padding: "1rem",
          borderRadius: "0.75rem",
          background: "rgba(255,255,255,0.02)",
          border: `1px solid ${getActionColor(recommendations.recommendations.purifier_advice.setting).replace(")", " / 0.3)")}`,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.5rem" }}>
            <span style={{ fontSize: "1.125rem" }}>{getActionIcon(recommendations.recommendations.purifier_advice.setting)}</span>
            <span style={{ fontSize: "0.8125rem", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.1em" }}>
              Air Purifier
            </span>
          </div>
          <p style={{ fontSize: "0.75rem", lineHeight: 1.5, marginBottom: "0.5rem" }}>
            {recommendations.recommendations.purifier_advice.message}
          </p>
          <p style={{ fontSize: "0.6875rem", color: "var(--muted-foreground)" }}>
            Runtime: {recommendations.recommendations.purifier_advice.runtime}
          </p>
        </div>
      </div>

      {/* Activity Recommendations */}
      <div style={{ marginBottom: "1.5rem" }}>
        <h4 style={{ fontSize: "0.8125rem", fontWeight: 600, marginBottom: "0.75rem", textTransform: "uppercase", letterSpacing: "0.1em" }}>
          Indoor Activity Guidelines
        </h4>
        <div style={{ display: "grid", gap: "0.5rem" }}>
          {Object.entries(recommendations.recommendations.activity_advice).map(([activity, advice]) => (
            <div key={activity} style={{
              padding: "0.75rem",
              borderRadius: "0.5rem",
              background: "rgba(255,255,255,0.02)",
              border: "1px solid var(--border)",
              display: "flex",
              gap: "0.75rem"
            }}>
              <span style={{ fontSize: "0.6875rem", fontWeight: 700, textTransform: "uppercase", color: "var(--accent)", minWidth: "60px" }}>
                {activity}
              </span>
              <span style={{ fontSize: "0.75rem", lineHeight: 1.4 }}>
                {advice}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Optimal Ventilation Times */}
      {recommendations.optimal_ventilation_times.length > 0 && (
        <div>
          <h4 style={{ fontSize: "0.8125rem", fontWeight: 600, marginBottom: "0.75rem", textTransform: "uppercase", letterSpacing: "0.1em" }}>
            🌿 Optimal Ventilation Windows (Next 24h)
          </h4>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem" }}>
            {recommendations.optimal_ventilation_times.map((time, index) => (
              <span key={index} style={{
                padding: "0.25rem 0.75rem",
                borderRadius: "9999px",
                background: "oklch(0.75 0.11 162 / 0.1)",
                border: "1px solid oklch(0.75 0.11 162 / 0.3)",
                color: "oklch(0.75 0.11 162)",
                fontSize: "0.75rem",
                fontFamily: "var(--font-mono)",
                fontWeight: 500
              }}>
                {time}
              </span>
            ))}
          </div>
          <p style={{ fontSize: "0.6875rem", color: "var(--muted-foreground)", marginTop: "0.5rem" }}>
            These are the cleanest air hours for natural ventilation based on AQI predictions.
          </p>
        </div>
      )}

      {/* Refresh Button */}
      <div style={{ marginTop: "1.5rem", paddingTop: "1rem", borderTop: "1px solid var(--border)" }}>
        <button
          onClick={fetchRecommendations}
          disabled={loading}
          style={{
            background: "rgba(255,255,255,0.05)",
            border: "1px solid var(--border)",
            borderRadius: "0.5rem",
            padding: "0.5rem 1rem",
            fontSize: "0.75rem",
            color: "var(--foreground)",
            cursor: loading ? "not-allowed" : "pointer",
            transition: "all 0.2s"
          }}
        >
          {loading ? "Updating..." : "🔄 Refresh Recommendations"}
        </button>
      </div>
    </div>
  );
}