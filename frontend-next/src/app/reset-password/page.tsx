"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { getSupabaseClient } from "@/lib/supabaseClient";

// ── SVG Icons ─────────────────────────────────────────────────────────────────
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

// ── Password strength util ────────────────────────────────────────────────────
function getStrength(pw: string): { score: number; label: string; color: string } {
  let score = 0;
  if (pw.length >= 8)  score++;
  if (pw.length >= 12) score++;
  if (/[A-Z]/.test(pw)) score++;
  if (/[0-9]/.test(pw)) score++;
  if (/[^A-Za-z0-9]/.test(pw)) score++;

  const levels = [
    { score: 0, label: "",        color: "transparent" },
    { score: 1, label: "Weak",    color: "oklch(0.62 0.18 28)" },
    { score: 2, label: "Fair",    color: "oklch(0.72 0.14 45)" },
    { score: 3, label: "Good",    color: "oklch(0.82 0.11 78)" },
    { score: 4, label: "Strong",  color: "oklch(0.75 0.11 162)" },
    { score: 5, label: "Very Strong", color: "oklch(0.78 0.09 210)" },
  ];
  return levels[Math.min(score, 5)];
}

// ── Component ─────────────────────────────────────────────────────────────────
export default function ResetPassword() {
  const router = useRouter();

  const [password, setPassword]           = useState("");
  const [confirm, setConfirm]             = useState("");
  const [showPassword, setShowPassword]   = useState(false);
  const [showConfirm, setShowConfirm]     = useState(false);
  const [loading, setLoading]             = useState(false);
  const [sessionReady, setSessionReady]   = useState(false);
  const [feedback, setFeedback]           = useState<{ message: string; isError: boolean } | null>(null);
  const [done, setDone]                   = useState(false);

  const strength = getStrength(password);
  const mismatch = confirm.length > 0 && password !== confirm;

  // The /auth/callback page already called exchangeCodeForSession.
  // We just verify the session is active before rendering the form.
  useEffect(() => {
    const check = async () => {
      try {
        const supabase = getSupabaseClient();
        const { data } = await supabase.auth.getSession();
        if (data.session) {
          setSessionReady(true);
        } else {
          // No active session — the reset link may have expired
          setFeedback({ message: "Your reset link has expired or is invalid. Please request a new one.", isError: true });
        }
      } catch {
        setFeedback({ message: "Could not verify session. Please try again.", isError: true });
      }
    };
    check();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password !== confirm) {
      setFeedback({ message: "Passwords do not match.", isError: true });
      return;
    }
    if (password.length < 8) {
      setFeedback({ message: "Password must be at least 8 characters.", isError: true });
      return;
    }

    setFeedback(null);
    setLoading(true);

    try {
      const supabase = getSupabaseClient();
      const { error } = await supabase.auth.updateUser({ password });
      if (error) throw error;
      setDone(true);
      // Sign out so the user must log in fresh with the new password
      await supabase.auth.signOut();
      setTimeout(() => router.replace("/login"), 2500);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to update password.";
      setFeedback({ message: msg, isError: true });
    } finally {
      setLoading(false);
    }
  };

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <>
      <div className="ambient-bg" aria-hidden="true">
        <div className="orb-1" />
        <div className="orb-2" />
        <div className="vignette-top" />
        <div className="vignette-bottom" />
      </div>

      <header className="topbar">
        <div className="topbar-inner">
          <Link href="/" className="logo" style={{ textDecoration: "none", color: "var(--foreground)" }}>
            <div className="logo-orb"><div className="logo-orb-inner" /></div>
            <span className="logo-name">AQI Alert</span>
          </Link>
        </div>
      </header>

      <div className="login-wrap">
        <div className="glass login-card" role="main">

          {done ? (
            /* ── Success state ── */
            <div style={{ textAlign: "center" }}>
              <div style={{
                width: 64, height: 64, borderRadius: "50%",
                background: "rgba(var(--accent-rgb), 0.12)",
                border: "1px solid rgba(var(--accent-rgb), 0.3)",
                display: "flex", alignItems: "center", justifyContent: "center",
                margin: "0 auto 1.75rem", fontSize: "1.75rem", color: "var(--accent)",
              }} aria-hidden="true">
                ✓
              </div>
              <h1 className="login-title" style={{ fontSize: "2rem" }}>Password updated</h1>
              <p style={{ color: "var(--muted-foreground)", fontSize: "0.9375rem", marginTop: "0.75rem", lineHeight: 1.6 }}>
                Your new password is set. Redirecting you to login…
              </p>
            </div>

          ) : (
            <>
              <div className="login-header">
                <div style={{
                  width: 64, height: 64, borderRadius: "50%",
                  background: "rgba(var(--accent-rgb), 0.10)",
                  border: "1px solid rgba(var(--accent-rgb), 0.2)",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  margin: "0 auto 1.75rem", fontSize: "1.625rem",
                }} aria-hidden="true">
                  🔒
                </div>
                <h1 className="login-title">New password</h1>
                <p className="login-subtitle">
                  Choose a strong password — at least 8 characters, mix of letters, numbers &amp; symbols.
                </p>
              </div>

              {!sessionReady && !feedback?.isError ? (
                <div style={{ display: "flex", justifyContent: "center", padding: "2rem 0" }}>
                  <div
                    style={{
                      width: 40, height: 40,
                      border: "3px solid rgba(255,255,255,0.08)",
                      borderTopColor: "var(--accent)",
                      borderRadius: "50%",
                      animation: "spin 1s linear infinite",
                    }}
                    role="status"
                    aria-label="Verifying session"
                  />
                </div>
              ) : (
                <form onSubmit={handleSubmit} noValidate>
                  {/* New password */}
                  <div className="form-group">
                    <label htmlFor="new-password">New Password</label>
                    <div className="password-field-wrap">
                      <input
                        type={showPassword ? "text" : "password"}
                        id="new-password"
                        autoComplete="new-password"
                        required
                        placeholder="Create a strong password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        aria-describedby="pw-strength-label"
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

                    {/* Strength bar */}
                    {password.length > 0 && (
                      <>
                        <div className="password-strength-bar" aria-hidden="true">
                          <div
                            className="password-strength-fill"
                            style={{
                              width: `${(strength.score / 5) * 100}%`,
                              backgroundColor: strength.color,
                            }}
                          />
                        </div>
                        <p
                          id="pw-strength-label"
                          className="password-strength-label"
                          style={{ color: strength.color }}
                          aria-live="polite"
                        >
                          {strength.label}
                        </p>
                      </>
                    )}
                  </div>

                  {/* Confirm password */}
                  <div className="form-group">
                    <label htmlFor="confirm-password">Confirm Password</label>
                    <div className="password-field-wrap">
                      <input
                        type={showConfirm ? "text" : "password"}
                        id="confirm-password"
                        autoComplete="new-password"
                        required
                        placeholder="Repeat your new password"
                        value={confirm}
                        onChange={(e) => setConfirm(e.target.value)}
                        style={{
                          borderColor: mismatch ? "oklch(0.62 0.18 28 / 0.6)" : undefined,
                        }}
                        aria-invalid={mismatch}
                        aria-describedby={mismatch ? "confirm-error" : undefined}
                      />
                      <button
                        type="button"
                        className="password-toggle-btn"
                        onClick={() => setShowConfirm((v) => !v)}
                        aria-label={showConfirm ? "Hide confirm password" : "Show confirm password"}
                      >
                        {showConfirm ? <EyeOffIcon /> : <EyeIcon />}
                      </button>
                    </div>
                    {mismatch && (
                      <p
                        id="confirm-error"
                        style={{ fontSize: "0.75rem", color: "oklch(0.62 0.18 28)", marginTop: "0.4rem" }}
                        role="alert"
                      >
                        Passwords do not match.
                      </p>
                    )}
                  </div>

                  <button
                    type="submit"
                    className="btn-primary"
                    disabled={loading || !sessionReady || !password || !confirm || mismatch}
                    style={{ marginTop: "0.5rem" }}
                  >
                    {loading ? (
                      <>
                        <span
                          className="loader-ring"
                          style={{ borderColor: "rgba(0,0,0,0.2)", borderTopColor: "#000" }}
                          aria-hidden="true"
                        />
                        Updating…
                      </>
                    ) : (
                      "Set New Password →"
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
                      {feedback.isError && feedback.message.includes("expired") && (
                        <> {" "}
                          <Link href="/forgot-password" style={{ color: "inherit", fontWeight: 600 }}>
                            Request a new link →
                          </Link>
                        </>
                      )}
                    </div>
                  )}
                </form>
              )}
            </>
          )}
        </div>
      </div>
    </>
  );
}
