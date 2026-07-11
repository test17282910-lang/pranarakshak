"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";

// ── Password helpers ──────────────────────────────────────────────────────────
function EyeIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" /><circle cx="12" cy="12" r="3" />
    </svg>
  );
}
function EyeOffIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
      <line x1="1" y1="1" x2="23" y2="23" />
    </svg>
  );
}
function getPasswordStrength(pw: string): { score: number; label: string; color: string } {
  let s = 0;
  if (pw.length >= 8)           s++;
  if (pw.length >= 12)          s++;
  if (/[A-Z]/.test(pw))         s++;
  if (/[0-9]/.test(pw))         s++;
  if (/[^A-Za-z0-9]/.test(pw))  s++;
  const levels = [
    { score: 0, label: "",           color: "transparent" },
    { score: 1, label: "Weak",       color: "oklch(0.62 0.18 28)" },
    { score: 2, label: "Fair",       color: "oklch(0.72 0.14 45)" },
    { score: 3, label: "Good",       color: "oklch(0.82 0.11 78)" },
    { score: 4, label: "Strong",     color: "oklch(0.75 0.11 162)" },
    { score: 5, label: "Very Strong",color: "oklch(0.78 0.09 210)" },
  ];
  return levels[Math.min(s, 5)];
}

export default function Home() {
  const [formData, setFormData] = useState({
    name: "", email: "", phone: "", password: "",
    condition: "", severity: "moderate",
    lat: null as number | null, lon: null as number | null,
    personalized_issue: "",
    alert_threshold: 100,
  });
  const [showPassword, setShowPassword]   = useState(false);
  const [selectedSymptoms, setSelectedSymptoms] = useState<string[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [geocoding, setGeocoding] = useState(false);
  const [feedback, setFeedback] = useState<{ message: string; isError: boolean } | null>(null);
  const [locationStatus, setLocationStatus] = useState<{ message: string; type: "success" | "error" | "loading" | null }>({ message: "", type: null });
  const [showModal, setShowModal] = useState(false);
  const [registeredUserId, setRegisteredUserId] = useState("");
  const [activeUserId, setActiveUserId] = useState<string | null>(null);
  const [dockHidden, setDockHidden] = useState(false);
  const lastScroll = useRef(0);

  const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  useEffect(() => {
    setActiveUserId(localStorage.getItem("aqi_user_id"));
  }, []);

  const symptomsList = [
    { id: "Wheezing",           label: "Wheezing" },
    { id: "Coughing",           label: "Frequent Coughing" },
    { id: "ChestTightness",     label: "Chest Tightness" },
    { id: "ShortnessOfBreath",  label: "Shortness of Breath" },
    { id: "NighttimeSymptoms",  label: "Nighttime Symptoms" },
    { id: "ExerciseInduced",    label: "Exercise-Induced" },
  ];

  // Scroll-reveal
  useEffect(() => {
    const els = document.querySelectorAll(".reveal");
    const observer = new IntersectionObserver(
      (entries) => entries.forEach((e) => { if (e.isIntersecting) e.target.classList.add("visible"); }),
      { threshold: 0.08 }
    );
    els.forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, []);

  // Dock hide on scroll down
  useEffect(() => {
    const onScroll = () => {
      const y = window.scrollY;
      setDockHidden(y > lastScroll.current && y > 100);
      lastScroll.current = y;
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const toggleSymptom = (id: string) =>
    setSelectedSymptoms((prev) => prev.includes(id) ? prev.filter((s) => s !== id) : [...prev, id]);

  const getLocation = () => {
    if (!navigator.geolocation) { setLocationStatus({ message: "Geolocation not supported.", type: "error" }); return; }
    setLocationStatus({ message: "Locating…", type: "loading" });
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const { latitude: lat, longitude: lon } = pos.coords;
        setFormData((prev) => ({ ...prev, lat, lon }));
        setLocationStatus({ message: `✓ Secured — ${lat.toFixed(4)}, ${lon.toFixed(4)}`, type: "success" });
      },
      () => setLocationStatus({ message: "GPS unavailable. Try searching your city below.", type: "error" }),
      { enableHighAccuracy: true, timeout: 5000, maximumAge: 0 }
    );
  };

  const handleGeocodeSearch = async (e: React.MouseEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    setGeocoding(true);
    setLocationStatus({ message: "Searching…", type: "loading" });
    try {
      const res = await fetch(`https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(searchQuery)}&format=json&limit=1`);
      const data = await res.json();
      if (data?.length > 0) {
        const lat = parseFloat(data[0].lat), lon = parseFloat(data[0].lon);
        setFormData((prev) => ({ ...prev, lat, lon }));
        setLocationStatus({ message: `✓ ${data[0].display_name.split(",")[0]} (${lat.toFixed(2)}, ${lon.toFixed(2)})`, type: "success" });
      } else {
        setLocationStatus({ message: "Location not found. Check spelling.", type: "error" });
      }
    } catch {
      setLocationStatus({ message: "Search failed. Try sharing GPS instead.", type: "error" });
    } finally { setGeocoding(false); }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFeedback(null); setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: formData.name, email: formData.email || null, phone: formData.phone || null,
          password: formData.password,
          condition: formData.condition, severity: formData.severity,
          lat: formData.lat, lon: formData.lon,
          symptoms: selectedSymptoms,
          personalized_issue: formData.personalized_issue || null,
          alert_threshold: formData.alert_threshold || 100,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Registration failed");
      // Persist immediately so the dashboard auto-loads
      localStorage.setItem("aqi_user_id", data.user_id);
      setRegisteredUserId(data.user_id);
      setShowModal(true);
      setFormData({ name: "", email: "", phone: "", password: "", condition: "", severity: "moderate", lat: null, lon: null, personalized_issue: "", alert_threshold: 100 });
      setSelectedSymptoms([]); setSearchQuery(""); setLocationStatus({ message: "", type: null });
    } catch (err: any) {
      setFeedback({ message: err.message, isError: true });
    } finally { setLoading(false); }
  };

  return (
    <>
      {/* ── Top Bar ── */}
      <header className="topbar">
        <div className="topbar-inner">
          <div className="logo">
            <div className="logo-orb"><div className="logo-orb-inner" /></div>
            <span className="logo-name">Pranarakshak</span>
          </div>
          <div className="topbar-status">
            <span className="live-dot animate-pulse" />
            Live · India · CPCB
          </div>
          <nav className="nav-links">
            <Link href="/login" className="nav-link">Login</Link>
          </nav>
        </div>
      </header>

      <main className="page-wrap">
        {/* ── Hero Section ── */}
        <section className="section" style={{ minHeight: "100svh", display: "grid", gridTemplateColumns: "1fr 1fr", gap: "4rem", alignItems: "start", paddingTop: "8rem", paddingBottom: "4rem" }}>
          <div className="section-inner" style={{ width: "100%", maxWidth: "1200px", margin: "0 auto", display: "contents" }}>
            <div>
              {/* Left: Copy */}
                <div className="overline reveal" style={{ transitionDelay: "0ms" }}>
                  <span className="overline-dash" />
                  Personalised Health Intelligence
                </div>

                <h1
                  className="font-display reveal"
                  style={{
                    fontSize: "clamp(3rem, 6vw, 6rem)",
                    fontWeight: 300,
                    lineHeight: 1,
                    letterSpacing: "-0.03em",
                    marginTop: "1.5rem",
                    transitionDelay: "120ms",
                  }}
                >
                  Breathe<br />
                  <em style={{ color: "rgba(242,240,232,0.6)", fontStyle: "italic" }}>safely.</em>
                </h1>

                <p className="reveal" style={{
                  marginTop: "1.5rem", fontSize: "1.0625rem", lineHeight: 1.6,
                  color: "var(--muted-foreground)", maxWidth: "44ch", transitionDelay: "240ms",
                }}>
                  AI-powered 24-hour AQI forecasts from real CPCB India monitoring stations —
                  personalised to your respiratory condition and triggers.
                </p>

                <div className="reveal" style={{ marginTop: "2rem", display: "flex", flexWrap: "wrap", gap: "1.5rem", transitionDelay: "360ms" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.625rem" }}>
                    <div style={{ display: "flex", height: "20px", alignItems: "flex-end", gap: "2px" }}>
                      {[0.9, 0.7, 0.5, 0.35, 0.2].map((h, i) => (
                        <span key={i} style={{ display: "block", width: "3px", height: `${h * 100}%`, background: "var(--accent)", borderRadius: "2px", opacity: i < 4 ? 1 : 0.3 }} />
                      ))}
                    </div>
                    <span style={{ fontSize: "0.6875rem", textTransform: "uppercase", letterSpacing: "0.25em", color: "var(--muted-foreground)" }}>
                      Model Confidence · 94%
                    </span>
                  </div>
                </div>

                <div className="reveal" style={{ marginTop: "2rem", paddingTop: "1.5rem", borderTop: "1px solid var(--border)", display: "grid", gridTemplateColumns: "repeat(3, auto)", gap: "2rem", transitionDelay: "480ms" }}>
                  {[
                    { label: "Sources", value: "WAQI", sub: "CPCB India" },
                    { label: "Forecast", value: "24h", sub: "Ahead" },
                    { label: "Model", value: "LSTM", sub: "AI-Powered" },
                  ].map((s) => (
                    <div key={s.label}>
                      <div style={{ fontSize: "0.625rem", textTransform: "uppercase", letterSpacing: "0.25em", color: "var(--muted-foreground)" }}>{s.label}</div>
                      <div style={{ fontFamily: "var(--font-display)", fontSize: "1.5rem", fontWeight: 200, marginTop: "0.25rem" }}>{s.value}</div>
                      <div style={{ fontSize: "0.6875rem", color: "var(--muted-foreground)" }}>{s.sub}</div>
                    </div>
                  ))}
                </div>

                {/* Enhanced Earth Monitoring Visualization - Larger & More Detailed */}
                <div className="reveal" style={{ marginTop: "calc(5rem + 150px)", position: "relative", height: "560px", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", transitionDelay: "600ms" }}>
                  {/* Earth globe container - Even larger */}
                  <div style={{ position: "relative", width: "520px", height: "520px", transform: "translateY(-80px)" }}>
                    
                    {/* Outer monitoring rings - More layers for depth */}
                    {[
                      { size: 520, duration: "80s", delay: "0s", opacity: 0.06, strokeWidth: "0.4" },
                      { size: 480, duration: "65s", delay: "-20s", opacity: 0.08, strokeWidth: "0.5" },
                      { size: 440, duration: "50s", delay: "-15s", opacity: 0.10, strokeWidth: "0.6", reverse: true },
                      { size: 400, duration: "40s", delay: "-10s", opacity: 0.12, strokeWidth: "0.7" },
                      { size: 360, duration: "30s", delay: "-25s", opacity: 0.15, strokeWidth: "0.8", reverse: true },
                      { size: 320, duration: "25s", delay: "-5s", opacity: 0.18, strokeWidth: "0.9" },
                    ].map((ring, i) => (
                      <svg
                        key={i}
                        viewBox="0 0 100 100"
                        style={{
                          position: "absolute",
                          top: "50%",
                          left: "50%",
                          transform: "translate(-50%, -50%)",
                          width: ring.size,
                          height: ring.size,
                          opacity: ring.opacity,
                          animation: `ring-rotate ${ring.duration} linear ${ring.reverse ? 'reverse' : 'normal'} infinite`,
                          animationDelay: ring.delay,
                        }}
                      >
                        <circle
                          cx="50"
                          cy="50"
                          r="48"
                          fill="none"
                          stroke="var(--accent)"
                          strokeWidth={ring.strokeWidth}
                          strokeDasharray={i === 0 ? "4 20" : i === 1 ? "3 16" : i === 2 ? "2 12" : i === 3 ? "2 10" : i === 4 ? "1 8" : "1 6"}
                        />
                        
                        {/* More monitoring station markers */}
                        {[0, 30, 60, 90, 120, 150, 180, 210, 240, 270, 300, 330].map((angle) => (
                          <g key={`marker-${i}-${angle}`}>
                            <circle
                              cx={50 + 47 * Math.cos((angle * Math.PI) / 180)}
                              cy={50 + 47 * Math.sin((angle * Math.PI) / 180)}
                              r={i < 3 ? "1" : "0.6"}
                              fill="var(--accent)"
                              opacity={i < 3 ? "0.8" : "0.5"}
                            />
                          </g>
                        ))}
                      </svg>
                    ))}

                    {/* Central Earth - Much larger and more detailed */}
                    <div
                      style={{
                        position: "absolute",
                        top: "50%",
                        left: "50%",
                        transform: "translate(-50%, -50%)",
                        width: "280px",
                        height: "280px",
                        borderRadius: "50%",
                        background: `
                          radial-gradient(circle at 35% 25%, 
                            oklch(0.55 0.08 220 / 0.95) 0%,
                            oklch(0.45 0.10 200 / 0.9) 15%,
                            oklch(0.35 0.12 180 / 0.85) 35%,
                            oklch(0.25 0.15 160 / 0.8) 55%,
                            oklch(0.15 0.18 140 / 0.7) 75%,
                            oklch(0.08 0.20 120 / 0.6) 90%,
                            oklch(0.03 0.25 100 / 0.5) 100%
                          )
                        `,
                        boxShadow: `
                          0 0 120px oklch(0.45 0.12 180 / 0.4),
                          0 0 80px oklch(0.55 0.10 200 / 0.3),
                          inset -18px -24px 48px rgba(0,0,0,0.5),
                          inset 18px 24px 48px rgba(255,255,255,0.15)
                        `,
                        animation: "earth-rotate 150s linear infinite",
                        overflow: "hidden",
                      }}
                    >
                      {/* More detailed continental patterns */}
                      <div style={{
                        position: "absolute",
                        inset: "8%",
                        borderRadius: "50%",
                        background: `
                          radial-gradient(ellipse 45% 25% at 30% 25%, oklch(0.42 0.08 140 / 0.8) 0%, oklch(0.38 0.06 130 / 0.4) 40%, transparent 65%),
                          radial-gradient(ellipse 35% 30% at 75% 35%, oklch(0.40 0.07 125 / 0.7) 0%, oklch(0.35 0.05 115 / 0.3) 45%, transparent 70%),
                          radial-gradient(ellipse 30% 20% at 50% 65%, oklch(0.45 0.06 110 / 0.6) 0%, oklch(0.40 0.04 100 / 0.2) 50%, transparent 75%),
                          radial-gradient(ellipse 20% 35% at 15% 50%, oklch(0.43 0.07 105 / 0.5) 0%, transparent 60%),
                          radial-gradient(ellipse 25% 15% at 85% 70%, oklch(0.41 0.05 95 / 0.4) 0%, transparent 65%)
                        `,
                        animation: "earth-rotate 150s linear infinite",
                      }} />

                      {/* Cloud layers for more realism */}
                      <div style={{
                        position: "absolute",
                        inset: "5%",
                        borderRadius: "50%",
                        background: `
                          radial-gradient(ellipse 60% 30% at 40% 20%, oklch(0.85 0.02 200 / 0.15) 0%, transparent 50%),
                          radial-gradient(ellipse 40% 20% at 70% 60%, oklch(0.88 0.01 180 / 0.12) 0%, transparent 60%),
                          radial-gradient(ellipse 30% 40% at 20% 70%, oklch(0.90 0.01 160 / 0.10) 0%, transparent 55%)
                        `,
                        animation: "cloud-drift 200s linear infinite",
                      }} />
                      
                      {/* Enhanced atmospheric glow */}
                      <div style={{
                        position: "absolute",
                        inset: "-12px",
                        borderRadius: "50%",
                        background: "radial-gradient(circle, transparent 68%, oklch(0.65 0.15 180 / 0.4) 78%, oklch(0.75 0.18 160 / 0.2) 88%, oklch(0.85 0.20 140 / 0.05) 100%)",
                        animation: "atmosphere-pulse 12s ease-in-out infinite",
                      }} />

                      {/* Ozone layer effect */}
                      <div style={{
                        position: "absolute",
                        inset: "-16px",
                        borderRadius: "50%",
                        background: "radial-gradient(circle, transparent 72%, oklch(0.70 0.20 200 / 0.1) 85%, oklch(0.80 0.15 180 / 0.05) 95%, transparent 100%)",
                        animation: "ozone-shimmer 25s ease-in-out infinite",
                      }} />
                    </div>

                    {/* India highlight marker - more prominent */}
                    <div
                      style={{
                        position: "absolute",
                        top: "50%",
                        left: "50%",
                        transform: "translate(-50%, -50%) translateX(36px) translateY(-20px)",
                        width: "12px",
                        height: "12px",
                        borderRadius: "50%",
                        background: "radial-gradient(circle, var(--accent) 0%, oklch(0.85 0.15 162) 50%, var(--accent) 100%)",
                        boxShadow: "0 0 20px var(--accent), 0 0 40px oklch(0.75 0.11 162 / 0.5)",
                        animation: "india-pulse 3s ease-in-out infinite",
                      }}
                    >
                      {/* India marker ring */}
                      <div style={{
                        position: "absolute",
                        inset: "-8px",
                        borderRadius: "50%",
                        border: "1px solid var(--accent)",
                        opacity: 0.3,
                        animation: "marker-ring-expand 3s ease-in-out infinite",
                      }} />
                    </div>

                    {/* Enhanced air quality data streams */}
                    {[...Array(18)].map((_, i) => (
                      <div
                        key={`stream-${i}`}
                        style={{
                          position: "absolute",
                          top: "50%",
                          left: "50%",
                          width: "3px",
                          height: "3px",
                          borderRadius: "50%",
                          background: `oklch(0.75 0.12 ${162 + (i * 12) % 120})`,
                          boxShadow: `0 0 8px oklch(0.75 0.12 ${162 + (i * 12) % 120})`,
                          opacity: 0.7,
                          animation: `data-stream-${i % 3} ${18 + i * 1.2}s linear infinite`,
                          animationDelay: `${-i * 1}s`,
                        }}
                      />
                    ))}

                    {/* Enhanced satellite monitoring indicators */}
                    {[30, 90, 150, 210, 270, 330].map((angle, i) => (
                      <div
                        key={`satellite-${i}`}
                        style={{
                          position: "absolute",
                          top: "50%",
                          left: "50%",
                          transform: `translate(-50%, -50%) rotate(${angle}deg) translateY(-220px)`,
                          width: "8px",
                          height: "8px",
                          background: "radial-gradient(circle, oklch(0.90 0.15 60) 0%, oklch(0.75 0.12 45) 100%)",
                          borderRadius: "3px",
                          boxShadow: "0 0 12px oklch(0.85 0.15 60), 0 0 24px oklch(0.75 0.12 60 / 0.3)",
                          animation: `satellite-orbit ${45 + i * 6}s linear infinite`,
                        }}
                      >
                        {/* Satellite signal beam */}
                        <div style={{
                          position: "absolute",
                          top: "50%",
                          left: "50%",
                          transform: "translate(-50%, -50%) rotate(180deg)",
                          width: "2px",
                          height: "40px",
                          background: "linear-gradient(to bottom, oklch(0.85 0.15 60 / 0.6) 0%, transparent 100%)",
                          opacity: 0.4,
                        }} />
                      </div>
                    ))}
                  </div>

                  {/* Comprehensive status display */}
                  <div style={{
                    marginTop: "2rem",
                    display: "grid",
                    gridTemplateColumns: "repeat(2, 1fr)",
                    gap: "1rem",
                    width: "100%",
                    maxWidth: "520px",
                  }}>
                    <div style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "0.5rem",
                      padding: "0.75rem 1rem",
                      borderRadius: "0.75rem",
                      border: "1px solid var(--border)",
                      background: "rgba(255,255,255,0.02)",
                    }}>
                      <div style={{
                        width: "8px",
                        height: "8px",
                        borderRadius: "50%",
                        background: "var(--accent)",
                        animation: "pulse 2s ease-in-out infinite"
                      }} />
                      <div>
                        <div style={{ fontSize: "0.625rem", textTransform: "uppercase", letterSpacing: "0.2em", color: "var(--muted-foreground)" }}>CPCB Network</div>
                        <div style={{ fontSize: "0.75rem", color: "var(--foreground)", marginTop: "0.125rem" }}>800+ Stations</div>
                      </div>
                    </div>

                    <div style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "0.5rem",
                      padding: "0.75rem 1rem",
                      borderRadius: "0.75rem",
                      border: "1px solid var(--border)",
                      background: "rgba(255,255,255,0.02)",
                    }}>
                      <div style={{
                        width: "8px",
                        height: "8px",
                        borderRadius: "50%",
                        background: "oklch(0.85 0.15 60)",
                        animation: "pulse 2s ease-in-out infinite",
                        animationDelay: "0.5s"
                      }} />
                      <div>
                        <div style={{ fontSize: "0.625rem", textTransform: "uppercase", letterSpacing: "0.2em", color: "var(--muted-foreground)" }}>AI Processing</div>
                        <div style={{ fontSize: "0.75rem", color: "var(--foreground)", marginTop: "0.125rem" }}>LSTM Neural Net</div>
                      </div>
                    </div>

                    <div style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "0.5rem",
                      padding: "0.75rem 1rem",
                      borderRadius: "0.75rem",
                      border: "1px solid var(--border)",
                      background: "rgba(255,255,255,0.02)",
                    }}>
                      <div style={{
                        width: "8px",
                        height: "8px",
                        borderRadius: "50%",
                        background: "oklch(0.75 0.12 120)",
                        animation: "pulse 2s ease-in-out infinite",
                        animationDelay: "1s"
                      }} />
                      <div>
                        <div style={{ fontSize: "0.625rem", textTransform: "uppercase", letterSpacing: "0.2em", color: "var(--muted-foreground)" }}>Update Frequency</div>
                        <div style={{ fontSize: "0.75rem", color: "var(--foreground)", marginTop: "0.125rem" }}>Real-time</div>
                      </div>
                    </div>

                    <div style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "0.5rem",
                      padding: "0.75rem 1rem",
                      borderRadius: "0.75rem",
                      border: "1px solid var(--border)",
                      background: "rgba(255,255,255,0.02)",
                    }}>
                      <div style={{
                        width: "8px",
                        height: "8px",
                        borderRadius: "50%",
                        background: "oklch(0.78 0.10 200)",
                        animation: "pulse 2s ease-in-out infinite",
                        animationDelay: "1.5s"
                      }} />
                      <div>
                        <div style={{ fontSize: "0.625rem", textTransform: "uppercase", letterSpacing: "0.2em", color: "var(--muted-foreground)" }}>Coverage</div>
                        <div style={{ fontSize: "0.75rem", color: "var(--foreground)", marginTop: "0.125rem" }}>Pan-India</div>
                      </div>
                    </div>
                  </div>

                  {/* Project details section */}
                  <div style={{
                    marginTop: "3rem",
                    textAlign: "center",
                    maxWidth: "560px",
                  }}>
                    <h3 className="font-display" style={{
                      fontSize: "1.5rem",
                      fontWeight: 300,
                      marginBottom: "1.25rem",
                      color: "rgba(242,240,232,0.9)"
                    }}>
                      Environmental Intelligence System
                    </h3>
                    <p style={{
                      fontSize: "1rem",
                      lineHeight: 1.6,
                      color: "var(--muted-foreground)",
                      marginBottom: "1.75rem"
                    }}>
                      Pranarakshak combines real-time CPCB monitoring data with advanced LSTM neural networks 
                      to predict air quality 24 hours ahead. Our system processes 17 environmental features 
                      including PM2.5, PM10, NO₂, O₃, CO, temperature, humidity, and wind patterns to deliver 
                      personalized health alerts based on your specific respiratory condition.
                    </p>
                    <div style={{
                      display: "flex",
                      justifyContent: "center",
                      gap: "2.5rem",
                      fontSize: "0.875rem",
                      color: "var(--muted-foreground)"
                    }}>
                      <div>
                        <div style={{ color: "var(--accent)", fontWeight: 600, fontSize: "1.125rem" }}>94.2%</div>
                        <div>Model Accuracy</div>
                      </div>
                      <div>
                        <div style={{ color: "var(--accent)", fontWeight: 600, fontSize: "1.125rem" }}>17</div>
                        <div>Input Features</div>
                      </div>
                      <div>
                        <div style={{ color: "var(--accent)", fontWeight: 600, fontSize: "1.125rem" }}>24h</div>
                        <div>Forecast Range</div>
                      </div>
                      <div>
                        <div style={{ color: "var(--accent)", fontWeight: 600, fontSize: "1.125rem" }}>4</div>
                        <div>Health Conditions</div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Right: Registration Form */}
              <div className="glass form-card reveal" style={{ transitionDelay: "180ms" }}>
                <div style={{ marginBottom: "2rem" }}>
                  <div className="overline" style={{ marginBottom: "0.75rem" }}>
                    <span className="live-dot animate-pulse" />
                    Create Profile
                  </div>
                  <h2 className="font-display" style={{ fontSize: "1.75rem", fontWeight: 300 }}>Your health profile</h2>
                  <p style={{ color: "var(--muted-foreground)", fontSize: "0.875rem", marginTop: "0.375rem" }}>Takes under 2 minutes.</p>
                </div>

                <form onSubmit={handleSubmit}>
                  {/* Basic Info */}
                  <div className="form-section-title">Personal Information</div>
                  <div className="form-group">
                    <label htmlFor="name">Full Name</label>
                    <input type="text" id="name" name="name" required placeholder="Yash Reddy" value={formData.name} onChange={handleInputChange} />
                  </div>
                  <div className="form-row">
                    <div className="form-group">
                      <label htmlFor="email">Email</label>
                      <input type="email" id="email" name="email" placeholder="you@email.com" value={formData.email} onChange={handleInputChange} />
                    </div>
                    <div className="form-group">
                      <label htmlFor="phone">Phone</label>
                      <input type="tel" id="phone" name="phone" placeholder="+91 99999 99999" value={formData.phone} onChange={handleInputChange} />
                    </div>
                  </div>

                  <div className="form-group" style={{ marginTop: "1rem" }}>
                    <label htmlFor="password">Password</label>
                    <div className="password-field-wrap">
                      <input
                        type={showPassword ? "text" : "password"}
                        id="password" name="password" required
                        placeholder="Create a secure password (min. 8 chars)"
                        value={formData.password}
                        onChange={handleInputChange}
                        autoComplete="new-password"
                      />
                      <button
                        type="button"
                        className="password-toggle-btn"
                        onClick={() => setShowPassword((v) => !v)}
                        aria-label={showPassword ? "Hide password" : "Show password"}
                      >
                        {showPassword ? <EyeOffIcon /> : <EyeIcon />}
                      </button>
                    </div>
                    {/* Strength bar — only shown while typing */}
                    {formData.password.length > 0 && (() => {
                      const s = getPasswordStrength(formData.password);
                      return (
                        <>
                          <div className="password-strength-bar" aria-hidden="true">
                            <div className="password-strength-fill" style={{ width: `${(s.score / 5) * 100}%`, backgroundColor: s.color }} />
                          </div>
                          <p className="password-strength-label" style={{ color: s.color }} aria-live="polite">{s.label}</p>
                        </>
                      );
                    })()}
                  </div>

                  {/* Health Info */}
                  <div className="form-section-title" style={{ marginTop: "1.5rem" }}>Health Profile</div>
                  <div className="form-row">
                    <div className="form-group">
                      <label htmlFor="condition">Condition</label>
                      <select id="condition" name="condition" required value={formData.condition} onChange={handleInputChange}>
                        <option value="" disabled>Select…</option>
                        <option value="asthma">Asthma</option>
                        <option value="copd">COPD</option>
                        <option value="both">Both</option>
                        <option value="other">Other / General</option>
                      </select>
                    </div>
                    <div className="form-group">
                      <label htmlFor="severity">Severity</label>
                      <select id="severity" name="severity" required value={formData.severity} onChange={handleInputChange}>
                        <option value="mild">Mild</option>
                        <option value="moderate">Moderate</option>
                        <option value="severe">Severe</option>
                      </select>
                    </div>
                  </div>

                  {/* Symptoms */}
                  <div className="form-group">
                    <label>Frequent Symptoms</label>
                    <div className="symptom-grid">
                      {symptomsList.map((s) => (
                        <div
                          key={s.id}
                          className={`symptom-tag${selectedSymptoms.includes(s.id) ? " selected" : ""}`}
                          onClick={() => toggleSymptom(s.id)}
                        >
                          <div className="symptom-check" />
                          {s.label}
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Triggers */}
                  <div className="form-group">
                    <label htmlFor="personalized_issue">Known Triggers</label>
                    <textarea
                      id="personalized_issue" name="personalized_issue" rows={2}
                      placeholder="e.g. Cold air, dust, specific pollen, exercise…"
                      value={formData.personalized_issue} onChange={handleInputChange}
                    />
                  </div>

                  {/* Custom AQI Alert Threshold */}
                  <div className="form-group">
                    <label htmlFor="alert_threshold">
                      Your Unsafe AQI Level
                      <span style={{ fontSize: "0.75rem", color: "var(--muted-foreground)", fontWeight: "normal", marginLeft: "0.5rem" }}>
                        (Alert me when AQI crosses this)
                      </span>
                    </label>
                    <input
                      type="number"
                      id="alert_threshold"
                      name="alert_threshold"
                      min="50"
                      max="500"
                      step="10"
                      placeholder="100"
                      value={formData.alert_threshold || 100}
                      onChange={handleInputChange}
                      style={{ fontFamily: "var(--font-mono)" }}
                    />
                    <p style={{ fontSize: "0.75rem", color: "var(--muted-foreground)", marginTop: "0.375rem" }}>
                      Standard: 100 (Satisfactory) · High sensitivity: 50 (Good) · Low sensitivity: 150 (Moderate)
                    </p>
                  </div>

                  {/* Location */}
                  <div className="form-section-title" style={{ marginTop: "1.5rem" }}>Location</div>
                  <div className="location-box">
                    <p style={{ fontSize: "0.8125rem", color: "var(--muted-foreground)", marginBottom: "0.875rem", lineHeight: 1.5 }}>
                      Required for nearest CPCB station AQI data.
                    </p>
                    <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginBottom: "0.75rem" }}>
                      <button type="button" className="btn-secondary" onClick={getLocation} disabled={locationStatus.type === "loading"} style={{ flex: 1 }}>
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
                        {formData.lat ? "GPS Secured ✓" : "Use GPS Location"}
                      </button>
                    </div>
                    <div style={{ display: "flex", gap: "0.5rem" }}>
                      <input
                        type="text" placeholder="Search city, pincode…"
                        style={{ flex: 1 }}
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); handleGeocodeSearch(e as any); } }}
                      />
                      <button type="button" className="btn-secondary" onClick={handleGeocodeSearch} disabled={geocoding || !searchQuery.trim()}>
                        {geocoding ? <span className="loader-ring" /> : "Search"}
                      </button>
                    </div>
                    {locationStatus.message && (
                      <div className={`location-status-msg ${locationStatus.type || ""}`}>{locationStatus.message}</div>
                    )}
                    <div style={{ display: "flex", gap: "0.5rem", alignItems: "flex-start", marginTop: "0.875rem" }}>
                      <input type="checkbox" id="location_consent" required style={{ width: "14px", height: "14px", marginTop: "0.2rem", flexShrink: 0, accentColor: "var(--accent)" }} />
                      <label htmlFor="location_consent" style={{ margin: 0, fontSize: "0.75rem", cursor: "pointer", textTransform: "none", letterSpacing: "normal", lineHeight: 1.4, color: "var(--muted-foreground)" }}>
                        I consent to sharing my location for AQI analysis and alert routing.
                      </label>
                    </div>
                  </div>

                  <button type="submit" className="btn-primary" disabled={loading}>
                    {loading ? <><span className="loader-ring" /> Registering…</> : <>Complete Registration →</>}
                  </button>

                  {feedback && (
                    <div className={`feedback-msg ${feedback.isError ? "error" : "success"}`}>{feedback.message}</div>
                  )}

                  <div style={{ marginTop: "1.5rem", textAlign: "center" }}>
                    <p style={{ fontSize: "0.8125rem", color: "var(--muted-foreground)" }}>
                      Already registered?{" "}
                      <Link href="/login" style={{ color: "var(--accent)", textDecoration: "none", fontWeight: 500 }}>Login here</Link>
                    </p>
                  </div>
                </form>
              </div>
          </div>
        </section>

        {/* ── Features Row ── */}
        <section className="section">
          <div className="section-inner">
            <div className="reveal" style={{ textAlign: "center", marginBottom: "4rem" }}>
              <div className="overline" style={{ justifyContent: "center", marginBottom: "1rem" }}>
                <span className="overline-dash" />
                How It Works
                <span className="overline-dash" />
              </div>
              <h2 className="font-display" style={{ fontSize: "clamp(2.5rem, 5vw, 4.5rem)", fontWeight: 300, letterSpacing: "-0.02em" }}>
                Intelligence that{" "}
                <em style={{ color: "rgba(242,240,232,0.55)" }}>breathes with you.</em>
              </h2>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "1.5rem" }}>
              {[
                {
                  icon: "◎", label: "Live CPCB Data", delay: "0ms",
                  desc: "Pulls real-time readings from the nearest CPCB-certified India monitoring station to your GPS coordinates via WAQI and OpenAQ.",
                },
                {
                  icon: "⬡", label: "LSTM AI Forecast", delay: "100ms",
                  desc: "A trained long short-term memory neural network predicts your local AQI 24 hours ahead using 17 environmental features.",
                },
                {
                  icon: "◈", label: "Personalised Alerts", delay: "200ms",
                  desc: "Precautions are tailored to your exact condition, severity, symptoms, and known triggers — not generic health advice.",
                },
              ].map((f) => (
                <div key={f.label} className="glass reveal" style={{ borderRadius: "1.5rem", padding: "2rem", transitionDelay: f.delay }}>
                  <div style={{ fontSize: "1.5rem", color: "var(--accent)", marginBottom: "1.25rem", fontFamily: "var(--font-mono)" }}>{f.icon}</div>
                  <div style={{ fontSize: "0.6875rem", textTransform: "uppercase", letterSpacing: "0.25em", color: "var(--muted-foreground)", marginBottom: "0.75rem" }}>{f.label}</div>
                  <p style={{ fontSize: "0.9375rem", lineHeight: 1.7, color: "rgba(242,240,232,0.75)" }}>{f.desc}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ── Footer ── */}
        <footer style={{ borderTop: "1px solid var(--border)", padding: "3rem 2.5rem" }}>
          <div style={{ maxWidth: "1400px", margin: "0 auto", display: "flex", justifyContent: "space-between", alignItems: "flex-end", flexWrap: "wrap", gap: "1.5rem" }}>
            <div>
              <div className="logo" style={{ marginBottom: "0.75rem" }}>
                <div className="logo-orb"><div className="logo-orb-inner" /></div>
                <span className="logo-name">Pranarakshak</span>
              </div>
              <p style={{ fontSize: "0.8125rem", color: "var(--muted-foreground)", maxWidth: "34ch", lineHeight: 1.6 }}>
                Environmental health intelligence for India.<br />© 2026 Pranarakshak System.
              </p>
            </div>
            <div style={{ display: "flex", gap: "2rem", fontSize: "0.75rem", textTransform: "uppercase", letterSpacing: "0.2em", color: "var(--muted-foreground)" }}>
              <Link href="/" style={{ color: "inherit", textDecoration: "none" }}>Register</Link>
              <Link href="/login" style={{ color: "inherit", textDecoration: "none" }}>Login</Link>
              <Link href={activeUserId ? `/dashboard?user_id=${activeUserId}` : "/dashboard"} style={{ color: "inherit", textDecoration: "none" }}>Dashboard</Link>
            </div>
          </div>
        </footer>
      </main>

      {/* ── Success Modal ── */}
      <div className={`modal-backdrop${showModal ? " open" : ""}`} onClick={(e) => { if (e.target === e.currentTarget) setShowModal(false); }}>
        <div className="glass modal-box">
          <div className="success-circle">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" /><polyline points="22 4 12 14.01 9 11.01" />
            </svg>
          </div>
          <h2 className="modal-title">Profile Created</h2>
          <p className="modal-desc">You will now receive AI-powered AQI alerts personalised to your health profile.</p>
          <div className="user-id-box">
            <span className="user-id-label">Your User ID</span>
            <span className="user-id-code">{registeredUserId}</span>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
            <Link href={`/dashboard?user_id=${registeredUserId}`} className="btn-accent">
              View Dashboard →
            </Link>
            <button onClick={() => setShowModal(false)} className="btn-secondary" style={{ width: "100%" }}>
              Close
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
