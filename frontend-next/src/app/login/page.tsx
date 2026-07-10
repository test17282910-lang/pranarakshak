"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabaseClient";

export default function Login() {
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [feedback, setFeedback] = useState<{ message: string; isError: boolean } | null>(null);
  const [activeUserId, setActiveUserId] = useState<string | null>(null);
  const router = useRouter();

  const API_BASE_URL = "http://localhost:8000";

  useEffect(() => {
    setActiveUserId(localStorage.getItem("aqi_user_id"));
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFeedback(null); setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ identifier, password }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Authentication failed.");
      localStorage.setItem("aqi_user_id", data.user_id);
      setFeedback({ message: "Login successful! Redirecting…", isError: false });
      setTimeout(() => router.push(`/dashboard?user_id=${data.user_id}`), 900);
    } catch (err: any) {
      setFeedback({ message: err.message || "Something went wrong.", isError: true });
    } finally { setLoading(false); }
  };

  const handleGoogleLogin = async () => {
    setFeedback(null);
    setGoogleLoading(true);
    try {
      const { error } = await supabase.auth.signInWithOAuth({
        provider: "google",
        options: {
          redirectTo: `${window.location.origin}/auth/callback`,
        },
      });
      if (error) throw error;
    } catch (err: any) {
      const isKeyMissing = err.message?.includes("NEXT_PUBLIC_SUPABASE_ANON_KEY");
      setFeedback({
        message: isKeyMissing
          ? "Google login not configured yet. Add NEXT_PUBLIC_SUPABASE_ANON_KEY to frontend-next/.env.local and restart the dev server."
          : err.message || "Google Authentication failed.",
        isError: true,
      });
      setGoogleLoading(false);
    }
  };

  return (
    <>
      {/* Top Bar */}
      <header className="topbar">
        <div className="topbar-inner">
          <Link href="/" className="logo" style={{ textDecoration: "none", color: "var(--foreground)" }}>
            <div className="logo-orb"><div className="logo-orb-inner" /></div>
            <span className="logo-name">AQI Alert</span>
          </Link>
          <div className="topbar-status">
            <span className="live-dot animate-pulse" />
            Live · India · CPCB
          </div>
          <nav className="nav-links">
            <Link href="/" className="nav-link">Register</Link>
            <Link href="/login" className="nav-link active">Login</Link>
            <Link href={activeUserId ? `/dashboard?user_id=${activeUserId}` : "/dashboard"} className="nav-link">Dashboard</Link>
          </nav>
        </div>
      </header>

      {/* Login form */}
      <div className="login-wrap">
        <div className="glass login-card">
          <div className="login-header">
            {/* Animated orb icon */}
            <div style={{
              width: 64, height: 64, borderRadius: "50%",
              background: "var(--gradient-orb)",
              animation: "orb-pulse 5s ease-in-out infinite",
              boxShadow: "0 0 60px rgba(var(--accent-rgb), 0.35)",
              margin: "0 auto 1.75rem",
            }} />
            <h1 className="login-title">Welcome back</h1>
            <p className="login-subtitle">Access your personalised AQI intelligence and health alerts.</p>
          </div>

          <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
            <div className="form-group">
              <label htmlFor="identifier">Email, Phone, or Patient ID</label>
              <input
                type="text" id="identifier" required
                placeholder="e.g. you@email.com, +91… or UUID"
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
              />
            </div>

            <div className="form-group">
              <label htmlFor="password">Password</label>
              <input
                type="password" id="password" required
                placeholder="Enter your account password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>

            <button type="submit" className="btn-primary" disabled={loading || googleLoading || !identifier.trim() || !password.trim()}>
              {loading ? <><span className="loader-ring" /> Verifying…</> : "Continue →"}
            </button>

            {/* Google OAuth Login Button */}
            <button
              type="button"
              className="btn-secondary"
              onClick={handleGoogleLogin}
              disabled={loading || googleLoading}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "0.75rem",
                marginTop: "0.5rem"
              }}
            >
              {googleLoading ? (
                <span className="loader-ring" />
              ) : (
                <svg viewBox="0 0 24 24" width="18" height="18" style={{ fill: "currentColor" }}>
                  <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
                  <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                  <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z" fill="#FBBC05"/>
                  <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z" fill="#EA4335"/>
                </svg>
              )}
              {googleLoading ? "Connecting to Google…" : "Continue with Google"}
            </button>

            {feedback && (
              <div className={`feedback-msg ${feedback.isError ? "error" : "success"}`} style={{ marginTop: "0.25rem" }}>
                {feedback.message}
              </div>
            )}
          </form>

          <div style={{ marginTop: "2rem", paddingTop: "1.5rem", borderTop: "1px solid var(--border)", textAlign: "center" }}>
            <p style={{ fontSize: "0.8125rem", color: "var(--muted-foreground)" }}>
              No account yet?{" "}
              <Link href="/" style={{ color: "var(--accent)", textDecoration: "none", fontWeight: 500 }}>Register here</Link>
            </p>
          </div>
        </div>
      </div>

      {/* Command Dock */}
      <nav className="command-dock">
        <div className="glass dock-inner">
          {[
            { href: "/", label: "Register", icon: "○" },
            { href: "/login", label: "Login", icon: "◎" },
            { href: activeUserId ? `/dashboard?user_id=${activeUserId}` : "/dashboard", label: "Dashboard", icon: "⬡" },
          ].map((item) => (
            <Link key={item.label} href={item.href} className={`dock-item${item.href === "/login" ? " active" : ""}`}>
              <span style={{ fontFamily: "var(--font-mono)" }}>{item.icon}</span>
              <span>{item.label}</span>
            </Link>
          ))}
        </div>
      </nav>
    </>
  );
}
