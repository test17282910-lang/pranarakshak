"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";

export default function Home() {
  const [formData, setFormData] = useState({
    name: "", email: "", phone: "", password: "",
    condition: "", severity: "moderate",
    lat: null as number | null, lon: null as number | null,
    personalized_issue: "",
  });
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

  const API_BASE_URL = "http://localhost:8000";

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
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Registration failed");
      setRegisteredUserId(data.user_id);
      setShowModal(true);
      setFormData({ name: "", email: "", phone: "", password: "", condition: "", severity: "moderate", lat: null, lon: null, personalized_issue: "" });
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
            <span className="logo-name">AQI Alert</span>
          </div>
          <div className="topbar-status">
            <span className="live-dot animate-pulse" />
            Live · India · CPCB
          </div>
          <nav className="nav-links">
            <Link href="/" className="nav-link active">Register</Link>
            <Link href="/login" className="nav-link">Login</Link>
            <Link href={activeUserId ? `/dashboard?user_id=${activeUserId}` : "/dashboard"} className="nav-link">Dashboard</Link>
          </nav>
        </div>
      </header>

      <main className="page-wrap">
        {/* ── Hero Section ── */}
        <section className="section" style={{ minHeight: "100svh", display: "flex", alignItems: "center", paddingTop: "8rem" }}>
          <div className="section-inner" style={{ width: "100%" }}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "5rem", alignItems: "center", maxWidth: "1200px", margin: "0 auto" }}>
              {/* Left: Copy */}
              <div>
                <div className="overline reveal" style={{ transitionDelay: "0ms" }}>
                  <span className="overline-dash" />
                  Personalised Health Intelligence
                </div>

                <h1
                  className="font-display reveal"
                  style={{
                    fontSize: "clamp(3.5rem, 7vw, 7rem)",
                    fontWeight: 300,
                    lineHeight: 0.95,
                    letterSpacing: "-0.03em",
                    marginTop: "2rem",
                    transitionDelay: "120ms",
                  }}
                >
                  Breathe<br />
                  <em style={{ color: "rgba(242,240,232,0.6)", fontStyle: "italic" }}>safely.</em>
                </h1>

                <p className="reveal" style={{
                  marginTop: "2rem", fontSize: "1.125rem", lineHeight: 1.7,
                  color: "var(--muted-foreground)", maxWidth: "44ch", transitionDelay: "240ms",
                }}>
                  AI-powered 24-hour AQI forecasts from real CPCB India monitoring stations —
                  personalised to your respiratory condition and triggers.
                </p>

                <div className="reveal" style={{ marginTop: "3rem", display: "flex", flexWrap: "wrap", gap: "2rem", transitionDelay: "360ms" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.625rem" }}>
                    <div style={{ display: "flex", height: "24px", alignItems: "flex-end", gap: "3px" }}>
                      {[0.9, 0.7, 0.5, 0.35, 0.2].map((h, i) => (
                        <span key={i} style={{ display: "block", width: "3px", height: `${h * 100}%`, background: "var(--accent)", borderRadius: "2px", opacity: i < 4 ? 1 : 0.3 }} />
                      ))}
                    </div>
                    <span style={{ fontSize: "0.6875rem", textTransform: "uppercase", letterSpacing: "0.25em", color: "var(--muted-foreground)" }}>
                      Model Confidence · 94%
                    </span>
                  </div>
                </div>

                <div className="reveal" style={{ marginTop: "3rem", paddingTop: "2rem", borderTop: "1px solid var(--border)", display: "grid", gridTemplateColumns: "repeat(3, auto)", gap: "2.5rem", transitionDelay: "480ms" }}>
                  {[
                    { label: "Sources", value: "WAQI", sub: "CPCB India" },
                    { label: "Forecast", value: "24h", sub: "Ahead" },
                    { label: "Model", value: "LSTM", sub: "AI-Powered" },
                  ].map((s) => (
                    <div key={s.label}>
                      <div style={{ fontSize: "0.625rem", textTransform: "uppercase", letterSpacing: "0.25em", color: "var(--muted-foreground)" }}>{s.label}</div>
                      <div style={{ fontFamily: "var(--font-display)", fontSize: "1.875rem", fontWeight: 200, marginTop: "0.25rem" }}>{s.value}</div>
                      <div style={{ fontSize: "0.6875rem", color: "var(--muted-foreground)" }}>{s.sub}</div>
                    </div>
                  ))}
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
                    <input type="password" id="password" name="password" required placeholder="Create a secure account password" value={formData.password} onChange={handleInputChange} />
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
          </div>

          {/* Scroll cue */}
          <div style={{
            position: "absolute", bottom: "2rem", left: "50%", transform: "translateX(-50%)",
            display: "flex", flexDirection: "column", alignItems: "center", gap: "0.75rem",
            fontSize: "0.625rem", textTransform: "uppercase", letterSpacing: "0.4em", color: "rgba(122,136,153,0.6)",
          }}>
            <span>Scroll</span>
            <span style={{ display: "block", width: "1px", height: "2.5rem", background: "linear-gradient(to bottom, rgba(242,240,232,0.5), transparent)" }} className="animate-float-y" />
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
                  desc: "A trained long short-term memory neural network predicts your local AQI 24 hours ahead using 18 environmental features.",
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
                <span className="logo-name">AQI Alert</span>
              </div>
              <p style={{ fontSize: "0.8125rem", color: "var(--muted-foreground)", maxWidth: "34ch", lineHeight: 1.6 }}>
                Environmental health intelligence for India.<br />© 2026 AQI Alert System.
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

      {/* ── Command Dock ── */}
      <nav className={`command-dock${dockHidden ? " hidden" : ""}`}>
        <div className="glass dock-inner">
          {[
            { href: "/", label: "Register", icon: "○" },
            { href: "/login", label: "Login", icon: "◎" },
            { href: activeUserId ? `/dashboard?user_id=${activeUserId}` : "/dashboard", label: "Dashboard", icon: "⬡" },
          ].map((item) => (
            <Link key={item.label} href={item.href} className="dock-item">
              <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.875rem" }}>{item.icon}</span>
              <span>{item.label}</span>
            </Link>
          ))}
        </div>
      </nav>

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
