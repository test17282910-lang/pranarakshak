"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

function EyeIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
      <circle cx="12" cy="12" r="3" />
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

export default function Login() {
  const [identifier, setIdentifier]     = useState("");
  const [password, setPassword]         = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading]           = useState(false);
  const [feedback, setFeedback]         = useState<{ message: string; isError: boolean } | null>(null);
  const [activeUserId, setActiveUserId] = useState<string | null>(null);

  const router = useRouter();
  const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  useEffect(() => {
    // If already logged in, go straight to dashboard
    const stored = localStorage.getItem("aqi_user_id");
    if (stored) {
      router.replace(`/dashboard?user_id=${stored}`);
    } else {
      setActiveUserId(null);
    }
  }, [router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFeedback(null);
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ identifier: identifier.trim(), password }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Authentication failed.");

      localStorage.setItem("aqi_user_id", data.user_id);
      setFeedback({ message: "Login successful! Taking you to your dashboard…", isError: false });

      // Redirect immediately — no artificial delay needed
      router.push(`/dashboard?user_id=${data.user_id}`);
    } catch (err: unknown) {
      setFeedback({
        message: err instanceof Error ? err.message : "Something went wrong.",
        isError: true,
      });
      setLoading(false);
    }
  };

  return (
    <>
      {/* Top Bar */}
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
            <Link href="/"      className="nav-link">Register</Link>
            <Link href="/login" className="nav-link active">Login</Link>
          </nav>
        </div>
      </header>

      {/* Card */}
      <div className="login-wrap">
        <div className="glass login-card" role="main">

          {/* Header orb + titles */}
          <div className="login-header">
            <div
              aria-hidden="true"
              style={{
                width: 64, height: 64,
                borderRadius: "50%",
                background: "var(--gradient-orb)",
                animation: "orb-pulse 5s ease-in-out infinite",
                boxShadow: "0 0 60px rgba(var(--accent-rgb), 0.35)",
                margin: "0 auto 1.75rem",
              }}
            />
            <h1 className="login-title">Welcome back</h1>
            <p className="login-subtitle">
              Access your personalised AQI intelligence and health alerts.
            </p>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} noValidate>
            <div className="form-group">
              <label htmlFor="identifier">Email or Phone</label>
              <input
                type="text"
                id="identifier"
                autoComplete="username email"
                required
                placeholder="you@email.com or +91…"
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
              />
            </div>

            <div className="form-group">
              {/* Label row with forgot-password link */}
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                <label htmlFor="password" style={{ margin: 0 }}>Password</label>
                <Link
                  href="/forgot-password"
                  style={{ fontSize: "0.75rem", color: "var(--accent)", textDecoration: "none", letterSpacing: "0.03em" }}
                >
                  Forgot password?
                </Link>
              </div>

              {/* Show / hide toggle */}
              <div className="password-field-wrap" style={{ marginTop: "0.5rem" }}>
                <input
                  type={showPassword ? "text" : "password"}
                  id="password"
                  autoComplete="current-password"
                  required
                  placeholder="Enter your password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
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
            </div>

            <button
              type="submit"
              className="btn-primary"
              disabled={loading || !identifier.trim() || !password.trim()}
              style={{ marginTop: "1.5rem" }}
            >
              {loading ? (
                <>
                  <span
                    className="loader-ring"
                    style={{ borderColor: "rgba(0,0,0,0.2)", borderTopColor: "#000" }}
                    aria-hidden="true"
                  />
                  Verifying…
                </>
              ) : (
                "Sign In →"
              )}
            </button>

            {feedback && (
              <div
                className={`feedback-msg ${feedback.isError ? "error" : "success"}`}
                role={feedback.isError ? "alert" : "status"}
                aria-live="polite"
                style={{ marginTop: "1rem" }}
              >
                {feedback.message}
              </div>
            )}
          </form>

          {/* Footer */}
          <div style={{ marginTop: "2rem", paddingTop: "1.5rem", borderTop: "1px solid var(--border)", textAlign: "center" }}>
            <p style={{ fontSize: "0.8125rem", color: "var(--muted-foreground)" }}>
              No account yet?{" "}
              <Link href="/" style={{ color: "var(--accent)", textDecoration: "none", fontWeight: 500 }}>
                Register here
              </Link>
            </p>
          </div>
        </div>
      </div>

      {/* Command Dock */}
      <nav className="command-dock" aria-label="Quick navigation">
        <div className="glass dock-inner">
          {[
            { href: "/",      label: "Register", icon: "○" },
            { href: "/login", label: "Login",    icon: "◎" },
          ].map((item) => (
            <Link
              key={item.label}
              href={item.href}
              className={`dock-item${item.href === "/login" ? " active" : ""}`}
            >
              <span style={{ fontFamily: "var(--font-mono)" }} aria-hidden="true">{item.icon}</span>
              <span>{item.label}</span>
            </Link>
          ))}
        </div>
      </nav>
    </>
  );
}
