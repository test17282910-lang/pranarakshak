"use client";

import { useState } from "react";
import Link from "next/link";
import { getSupabaseClient } from "@/lib/supabaseClient";

export default function ForgotPassword() {
  const [email, setEmail]       = useState("");
  const [loading, setLoading]   = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [feedback, setFeedback] = useState<{ message: string; isError: boolean } | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFeedback(null);
    setLoading(true);

    try {
      const supabase = getSupabaseClient();
      const { error } = await supabase.auth.resetPasswordForEmail(email.trim(), {
        redirectTo: `${window.location.origin}/auth/callback`,
      });
      if (error) throw error;
      setSubmitted(true);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to send reset email.";
      setFeedback({ message: msg, isError: true });
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      {/* Ambient background */}
      <div className="ambient-bg" aria-hidden="true">
        <div className="orb-1" />
        <div className="orb-2" />
        <div className="vignette-top" />
        <div className="vignette-bottom" />
      </div>

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

      <div className="login-wrap">
        <div className="glass login-card" role="main">

          {submitted ? (
            /* ── Success state ── */
            <div style={{ textAlign: "center" }}>
              <div style={{
                width: 64, height: 64, borderRadius: "50%",
                background: "rgba(var(--accent-rgb), 0.12)",
                border: "1px solid rgba(var(--accent-rgb), 0.3)",
                display: "flex", alignItems: "center", justifyContent: "center",
                margin: "0 auto 1.75rem", fontSize: "1.5rem", color: "var(--accent)",
              }}>
                ✓
              </div>
              <h1 className="login-title" style={{ fontSize: "2rem" }}>Check your inbox</h1>
              <p style={{ color: "var(--muted-foreground)", fontSize: "0.9375rem", marginTop: "0.75rem", lineHeight: 1.6 }}>
                A password reset link has been sent to{" "}
                <strong style={{ color: "var(--foreground)" }}>{email}</strong>.
                <br />It expires in 1 hour.
              </p>
              <p style={{ fontSize: "0.8125rem", color: "var(--muted-foreground)", marginTop: "1rem" }}>
                Didn&apos;t receive it? Check spam or{" "}
                <button
                  onClick={() => { setSubmitted(false); setEmail(""); }}
                  style={{ background: "none", border: "none", color: "var(--accent)", cursor: "pointer", fontSize: "inherit", fontWeight: 500 }}
                >
                  try again
                </button>.
              </p>
              <div style={{ marginTop: "2rem", paddingTop: "1.5rem", borderTop: "1px solid var(--border)" }}>
                <Link
                  href="/login"
                  style={{ color: "var(--muted-foreground)", fontSize: "0.8125rem", textDecoration: "none" }}
                >
                  ← Back to login
                </Link>
              </div>
            </div>

          ) : (
            /* ── Form state ── */
            <>
              <div className="login-header">
                {/* Lock icon */}
                <div style={{
                  width: 64, height: 64, borderRadius: "50%",
                  background: "rgba(var(--accent-rgb), 0.10)",
                  border: "1px solid rgba(var(--accent-rgb), 0.2)",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  margin: "0 auto 1.75rem", fontSize: "1.625rem",
                }} aria-hidden="true">
                  🔑
                </div>
                <h1 className="login-title">Reset password</h1>
                <p className="login-subtitle">
                  Enter your registered email address and we&apos;ll send you a secure reset link.
                </p>
              </div>

              <form onSubmit={handleSubmit} noValidate>
                <div className="form-group">
                  <label htmlFor="email">Email address</label>
                  <input
                    type="email"
                    id="email"
                    autoComplete="email"
                    required
                    placeholder="you@email.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                  />
                </div>

                <button
                  type="submit"
                  className="btn-primary"
                  disabled={loading || !email.trim()}
                  style={{ marginTop: "0.5rem" }}
                >
                  {loading ? (
                    <>
                      <span
                        className="loader-ring"
                        style={{ borderColor: "rgba(0,0,0,0.2)", borderTopColor: "#000" }}
                        aria-hidden="true"
                      />
                      Sending…
                    </>
                  ) : (
                    "Send Reset Link →"
                  )}
                </button>

                {feedback && (
                  <div
                    className={`feedback-msg ${feedback.isError ? "error" : "success"}`}
                    role="alert"
                    aria-live="polite"
                    style={{ marginTop: "1rem" }}
                  >
                    {feedback.message}
                  </div>
                )}
              </form>

              <div style={{ marginTop: "2rem", paddingTop: "1.5rem", borderTop: "1px solid var(--border)", textAlign: "center" }}>
                <Link
                  href="/login"
                  style={{ color: "var(--muted-foreground)", fontSize: "0.8125rem", textDecoration: "none" }}
                >
                  ← Back to login
                </Link>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Command Dock */}
      <nav className="command-dock" aria-label="Quick navigation">
        <div className="glass dock-inner">
          {[
            { href: "/",      label: "Register", icon: "○" },
            { href: "/login", label: "Login",    icon: "◎" },
          ].map((item) => (
            <Link key={item.label} href={item.href} className="dock-item">
              <span style={{ fontFamily: "var(--font-mono)" }} aria-hidden="true">{item.icon}</span>
              <span>{item.label}</span>
            </Link>
          ))}
        </div>
      </nav>
    </>
  );
}
