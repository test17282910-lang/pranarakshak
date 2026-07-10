"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabaseClient";

export default function AuthCallback() {
  const router = useRouter();

  useEffect(() => {
    const handleAuthCallback = async () => {
      const { data, error } = await supabase.auth.getSession();
      if (error) {
        console.error("Auth callback error:", error);
        router.push("/login?error=auth_failed");
        return;
      }
      
      const session = data?.session;
      if (session?.user) {
        localStorage.setItem("aqi_user_id", session.user.id);
        // Redirect to dashboard with user_id query parameter
        router.push(`/dashboard?user_id=${session.user.id}`);
      } else {
        router.push("/login");
      }
    };

    handleAuthCallback();
  }, [router]);

  return (
    <div style={{
      minHeight: "100vh",
      display: "flex",
      flexDirection: "column",
      justifyContent: "center",
      alignItems: "center",
      background: "var(--background)",
      color: "var(--foreground)"
    }}>
      <div className="loader-ring" style={{ width: 48, height: 48, border: "4px solid var(--accent)", borderTopColor: "transparent", borderRadius: "50%", animation: "spin 1s linear infinite" }} />
      <p style={{ marginTop: "1rem", fontSize: "0.875rem", color: "var(--muted-foreground)" }}>Completing Google authentication...</p>
      
      <style jsx global>{`
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}
