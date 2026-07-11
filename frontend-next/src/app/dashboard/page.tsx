"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import SmartIndoorRecommendations from "../../components/SmartIndoorRecommendations";

interface UserProfile {
  id: string;
  name: string;
  phone: string | null;
  email: string | null;
  condition: string;
  severity: string;
  last_known_lat: number | null;
  last_known_lon: number | null;
  symptoms: string[] | null;
  personalized_issue: string | null;
}

interface PrecautionItem {
  category: "general" | "condition" | "symptom" | "trigger";
  text: string;
}

interface RiskExplanation {
  raw_aqi: number;
  condition: string;
  severity: string;
  condition_shift: number;
  symptom_count: number;
  symptom_penalty: number;
  effective_aqi: number;
  threshold_crossed: string;
  method: string;
  why_be_careful?: string;
  severity_multiplier?: number;
  symptom_weights?: Record<string, number>;
}

interface PredictionData {
  user_id: string;
  current_aqi?: number;
  air_quality_tier?: string;
  predicted_aqi_raw: number;
  predicted_aqi_adjusted: number;
  rmse_buffer: number;
  prediction_confidence: number;
  prediction_source: string;
  alert_tier: string;
  alert_message: string;
  precautions: PrecautionItem[];
  risk_explanation?: RiskExplanation;
  safe_hours?: string[];
  aqi_trend?: "improving" | "worsening" | "stable";
  timestamp: string;
  forecast_for: string;
}

// ── India NAQI Air Quality Classification ────────────────────────────────────
function naqi_air_quality_tier(aqi: number): string {
  if (aqi <= 50) return "Good";
  if (aqi <= 100) return "Satisfactory"; 
  if (aqi <= 200) return "Moderate";
  if (aqi <= 300) return "Poor";
  if (aqi <= 400) return "Very Poor";
  return "Severe";
}

// ── Air Quality Tier helpers (India NAQI) ────────────────────────────────────
function getAqiTierColor(tier: string): string {
  switch (tier?.toLowerCase()) {
    case "good":         return "oklch(0.75 0.11 162)";
    case "satisfactory": return "oklch(0.82 0.11 95)";
    case "moderate":     return "oklch(0.82 0.09 55)";
    case "poor":         return "oklch(0.72 0.14 32)";
    case "very poor":    return "oklch(0.62 0.18 28)";
    case "severe":       return "oklch(0.52 0.20 12)";
    default:             return "oklch(0.75 0.11 162)";
  }
}

function getAqiTierHue(tier: string): string {
  switch (tier?.toLowerCase()) {
    case "good":         return "162";
    case "satisfactory": return "95";
    case "moderate":     return "55";
    case "poor":         return "32";
    case "very poor":    return "28";
    case "severe":       return "12";
    default:             return "162";
  }
}

// ── Health Risk Tier helpers (Personalized: Safe/Caution/High Risk/Critical) ─
function getHealthRiskColor(tier: string): string {
  switch (tier?.toLowerCase()) {
    case "safe":      return "oklch(0.75 0.11 162)";
    case "caution":   return "oklch(0.82 0.11 78)";
    case "high risk": return "oklch(0.78 0.14 36)";
    case "critical":  return "oklch(0.62 0.20 18)";
    default:          return "oklch(0.75 0.11 162)";
  }
}

// Aliases for the Orb — driven by air quality tier
function getTierColor(tier: string): string { return getAqiTierColor(tier); }
function getTierHue(tier: string): string   { return getAqiTierHue(tier); }

function getAqiPercent(aqi: number): number {
  return Math.min(100, Math.max(0, (aqi / 500) * 100));
}

function getConfidenceLabel(std: number): string {
  if (std < 5)  return "Very High";
  if (std < 10) return "High";
  if (std < 20) return "Moderate";
  return "Low";
}

// ── Comfort Ring SVG ─────────────────────────────────────────────────────────
function ComfortRing({ value, label, sublabel, hue = "162" }: { value: number; label: string; sublabel?: string; hue?: string }) {
  const r = 45;
  const c = 2 * Math.PI * r;
  const offset = c - (c * value) / 100;
  return (
    <div className="comfort-ring-wrap">
      <div style={{ position: "relative", width: 80, height: 80 }}>
        <svg viewBox="0 0 100 100" style={{ width: "100%", height: "100%", transform: "rotate(-90deg)" }}>
          <circle cx="50" cy="50" r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="3" />
          <circle
            cx="50" cy="50" r={r} fill="none"
            stroke={`oklch(0.78 0.10 ${hue})`} strokeWidth="3"
            strokeLinecap="round" strokeDasharray={c} strokeDashoffset={offset}
            style={{ filter: `drop-shadow(0 0 6px oklch(0.78 0.10 ${hue} / 0.6))`, transition: "stroke-dashoffset 1.2s cubic-bezier(0.16,1,0.3,1)" }}
          />
        </svg>
        <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
          <span style={{ fontFamily: "var(--font-display)", fontSize: "1.25rem", fontWeight: 200 }}>{value}</span>
          {sublabel && <span style={{ fontSize: "0.5rem", textTransform: "uppercase", letterSpacing: "0.2em", color: "var(--muted-foreground)", marginTop: "0.1rem" }}>{sublabel}</span>}
        </div>
      </div>
      <span className="comfort-ring-label">{label}</span>
    </div>
  );
}

// ── Atmospheric Orb ──────────────────────────────────────────────────────────
function AtmosphericOrb({ aqi, tier }: { aqi: number; tier: string }) {
  const color = getTierColor(tier);
  const pct   = getAqiPercent(aqi);
  const r = 45;
  const c = 2 * Math.PI * r;

  return (
    <div className="atmo-orb-wrap" style={{ maxWidth: 300 }}>
      {/* Rotating rings */}
      {[{ size: 280, dur: "60s" }, { size: 230, dur: "45s", reverse: true }, { size: 180, dur: "30s" }].map((ring, i) => (
        <svg key={i} viewBox="0 0 100 100" style={{
          position: "absolute",
          width: ring.size, height: ring.size,
          opacity: 0.1 + i * 0.03,
          animation: `ring-rotate ${ring.dur} linear ${(ring as any).reverse ? "reverse" : "normal"} infinite`,
        }}>
          <circle cx="50" cy="50" r="48" fill="none" stroke="currentColor" strokeWidth="0.2" strokeDasharray={i === 0 ? "1 12" : i === 1 ? "2 8" : "1 5"} />
        </svg>
      ))}

      {/* Tick marks */}
      <svg viewBox="0 0 100 100" style={{ position: "absolute", width: 320, height: 320, opacity: 0.35 }}>
        {Array.from({ length: 72 }).map((_, i) => {
          const angle = (i / 72) * Math.PI * 2;
          const long  = i % 6 === 0;
          const inner = long ? 44 : 45.5;
          return (
            <line key={i}
              x1={50 + Math.cos(angle) * inner} y1={50 + Math.sin(angle) * inner}
              x2={50 + Math.cos(angle) * 47}    y2={50 + Math.sin(angle) * 47}
              stroke="currentColor" strokeWidth={long ? 0.3 : 0.12}
            />
          );
        })}
      </svg>

      {/* Core */}
      <div className="atmo-core" style={{
        background: `radial-gradient(circle at 32% 28%, oklch(0.88 0.10 ${getTierHue(tier)} / 0.9), oklch(0.55 0.12 ${getTierHue(tier)} / 0.7) 45%, oklch(0.20 0.04 250 / 0.5) 80%)`,
        boxShadow: `inset -12px -20px 40px rgba(0,0,0,0.45), inset 12px 18px 40px rgba(255,255,255,0.12), 0 0 100px ${color.replace(")", " / 0.35)")}`,
      }}>
        <span className="atmo-core-label">24h Forecast</span>
        <span className="atmo-core-value">{Math.round(aqi)}</span>
        <span className="atmo-core-tier">{tier}</span>
      </div>
    </div>
  );
}

// ── Main Dashboard ───────────────────────────────────────────────────────────
export default function Dashboard() {
  const [userIdInput, setUserIdInput]   = useState("");
  const [userId, setUserId]             = useState<string | null>(null);
  const [profile, setProfile]           = useState<UserProfile | null>(null);
  const [prediction, setPrediction]     = useState<PredictionData | null>(null);
  const [alerts, setAlerts]             = useState<any[]>([]);
  const [loading, setLoading]           = useState(false);
  const [error, setError]               = useState<string | null>(null);
  const [locationStatus, setLocationStatus] = useState<string | null>(null);
  const [dockHidden, setDockHidden]     = useState(false);
  const lastScroll = useRef(0);
  const fetchCalledRef = useRef(false);

  const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  const fetchAlerts = async (id: string) => {
    try {
      const res = await fetch(`${API_BASE_URL}/users/${id}/alerts`);
      if (res.ok) {
        const data = await res.json();
        setAlerts(data || []);
      }
    } catch (err) {
      console.error("Failed to load alert log history:", err);
    }
  };

  // Scroll reveal
  useEffect(() => {
    const els = document.querySelectorAll(".reveal");
    const obs = new IntersectionObserver(
      (entries) => entries.forEach((e) => { if (e.isIntersecting) e.target.classList.add("visible"); }),
      { threshold: 0.06 }
    );
    els.forEach((el) => obs.observe(el));
    return () => obs.disconnect();
  }, [prediction]);

  // Dock hide
  useEffect(() => {
    const onScroll = () => {
      const y = window.scrollY;
      setDockHidden(y > lastScroll.current && y > 80);
      lastScroll.current = y;
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  // Auto-load from URL / localStorage
  useEffect(() => {
    if (fetchCalledRef.current) return;
    const params  = new URLSearchParams(window.location.search);
    const urlId   = params.get("user_id");
    const storedId = localStorage.getItem("aqi_user_id");
    const finalId = urlId || storedId;
    if (finalId) {
      fetchCalledRef.current = true;
      setUserId(finalId);
      setUserIdInput(finalId);
      fetchUserData(finalId);
    }
  }, []);

  const autoCheckAndUpdateLocation = (profileData: UserProfile) => {
    if (!navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const { latitude: lat, longitude: lon } = pos.coords;
        const oldLat = profileData.last_known_lat;
        const oldLon = profileData.last_known_lon;
        
        // If location is not set or changed by > 0.015 degrees (~1.5km), update it in background
        if (oldLat === null || oldLon === null || Math.abs(lat - oldLat) > 0.015 || Math.abs(lon - oldLon) > 0.015) {
          setLocationStatus("Relocating: updating to current location…");
          try {
            await fetch(`${API_BASE_URL}/update-location`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ user_id: profileData.id, lat, lon }),
            });
            const predictRes = await fetch(`${API_BASE_URL}/predict`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                user_id: profileData.id,
                lat,
                lon,
                condition: profileData.condition,
                severity: profileData.severity
              }),
            });
            if (predictRes.ok) {
              setPrediction(await predictRes.json());
              setProfile((prev) => prev ? { ...prev, last_known_lat: lat, last_known_lon: lon } : null);
              setLocationStatus("✓ Location updated to current city");
              setTimeout(() => setLocationStatus(null), 3000);
            }
          } catch (err) {
            console.error("Auto location update failed:", err);
          }
        }
      },
      (err) => {
        console.log("Automatic location check declined/failed:", err.message);
      },
      { enableHighAccuracy: false, timeout: 5000, maximumAge: 300000 }
    );
  };

  const fetchUserData = async (id: string) => {
    setLoading(true); setError(null);
    try {
      const profileRes = await fetch(`${API_BASE_URL}/users/${id}`);
      if (!profileRes.ok) throw new Error(profileRes.status === 404 ? "User ID not found." : "Failed to load profile.");
      const profileData: UserProfile = await profileRes.json();
      setProfile(profileData);
      localStorage.setItem("aqi_user_id", id);

      const lat = profileData.last_known_lat ?? 17.385044;
      const lon = profileData.last_known_lon ?? 78.486671;

      const predictRes = await fetch(`${API_BASE_URL}/predict`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: id, lat, lon, condition: profileData.condition, severity: profileData.severity }),
      });
      if (!predictRes.ok) throw new Error("Failed to generate prediction.");
      const predictData = await predictRes.json();
      setPrediction(predictData);
      fetchAlerts(id);

      // Trigger automatic background relocation check
      autoCheckAndUpdateLocation(profileData);
    } catch (err: any) {
      setError(err.message || "Unexpected error.");
    } finally {
      setLoading(false);
    }
  };

  const handleIdSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const id = userIdInput.trim();
    if (id) { setUserId(id); fetchUserData(id); window.history.pushState({}, "", `/dashboard?user_id=${id}`); }
  };

  const handleLogout = () => {
    localStorage.removeItem("aqi_user_id");
    setUserId(null); setProfile(null); setPrediction(null); setUserIdInput("");
    window.history.pushState({}, "", "/dashboard");
  };

  const handleRefreshPrediction = () => {
    if (!profile || !userId) return;
    setLocationStatus("Accessing GPS…");
    if (!navigator.geolocation) { setLocationStatus("Geolocation unsupported."); return; }
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const { latitude: lat, longitude: lon } = pos.coords;
        setLocationStatus(`✓ Location secured`);
        try {
          setLoading(true);
          await fetch(`${API_BASE_URL}/update-location`, {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ user_id: userId, lat, lon }),
          });
          const predictRes = await fetch(`${API_BASE_URL}/predict`, {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ user_id: userId, lat, lon, condition: profile.condition, severity: profile.severity }),
          });
          if (!predictRes.ok) throw new Error("Failed to fetch prediction.");
          setPrediction(await predictRes.json());
          setProfile((prev) => prev ? { ...prev, last_known_lat: lat, last_known_lon: lon } : null);
          fetchAlerts(userId);
        } catch (err: any) {
          setError(err.message);
        } finally {
          setLoading(false);
          setTimeout(() => setLocationStatus(null), 3500);
        }
      },
      () => { setLocationStatus("GPS access denied."); setTimeout(() => setLocationStatus(null), 3000); },
      { enableHighAccuracy: true, timeout: 5000 }
    );
  };

  // ── Render: Login Screen ───────────────────────────────────────────────────
  if (!userId || (!loading && !profile && !error)) {
    return (
      <>
        <header className="topbar">
          <div className="topbar-inner">
            <Link href="/" className="logo" style={{ textDecoration: "none", color: "var(--foreground)" }}>
              <div className="logo-orb"><div className="logo-orb-inner" /></div>
              <span className="logo-name">Pranarakshak</span>
            </Link>
            <div className="topbar-status">
              <span className="live-dot animate-pulse" />
              Live · India · CPCB
            </div>
            <nav className="nav-links">
              <Link href="/" className="nav-link">Register</Link>
              <Link href="/login" className="nav-link">Login</Link>
              <Link href="/dashboard" className="nav-link active">Dashboard</Link>
            </nav>
          </div>
        </header>

        <div className="login-wrap">
          <div className="glass login-card">
            <div className="login-header">
              <div style={{ width: 56, height: 56, borderRadius: "50%", background: `rgba(var(--accent-rgb), 0.15)`, border: `1px solid rgba(var(--accent-rgb), 0.25)`, display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 1.5rem", fontSize: "1.25rem" }}>
                ⬡
              </div>
              <h1 className="login-title">Your Dashboard</h1>
              <p className="login-subtitle">Enter your User ID to load your personalised AQI intelligence.</p>
            </div>

            <form onSubmit={handleIdSubmit}>
              <div className="form-group">
                <label htmlFor="user_id_input">User ID</label>
                <input
                  type="text" id="user_id_input" required
                  placeholder="e.g. usr_abc123…"
                  value={userIdInput}
                  onChange={(e) => setUserIdInput(e.target.value)}
                  style={{ fontFamily: "var(--font-mono)", fontSize: "0.875rem" }}
                />
              </div>
              <button type="submit" className="btn-primary" disabled={loading || !userIdInput.trim()}>
                {loading ? <><span className="loader-ring" /> Loading…</> : "View My AQI →"}
              </button>
            </form>

            {error && <div className="feedback-msg error" style={{ marginTop: "1rem" }}>{error}</div>}

            <div style={{ marginTop: "2rem", textAlign: "center", paddingTop: "1.5rem", borderTop: "1px solid var(--border)" }}>
              <p style={{ fontSize: "0.8125rem", color: "var(--muted-foreground)" }}>
                No account yet?{" "}
                <Link href="/" style={{ color: "var(--accent)", textDecoration: "none", fontWeight: 500 }}>Register here</Link>
              </p>
            </div>
          </div>
        </div>

        <nav className={`command-dock${dockHidden ? " hidden" : ""}`}>
          <div className="glass dock-inner" style={{ justifyContent: "space-between", padding: "0.75rem 1.5rem" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
              <div style={{ 
                width: 32, 
                height: 32, 
                borderRadius: "50%", 
                background: "var(--gradient-orb)", 
                display: "flex", 
                alignItems: "center", 
                justifyContent: "center",
                fontSize: "0.875rem"
              }}>
                {profile?.name?.charAt(0).toUpperCase() || "?"}
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: "0.125rem" }}>
                <span style={{ fontSize: "0.875rem", fontWeight: 500 }}>{profile?.name || "User"}</span>
                <span style={{ fontSize: "0.75rem", color: "var(--muted-foreground)" }}>
                  {profile?.condition?.toUpperCase()} · {profile?.severity}
                </span>
              </div>
            </div>
            <button 
              onClick={handleLogout} 
              className="dock-item"
              style={{ 
                background: "rgba(255,255,255,0.05)", 
                border: "1px solid var(--border)",
                borderRadius: "0.5rem",
                padding: "0.5rem 1rem",
                fontSize: "0.8125rem",
                cursor: "pointer",
                transition: "all 0.2s"
              }}
            >
              Sign Out →
            </button>
          </div>
        </nav>
      </>
    );
  }

  // ── Render: Loading State ──────────────────────────────────────────────────
  if (loading && !prediction) {
    return (
      <>
        <header className="topbar">
          <div className="topbar-inner">
            <Link href="/" className="logo" style={{ textDecoration: "none", color: "var(--foreground)" }}>
              <div className="logo-orb"><div className="logo-orb-inner" /></div>
              <span className="logo-name">Pranarakshak</span>
            </Link>
          </div>
        </header>
        <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: "2rem", position: "relative", zIndex: 1 }}>
          <div style={{
            width: 80, height: 80, borderRadius: "50%",
            background: "var(--gradient-orb)",
            animation: "orb-pulse 2s ease-in-out infinite",
            boxShadow: "0 0 80px rgba(var(--accent-rgb), 0.3)",
          }} />
          <div style={{ textAlign: "center" }}>
            <p className="font-display" style={{ fontSize: "1.5rem", fontWeight: 300 }}>Reading the atmosphere…</p>
            <p style={{ color: "var(--muted-foreground)", fontSize: "0.875rem", marginTop: "0.5rem" }}>Fetching CPCB station data & running LSTM forecast</p>
          </div>
        </div>
      </>
    );
  }

  // ── Render: Error State ────────────────────────────────────────────────────
  if (error && !prediction) {
    return (
      <>
        <header className="topbar">
          <div className="topbar-inner">
            <Link href="/" className="logo" style={{ textDecoration: "none", color: "var(--foreground)" }}>
              <div className="logo-orb"><div className="logo-orb-inner" /></div>
              <span className="logo-name">Pranarakshak</span>
            </Link>
          </div>
        </header>
        <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: "1.5rem", padding: "2rem", position: "relative", zIndex: 1 }}>
          <div style={{ fontSize: "2rem" }}>✕</div>
          <h2 className="font-display" style={{ fontSize: "1.75rem", fontWeight: 300 }}>Something went wrong</h2>
          <p style={{ color: "var(--muted-foreground)", textAlign: "center", maxWidth: "36ch" }}>{error}</p>
          <button className="btn-secondary" onClick={handleLogout}>← Try Again</button>
        </div>
      </>
    );
  }

  // ── Render: Full Dashboard ─────────────────────────────────────────────────
  const currentAqi   = prediction?.current_aqi ?? 0;
  const predictedAqi = prediction?.predicted_aqi_adjusted ?? 0;
  const pct          = getAqiPercent(predictedAqi); // Use predicted for main calculations

  // Derived color/hue values for styling
  const tierHue = prediction ? getTierHue(naqi_air_quality_tier(predictedAqi)) : "162";
  const tierColor = prediction ? getTierColor(naqi_air_quality_tier(predictedAqi)) : "oklch(0.75 0.11 162)";

  // Derive comfort ring values from predicted AQI
  const pm25Score  = prediction ? Math.max(0, 100 - getAqiPercent(prediction.predicted_aqi_adjusted)) : 50;
  const confScore  = prediction ? Math.min(100, 100 - (prediction.prediction_confidence / 50) * 100) : 50;
  const safetyScore = Math.max(0, 100 - pct);

  return (
    <>
      {/* ── Top Bar ── */}
      <header className="topbar">
        <div className="topbar-inner">
          <Link href="/" className="logo" style={{ textDecoration: "none", color: "var(--foreground)" }}>
            <div className="logo-orb"><div className="logo-orb-inner" /></div>
            <span className="logo-name">Pranarakshak</span>
          </Link>
          <div className="topbar-status">
            <span className="live-dot animate-pulse" />
            Live · India · CPCB
          </div>
          <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
            {profile && (
              <>
                <button onClick={handleRefreshPrediction} disabled={loading} className="btn-secondary" style={{ fontSize: "0.75rem" }}>
                  {loading ? <span className="loader-ring" /> : "📍 Update Location"}
                </button>
                <button onClick={() => fetchUserData(userId!)} disabled={loading} className="btn-secondary" style={{ fontSize: "0.75rem" }}>
                  {loading ? <span className="loader-ring" /> : "↺ Refresh Data"}
                </button>
              </>
            )}
            <button onClick={handleLogout} className="btn-secondary" style={{ fontSize: "0.75rem" }}>Sign Out</button>
          </div>
        </div>
      </header>

      {/* Feature Navigation Bar */}
      {/* TODO: Uncomment when features are ready for production
      {profile && (
        <div style={{
          background: "rgba(18, 18, 18, 0.6)",
          backdropFilter: "blur(20px)",
          borderBottom: "1px solid rgba(242, 240, 232, 0.08)",
          position: "sticky",
          top: 0,
          zIndex: 50,
          padding: "1rem 0"
        }}>
          <div style={{ maxWidth: 1200, margin: "0 auto", padding: "0 2rem" }}>
            <div style={{ display: "flex", gap: "1rem", overflowX: "auto" }}>
              <Link 
                href="/medications"
                className="btn-secondary"
                style={{
                  fontSize: "0.875rem",
                  whiteSpace: "nowrap",
                  background: "rgba(59, 130, 246, 0.1)",
                  border: "1px solid rgba(59, 130, 246, 0.2)"
                }}
              >
                💊 Medications
              </Link>
              <Link 
                href="/family-groups"
                className="btn-secondary"
                style={{
                  fontSize: "0.875rem",
                  whiteSpace: "nowrap",
                  background: "rgba(168, 85, 247, 0.1)",
                  border: "1px solid rgba(168, 85, 247, 0.2)"
                }}
              >
                👨‍👩‍👧‍👦 Family Groups
              </Link>
              <Link 
                href="/emergency-contacts"
                className="btn-secondary"
                style={{
                  fontSize: "0.875rem",
                  whiteSpace: "nowrap",
                  background: "rgba(239, 68, 68, 0.1)",
                  border: "1px solid rgba(239, 68, 68, 0.2)"
                }}
              >
                🚨 Emergency Contacts
              </Link>
            </div>
          </div>
        </div>
      )}
      */}

      <main className="dashboard-wrap" style={{ position: "relative", zIndex: 1 }}>
        <div style={{ maxWidth: 1200, margin: "0 auto", padding: "0 2rem" }}>

          {/* Page header */}
          <div className="reveal" style={{ marginBottom: "3rem" }}>
            <div className="overline" style={{ marginBottom: "0.75rem" }}>
              <span className="overline-dash" />
              Live Intelligence
            </div>
            <h1 className="font-display" style={{ fontSize: "clamp(2.5rem, 5vw, 4rem)", fontWeight: 300, letterSpacing: "-0.02em" }}>
              Your air, <em style={{ color: "rgba(242,240,232,0.55)" }}>right now.</em>
            </h1>
            {locationStatus && (
              <p style={{ color: "var(--accent)", fontSize: "0.8125rem", marginTop: "0.5rem" }}>{locationStatus}</p>
            )}
          </div>

          {prediction && (
            <>
              {/* ── Primary Row ── */}
              <div style={{ display: "grid", gridTemplateColumns: "auto 1fr", gap: "2rem", alignItems: "start", marginBottom: "2rem" }}>

                {/* Atmospheric Orb — colour driven by predicted air quality */}
                <div className="glass reveal" style={{ borderRadius: "1.5rem", padding: "2.5rem", display: "flex", flexDirection: "column", alignItems: "center", gap: "1.5rem", transitionDelay: "0ms" }}>
                  <div style={{ position: "relative" }}>
                    <AtmosphericOrb aqi={predictedAqi} tier={naqi_air_quality_tier(predictedAqi)} />
                    <div style={{
                      position: "absolute",
                      top: "-0.5rem",
                      right: "-0.5rem",
                      background: "oklch(0.78 0.10 210)",
                      color: "white",
                      fontSize: "0.625rem",
                      fontWeight: 700,
                      textTransform: "uppercase",
                      padding: "0.25rem 0.5rem",
                      borderRadius: "9999px",
                      boxShadow: "0 2px 8px rgba(0,0,0,0.3)"
                    }}>
                      24h AI
                    </div>
                  </div>

                  {/* Badges */}
                  <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", justifyContent: "center" }}>
                    <span className="badge badge-accent">{prediction.prediction_source}</span>
                    <span className="badge">{naqi_air_quality_tier(predictedAqi)}</span>
                    <span className="badge" style={{ background: "oklch(0.78 0.10 210 / 0.15)", border: "1px solid oklch(0.78 0.10 210 / 0.3)", color: "oklch(0.78 0.10 210)" }}>
                      Forecast
                    </span>
                  </div>
                </div>

                {/* Right panel */}
                <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>

                  {/* Air Quality vs Health Risk — clearly separated 4-col grid */}
                  <div className="glass reveal" style={{ borderRadius: "1.5rem", padding: "1.75rem", transitionDelay: "80ms" }}>

                    {/* Top: explanatory label */}
                    <div style={{ marginBottom: "1.25rem", paddingBottom: "1rem", borderBottom: "1px solid var(--border)" }}>
                      <div className="overline" style={{ marginBottom: "0.25rem" }}><span className="overline-dash" />Live + Forecast + Personalized Risk</div>
                      <p style={{ fontSize: "0.75rem", color: "var(--muted-foreground)", lineHeight: 1.5 }}>
                        <strong style={{ color: "rgba(242,240,232,0.7)" }}>Current AQI</strong> is live NAQI data from nearby stations.
                        &nbsp;<strong style={{ color: "rgba(242,240,232,0.7)" }}>24h Forecast</strong> is AI-predicted AQI for tomorrow.
                        &nbsp;<strong style={{ color: "rgba(242,240,232,0.7)" }}>Health Risk</strong> is personalised to your condition.
                      </p>
                    </div>

                    {/* 5-col grid: Current AQI | 24h Predicted | AQ tier | Risk tier */}
                    <div style={{ display: "grid", gridTemplateColumns: "1fr auto 1fr auto 1fr auto 1fr", gap: "1.25rem", alignItems: "center" }}>

                      {/* Current AQI number with Trend indicator */}
                      <div>
                        <div className="metric-lbl" style={{ display: "flex", alignItems: "center", gap: "0.375rem" }}>
                          Current AQI
                          {prediction.aqi_trend && (
                            <span style={{
                              fontSize: "0.625rem",
                              fontWeight: 600,
                              textTransform: "uppercase",
                              padding: "0.1rem 0.35rem",
                              borderRadius: "4px",
                              border: `1px solid ${prediction.aqi_trend === "improving" ? "oklch(0.75 0.11 162 / 0.4)" : prediction.aqi_trend === "worsening" ? "oklch(0.72 0.14 32 / 0.4)" : "rgba(255,255,255,0.15)"}`,
                              background: prediction.aqi_trend === "improving" ? "oklch(0.75 0.11 162 / 0.08)" : prediction.aqi_trend === "worsening" ? "oklch(0.72 0.14 32 / 0.08)" : "transparent",
                              color: prediction.aqi_trend === "improving" ? "oklch(0.75 0.11 162)" : prediction.aqi_trend === "worsening" ? "oklch(0.72 0.14 32)" : "var(--muted-foreground)"
                            }}>
                              {prediction.aqi_trend === "improving" ? "↓ Impr" : prediction.aqi_trend === "worsening" ? "↑ Wors" : "→ Stab"}
                            </span>
                          )}
                        </div>
                        <div className="metric-val" style={{ color: getAqiTierColor(prediction.air_quality_tier ?? "good"), fontSize: "2.25rem" }}>
                          {Math.round(currentAqi)}
                        </div>
                        <div className="metric-sub">Live reading</div>
                      </div>

                      <div style={{ width: 1, height: 52, background: "var(--border)" }} />

                      {/* 24h Predicted AQI */}
                      <div>
                        <div className="metric-lbl" style={{ display: "flex", alignItems: "center", gap: "0.375rem" }}>
                          24h Forecast
                          <span style={{
                            fontSize: "0.625rem",
                            fontWeight: 600,
                            textTransform: "uppercase",
                            padding: "0.1rem 0.35rem",
                            borderRadius: "4px",
                            border: "1px solid oklch(0.78 0.10 210 / 0.4)",
                            background: "oklch(0.78 0.10 210 / 0.08)",
                            color: "oklch(0.78 0.10 210)"
                          }}>
                            AI
                          </span>
                        </div>
                        <div className="metric-val" style={{ color: getAqiTierColor(naqi_air_quality_tier(predictedAqi)), fontSize: "2.25rem" }}>
                          {Math.round(predictedAqi)}
                        </div>
                        <div className="metric-sub">
                          {new Date(prediction.forecast_for).toLocaleDateString("en-IN", { 
                            day: "2-digit", 
                            month: "short",
                            hour: "2-digit",
                            minute: "2-digit"
                          })}
                        </div>
                      </div>

                      <div style={{ width: 1, height: 52, background: "var(--border)" }} />

                      {/* Air Quality tier */}
                      <div>
                        <div className="metric-lbl">Air Quality</div>
                        <div style={{
                          marginTop: "0.5rem",
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "0.4rem",
                          padding: "0.35rem 0.875rem",
                          borderRadius: "9999px",
                          border: `1px solid ${getAqiTierColor(prediction.air_quality_tier ?? "good")}`,
                          background: `${getAqiTierColor(prediction.air_quality_tier ?? "good").replace(")", " / 0.12)")}`
                        }}>
                          <span style={{ width: 7, height: 7, borderRadius: "50%", background: getAqiTierColor(prediction.air_quality_tier ?? "good"), display: "inline-block", flexShrink: 0 }} />
                          <span style={{ fontSize: "0.8125rem", fontWeight: 500, color: getAqiTierColor(prediction.air_quality_tier ?? "good") }}>
                            {prediction.air_quality_tier ?? "—"}
                          </span>
                        </div>
                        <div className="metric-sub" style={{ marginTop: "0.35rem" }}>Current (NAQI)</div>
                      </div>

                      <div style={{ width: 1, height: 52, background: "var(--border)" }} />

                      {/* Health Risk tier */}
                      <div>
                        <div className="metric-lbl">Your Health Risk</div>
                        <div style={{
                          marginTop: "0.5rem",
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "0.4rem",
                          padding: "0.35rem 0.875rem",
                          borderRadius: "9999px",
                          border: `1px solid ${getHealthRiskColor(prediction.alert_tier)}`,
                          background: `${getHealthRiskColor(prediction.alert_tier).replace(")", " / 0.12)")}`
                        }}>
                          <span style={{ width: 7, height: 7, borderRadius: "50%", background: getHealthRiskColor(prediction.alert_tier), display: "inline-block", flexShrink: 0 }} />
                          <span style={{ fontSize: "0.8125rem", fontWeight: 500, color: getHealthRiskColor(prediction.alert_tier) }}>
                            {prediction.alert_tier}
                          </span>
                        </div>
                        <div className="metric-sub" style={{ marginTop: "0.35rem" }}>Personalised to you</div>
                      </div>
                    </div>

                    {/* AQI progress bar */}
                    <div style={{ marginTop: "1.5rem" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.6875rem", textTransform: "uppercase", letterSpacing: "0.2em", color: "var(--muted-foreground)", marginBottom: "0.5rem" }}>
                        <span>Good (0)</span>
                        <span>Severe (500)</span>
                      </div>
                      <div style={{ height: "4px", borderRadius: "9999px", background: "rgba(255,255,255,0.07)", overflow: "hidden" }}>
                        <div style={{
                          height: "100%",
                          width: `${pct}%`,
                          borderRadius: "9999px",
                          background: `linear-gradient(90deg, oklch(0.75 0.11 162), ${getAqiTierColor(prediction.air_quality_tier ?? "good")})`,
                          transition: "width 1.2s cubic-bezier(0.16,1,0.3,1)",
                          boxShadow: `0 0 12px ${getAqiTierColor(prediction.air_quality_tier ?? "good").replace(")", " / 0.55)")}`,
                        }} />
                      </div>
                    </div>
                  </div>

                  {/* Alert message */}
                  {prediction.alert_message && (
                    <div className="glass reveal" style={{ borderRadius: "1.25rem", padding: "1.25rem 1.5rem", display: "flex", gap: "0.875rem", alignItems: "flex-start", transitionDelay: "160ms" }}>
                      <span style={{ color: "var(--accent)", fontSize: "1rem", flexShrink: 0 }}>◎</span>
                      <p style={{ fontSize: "0.875rem", lineHeight: 1.65, color: "rgba(242,240,232,0.85)" }}>{prediction.alert_message}</p>
                    </div>
                  )}

                  {/* ── Hackathon Core Feature 1: Personalised Risk Breakdown ── */}
                  {prediction.risk_explanation && (
                    <div className="glass reveal" style={{ borderRadius: "1.5rem", padding: "1.5rem", transitionDelay: "200ms" }}>
                      <div className="overline" style={{ marginBottom: "1rem" }}><span className="overline-dash" />Risk Explainability Model</div>
                      
                      <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                        <div style={{ fontSize: "0.75rem", color: "var(--muted-foreground)", lineHeight: 1.5 }}>
                          Personal susceptibility is computed dynamically. Shift values decrease the threshold at which alert tiers are crossed.
                        </div>
                        
                        {/* Horizontal Formula Flow */}
                        <div style={{
                          display: "flex",
                          alignItems: "center",
                          gap: "0.75rem",
                          flexWrap: "wrap",
                          background: "rgba(255,255,255,0.02)",
                          padding: "1rem",
                          borderRadius: "0.75rem",
                          border: "1px solid var(--border)"
                        }}>
                          <div style={{ textAlign: "center" }}>
                            <div style={{ fontSize: "0.625rem", textTransform: "uppercase", color: "var(--muted-foreground)" }}>Raw AQI</div>
                            {/* FIX Bug 1: round to integer so it matches the 24h Forecast hero card */}
                            <div style={{ fontSize: "1.125rem", fontWeight: 600, fontFamily: "var(--font-mono)", marginTop: "0.25rem" }}>{Math.round(prediction.risk_explanation.raw_aqi)}</div>
                          </div>
                          
                          <span style={{ color: "var(--muted-foreground)", fontSize: "0.875rem" }}>+</span>
                          
                          <div style={{ textAlign: "center" }}>
                            <div style={{ fontSize: "0.625rem", textTransform: "uppercase", color: "var(--muted-foreground)" }}>Cond. Shift</div>
                            <div style={{ fontSize: "1.125rem", fontWeight: 600, fontFamily: "var(--font-mono)", marginTop: "0.25rem", color: "var(--accent)" }}>+{Math.round(prediction.risk_explanation.condition_shift)}</div>
                            {prediction.risk_explanation.severity_multiplier && prediction.risk_explanation.severity_multiplier !== 1.0 && (
                              <div style={{ fontSize: "0.5rem", color: "var(--muted-foreground)", marginTop: "0.15rem" }}>×{prediction.risk_explanation.severity_multiplier}</div>
                            )}
                          </div>
                          
                          <span style={{ color: "var(--muted-foreground)", fontSize: "0.875rem" }}>+</span>
                          
                          <div style={{ textAlign: "center" }}>
                            <div style={{ fontSize: "0.625rem", textTransform: "uppercase", color: "var(--muted-foreground)" }}>Symp. Penalty</div>
                            <div style={{ fontSize: "1.125rem", fontWeight: 600, fontFamily: "var(--font-mono)", marginTop: "0.25rem", color: "var(--accent)" }}>+{Math.round(prediction.risk_explanation.symptom_penalty)}</div>
                            {/* Fix Bug 3: Show weighted breakdown per symptom */}
                            {prediction.risk_explanation.symptom_weights && Object.keys(prediction.risk_explanation.symptom_weights).length > 0 && (
                              <div style={{ fontSize: "0.5rem", color: "var(--muted-foreground)", marginTop: "0.15rem" }}>
                                {Object.entries(prediction.risk_explanation.symptom_weights).map(([s, w]) => `${s.slice(0,4)}:+${w}`).join(" ")}
                              </div>
                            )}
                          </div>
                          
                          <span style={{ color: "var(--muted-foreground)", fontSize: "0.875rem" }}>=</span>
                          
                          <div style={{ textAlign: "center" }}>
                            <div style={{ fontSize: "0.625rem", textTransform: "uppercase", color: "var(--muted-foreground)" }}>Effective AQI</div>
                            {/* FIX Bug 1: round effective_aqi to integer — must match raw_aqi + shifts arithmetically */}
                            <div style={{ fontSize: "1.125rem", fontWeight: 700, fontFamily: "var(--font-mono)", marginTop: "0.25rem" }}>{Math.round(prediction.risk_explanation.effective_aqi)}</div>
                          </div>
                          
                          <span style={{ color: "var(--muted-foreground)", fontSize: "0.875rem" }}>→</span>
                          
                          <div style={{ textAlign: "center" }}>
                            <div style={{ fontSize: "0.625rem", textTransform: "uppercase", color: "var(--muted-foreground)" }}>Risk Crossed</div>
                            <div style={{ 
                              fontSize: "0.8125rem", 
                              fontWeight: 700, 
                              textTransform: "uppercase", 
                              marginTop: "0.25rem",
                              color: getHealthRiskColor(prediction.alert_tier) 
                            }}>{prediction.alert_tier}</div>
                          </div>
                        </div>

                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "0.6875rem", color: "var(--muted-foreground)" }}>
                          <span>Engineered via: <strong style={{ textTransform: "uppercase" }}>{prediction.risk_explanation.method}</strong></span>
                          <span>Symptoms: {prediction.risk_explanation.symptom_count} · Multiplier: ×{prediction.risk_explanation.severity_multiplier ?? 1.0}</span>
                        </div>

                        {prediction.risk_explanation.why_be_careful && (
                          <div style={{ 
                            marginTop: "0.5rem",
                            padding: "0.875rem 1.125rem", 
                            borderRadius: "0.75rem", 
                            background: "rgba(var(--accent-rgb), 0.05)", 
                            borderLeft: "3px solid var(--accent)",
                            fontSize: "0.8125rem",
                            lineHeight: 1.6,
                            color: "rgba(242,240,232,0.9)"
                          }}>
                            <span style={{ fontWeight: 600, color: "var(--accent)", display: "block", marginBottom: "0.25rem", textTransform: "uppercase", fontSize: "0.625rem", letterSpacing: "0.1em" }}>Why you need to be careful:</span>
                            {prediction.risk_explanation.why_be_careful}
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* ── Hackathon Core Feature 2: Safe Outdoor Window ── */}
                  {prediction.safe_hours && prediction.safe_hours.length > 0 && (
                    <div className="glass reveal" style={{ borderRadius: "1.5rem", padding: "1.5rem", transitionDelay: "220ms" }}>
                      <div className="overline" style={{ marginBottom: "0.75rem" }}><span className="overline-dash" />Safest Outdoor Windows</div>
                      <div style={{ display: "flex", flexDirection: "column", gap: "0.875rem" }}>
                        <div style={{ fontSize: "0.75rem", color: "var(--muted-foreground)", lineHeight: 1.5 }}>
                          Historically, air pollutant levels dip during these time windows today. Plan outdoor activities, errands, or window ventilation during these periods:
                        </div>
                        <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
                          {/* FIX Bug 2: sort time slots chronologically before rendering */}
                          {[...prediction.safe_hours].sort((a, b) => a.localeCompare(b)).map((slot, idx) => (
                            <div key={idx} style={{
                              display: "inline-flex",
                              alignItems: "center",
                              gap: "0.5rem",
                              padding: "0.5rem 1rem",
                              borderRadius: "9999px",
                              border: "1px solid oklch(0.75 0.11 162 / 0.3)",
                              background: "oklch(0.75 0.11 162 / 0.06)",
                              fontSize: "0.8125rem",
                              color: "oklch(0.75 0.11 162)",
                              fontWeight: 500
                            }}>
                              <span style={{ fontSize: "0.9375rem" }}>⏰</span>
                              <span>{slot}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Metrics grid */}
                  <div className="metric-grid reveal" style={{ transitionDelay: "260ms" }}>
                    <div className="metric-item">
                      <div className="metric-lbl">Raw Model AQI</div>
                      {/* FIX Bug 1: round raw float to match rounding used everywhere else */}
                      <div className="metric-val" style={{ fontSize: "1.5rem" }}>{Math.round(prediction.predicted_aqi_raw)}</div>
                    </div>
                    <div className="metric-item">
                      <div className="metric-lbl">Safety Buffer</div>
                      {/* FIX Bug 1: round buffer value consistently */}
                      <div className="metric-val" style={{ fontSize: "1.5rem" }}>+{Math.round(prediction.rmse_buffer)}</div>
                      <div className="metric-sub">RMSE adjusted</div>
                    </div>
                    <div className="metric-item">
                      <div className="metric-lbl">AI Confidence</div>
                      <div className="metric-val" style={{ fontSize: "1.5rem", color: "var(--accent)" }}>{getConfidenceLabel(prediction.prediction_confidence)}</div>
                    </div>
                    <div className="metric-item">
                      <div className="metric-lbl">Forecast For</div>
                      <div style={{ fontFamily: "var(--font-mono)", fontSize: "0.75rem", marginTop: "0.5rem", color: "var(--muted-foreground)", lineHeight: 1.4 }}>
                        {new Date(prediction.forecast_for).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })}
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* ── Comfort Rings ── */}
              <div className="glass reveal" style={{ borderRadius: "1.5rem", padding: "2rem", marginBottom: "1.5rem", transitionDelay: "120ms" }}>
                <div style={{ marginBottom: "1.5rem" }}>
                  <div className="overline" style={{ marginBottom: "0.5rem" }}><span className="overline-dash" />Exposure Profile</div>
                  <h2 className="font-display" style={{ fontSize: "1.5rem", fontWeight: 300 }}>Your atmosphere, <em style={{ color: "rgba(242,240,232,0.55)" }}>at a glance.</em></h2>
                </div>
                <div className="comfort-rings-row" style={{ flexWrap: "wrap", gap: "1.5rem" }}>
                  <ComfortRing value={Math.round(pct)} label="AQI Level" sublabel="%" hue={tierHue} />
                  <ComfortRing value={Math.round(pm25Score)} label="Air Safety" sublabel="Score" hue="162" />
                  <ComfortRing value={Math.round(confScore)} label="Model Conf." sublabel="%" hue="210" />
                  <ComfortRing value={Math.round(safetyScore)} label="Safe Index" sublabel="%" hue="78" />
                  <ComfortRing value={Math.round(Math.max(0, 100 - getAqiPercent(prediction.rmse_buffer * 5)))} label="Stability" sublabel="%" hue="55" />
                </div>
              </div>

              {/* ── Precautions — Categorised and Personalised ── */}
              <div className="glass reveal" style={{ borderRadius: "1.5rem", padding: "2rem", marginBottom: "1.5rem", transitionDelay: "160ms" }}>
                <div style={{ marginBottom: "1.5rem" }}>
                  <div className="overline" style={{ marginBottom: "0.5rem" }}><span className="overline-dash" />Personalised Guidance</div>
                  <h2 className="font-display" style={{ fontSize: "1.5rem", fontWeight: 300 }}>Your precautions, <em style={{ color: "rgba(242,240,232,0.55)" }}>today.</em></h2>
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: "1.5rem" }}>
                  
                  {/* Category 1: General Guidance */}
                  {prediction.precautions.some(p => p.category === "general") && (
                    <div>
                      <div style={{ fontSize: "0.8125rem", fontWeight: 600, color: "var(--foreground)", display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.75rem" }}>
                        <span style={{ fontSize: "1rem" }}>🛡️</span> General Guidance
                      </div>
                      <div className="precaution-list" style={{ paddingLeft: "1.5rem" }}>
                        {prediction.precautions.filter(p => p.category === "general").map((p, i) => (
                          <div key={i} className="precaution-item" style={{ marginBottom: "0.5rem" }}>
                            <span className="precaution-dot">—</span>
                            <span>{p.text}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Category 2: Condition Specific */}
                  {prediction.precautions.some(p => p.category === "condition") && (
                    <div style={{ borderTop: "1px solid var(--border)", paddingTop: "1.25rem" }}>
                      <div style={{ fontSize: "0.8125rem", fontWeight: 600, color: "var(--accent)", display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.75rem" }}>
                        <span style={{ fontSize: "1rem" }}>💊</span> Respiratory Profile Suggestions
                      </div>
                      <div className="precaution-list" style={{ paddingLeft: "1.5rem" }}>
                        {prediction.precautions.filter(p => p.category === "condition").map((p, i) => (
                          <div key={i} className="precaution-item" style={{ marginBottom: "0.5rem" }}>
                            <span className="precaution-dot" style={{ color: "var(--accent)" }}>—</span>
                            <span>{p.text}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Category 3: Symptoms Specific */}
                  {prediction.precautions.some(p => p.category === "symptom") && (
                    <div style={{ borderTop: "1px solid var(--border)", paddingTop: "1.25rem" }}>
                      <div style={{ fontSize: "0.8125rem", fontWeight: 600, color: "oklch(0.78 0.14 36)", display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.75rem" }}>
                        <span style={{ fontSize: "1rem" }}>🫁</span> Active Symptoms Relief
                      </div>
                      <div className="precaution-list" style={{ paddingLeft: "1.5rem" }}>
                        {prediction.precautions.filter(p => p.category === "symptom").map((p, i) => (
                          <div key={i} className="precaution-item" style={{ marginBottom: "0.5rem" }}>
                            <span className="precaution-dot" style={{ color: "oklch(0.78 0.14 36)" }}>—</span>
                            <span>{p.text}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Category 4: Triggers Specific */}
                  {prediction.precautions.some(p => p.category === "trigger") && (
                    <div style={{ borderTop: "1px solid var(--border)", paddingTop: "1.25rem" }}>
                      <div style={{ fontSize: "0.8125rem", fontWeight: 600, color: "oklch(0.82 0.11 95)", display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.75rem" }}>
                        <span style={{ fontSize: "1rem" }}>⚡</span> Environmental Trigger Safeguards
                      </div>
                      <div className="precaution-list" style={{ paddingLeft: "1.5rem" }}>
                        {prediction.precautions.filter(p => p.category === "trigger").map((p, i) => (
                          <div key={i} className="precaution-item" style={{ marginBottom: "0.5rem" }}>
                            <span className="precaution-dot" style={{ color: "oklch(0.82 0.11 95)" }}>—</span>
                            <span>{p.text}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                </div>
              </div>

              {/* ── Profile Card ── */}
              {profile && (
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.5rem", marginBottom: "1.5rem" }}>
                  <div className="glass reveal" style={{ borderRadius: "1.5rem", padding: "2rem", transitionDelay: "200ms" }}>
                    <div className="overline" style={{ marginBottom: "1.25rem" }}><span className="overline-dash" />Health Profile</div>
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))", gap: "1rem" }}>
                      {[
                        { label: "Name", value: profile.name },
                        { label: "Condition", value: profile.condition },
                        { label: "Severity", value: profile.severity },
                        { label: "Symptoms", value: (profile.symptoms?.join(", ") || "—") },
                        { label: "Triggers", value: (profile.personalized_issue || "—") },
                        { label: "Location", value: profile.last_known_lat ? `${profile.last_known_lat?.toFixed(3)}, ${profile.last_known_lon?.toFixed(3)}` : "Not set" },
                      ].map((item) => (
                        <div key={item.label}>
                          <div className="metric-lbl">{item.label}</div>
                          <div style={{ fontSize: "0.875rem", marginTop: "0.375rem", color: "var(--foreground)", lineHeight: 1.5 }}>{item.value}</div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* ── NEW FEATURE: Smart Indoor Air Quality Recommendations ── */}
                  <SmartIndoorRecommendations 
                    userId={userId!} 
                    currentAqi={currentAqi}
                    alertTier={prediction.alert_tier}
                    effectiveAqi={prediction.risk_explanation?.effective_aqi}
                  />

                  {/* ── Alert Notification Dispatch History Log ── */}
                  <div className="glass reveal" style={{ borderRadius: "1.5rem", padding: "2rem", transitionDelay: "240ms", display: "flex", flexDirection: "column" }}>
                    <div className="overline" style={{ marginBottom: "1.25rem" }}><span className="overline-dash" />Notification Dispatch Logs</div>
                    
                    <div style={{ flex: 1, overflowY: "auto", maxHeight: "240px", display: "flex", flexDirection: "column", gap: "0.875rem" }}>
                      {alerts.length === 0 ? (
                        <div style={{ margin: "auto", textAlign: "center", color: "var(--muted-foreground)", fontSize: "0.8125rem", padding: "1.5rem 0" }}>
                          <span style={{ fontSize: "1.5rem", display: "block", marginBottom: "0.5rem" }}>📡</span>
                          No alerts dispatched yet.<br/>Standard real-time monitoring active.
                        </div>
                      ) : (
                        alerts.map((alert, index) => {
                          const dateStr = new Date(alert.sent_at).toLocaleString("en-IN", { dateStyle: "short", timeStyle: "short" });
                          const channelLabel = alert.channel === "sms" ? "📱 SMS Alert" : "✉️ Email Alert";
                          
                          return (
                            <div key={index} style={{
                              padding: "0.75rem",
                              borderRadius: "0.75rem",
                              border: "1px solid var(--border)",
                              background: "rgba(255,255,255,0.01)",
                              display: "flex",
                              flexDirection: "column",
                              gap: "0.375rem"
                            }}>
                              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "0.75rem" }}>
                                <span style={{ fontWeight: 600, color: "var(--foreground)" }}>{channelLabel}</span>
                                <span style={{ color: "var(--muted-foreground)", fontFamily: "var(--font-mono)", fontSize: "0.6875rem" }}>{dateStr}</span>
                              </div>
                              
                              <p style={{ fontSize: "0.8125rem", color: "rgba(242,240,232,0.8)", margin: 0, lineHeight: 1.4 }}>
                                {alert.alert_message}
                              </p>
                              
                              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "0.6875rem", marginTop: "0.125rem" }}>
                                <span style={{
                                  color: getHealthRiskColor(alert.alert_tier),
                                  fontWeight: 600,
                                  textTransform: "uppercase"
                                }}>{alert.alert_tier}</span>
                                
                                <span style={{
                                  color: alert.status === "sent" ? "oklch(0.75 0.11 162)" : alert.status === "failed" ? "oklch(0.72 0.14 32)" : "var(--muted-foreground)",
                                  fontWeight: 500,
                                  fontSize: "0.625rem",
                                  textTransform: "uppercase"
                                }}>{alert.status}</span>
                              </div>
                            </div>
                          );
                        })
                      )}
                    </div>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </main>

      {/* ── User Info Dock ── */}
      <nav className={`command-dock${dockHidden ? " hidden" : ""}`}>
        <div className="glass dock-inner" style={{ justifyContent: "space-between", padding: "0.75rem 1.5rem" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
            <div style={{ 
              width: 40, 
              height: 40, 
              borderRadius: "50%", 
              background: "var(--gradient-orb)", 
              display: "flex", 
              alignItems: "center", 
              justifyContent: "center",
              fontSize: "1rem",
              fontWeight: 600,
              boxShadow: "0 0 20px rgba(var(--accent-rgb), 0.3)"
            }}>
              {profile?.name?.charAt(0).toUpperCase() || "?"}
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
              <span style={{ fontSize: "0.9375rem", fontWeight: 500 }}>{profile?.name || "User"}</span>
              <span style={{ fontSize: "0.75rem", color: "var(--muted-foreground)" }}>
                {profile?.condition?.toUpperCase()} · {profile?.severity} · {profile?.email || profile?.phone || "No contact"}
              </span>
            </div>
          </div>
          <button 
            onClick={handleLogout} 
            className="btn-secondary"
            style={{ 
              fontSize: "0.8125rem",
              padding: "0.5rem 1.25rem"
            }}
          >
            Sign Out →
          </button>
        </div>
      </nav>
    </>
  );
}
