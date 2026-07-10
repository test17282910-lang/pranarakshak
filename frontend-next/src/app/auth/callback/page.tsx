"use client";

import { useEffect, useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { getSupabaseClient } from "@/lib/supabaseClient";

/**
 * /auth/callback
 *
 * Only handles the password-reset flow.
 * Supabase sends the user here with ?type=recovery&code=...
 * We exchange that code for a live session, then send them to /reset-password.
 *
 * Any other landing here (stale link, wrong URL) redirects to /login.
 */
function AuthCallbackContent() {
  const router       = useRouter();
  const searchParams = useSearchParams();
  const [statusMsg, setStatusMsg] = useState("Verifying reset link…");
  const [isError, setIsError]     = useState(false);

  useEffect(() => {
    const run = async () => {
      try {
        const type = searchParams.get("type");
        const code = searchParams.get("code");

        if (type === "recovery" && code) {
          // Exchange the one-time code for a short-lived session
          const supabase = getSupabaseClient();
          const { error } = await supabase.auth.exchangeCodeForSession(code);
          if (error) throw error;

          setStatusMsg("Link verified. Redirecting…");
          router.replace("/reset-password");
          return;
        }

        // Anything else — stale link, wrong params, etc.
        throw new Error("Invalid or expired reset link. Please request a new one.");
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : "Something went wrong.";
        setStatusMsg(message);
        setIsError(true);
        setTimeout(() => router.replace(`/forgot-password`), 2500);
      }
    };

    run();
  }, [router, searchParams]);

  return (
    <div style={{
      minHeight: "100vh",
      display: "flex", flexDirection: "column",
      justifyContent: "center", alignItems: "center",
      gap: "1.25rem",
      background: "var(--background)",
      color: "var(--foreground)",
      padding: "2rem",
      textAlign: "center",
      position: "relative",
      zIndex: 1,
    }}>
      {/* Logo */}
      <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "0.5rem" }}>
        <div className="logo-orb"><div className="logo-orb-inner" /></div>
        <span style={{ fontFamily: "var(--font-display)", fontSize: "1.25rem" }}>AQI Alert</span>
      </div>

      {/* Spinner or error icon */}
      {isError ? (
        <div style={{
          width: 52, height: 52, borderRadius: "50%",
          background: "rgba(248,113,113,0.1)",
          border: "2px solid rgba(248,113,113,0.3)",
          display: "flex", alignItems: "center", justifyContent: "center",
          color: "#f87171", fontSize: "1.5rem",
        }} aria-hidden="true">✕</div>
      ) : (
        <div style={{
          width: 52, height: 52,
          border: "3px solid rgba(255,255,255,0.08)",
          borderTopColor: "var(--accent)",
          borderRadius: "50%",
          animation: "spin 1s linear infinite",
        }} role="status" aria-label="Loading" />
      )}

      <p style={{
        fontSize: "0.9375rem",
        color: isError ? "#f87171" : "var(--muted-foreground)",
        maxWidth: "36ch", lineHeight: 1.6,
      }} role={isError ? "alert" : "status"} aria-live="polite">
        {statusMsg}
      </p>

      {isError && (
        <p style={{ fontSize: "0.8125rem", color: "var(--muted-foreground)" }}>
          Redirecting to forgot password…
        </p>
      )}
    </div>
  );
}

export default function AuthCallback() {
  return (
    <Suspense fallback={
      <div style={{
        minHeight: "100vh",
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        background: "var(--background)",
      }}>
        <div style={{
          width: 52, height: 52,
          border: "3px solid rgba(255,255,255,0.08)",
          borderTopColor: "var(--accent)",
          borderRadius: "50%",
          animation: "spin 1s linear infinite",
        }} role="status" aria-label="Loading" />
      </div>
    }>
      <AuthCallbackContent />
    </Suspense>
  );
}
