/**
 * supabaseClient.ts — Supabase browser-side client (anon key only)
 *
 * Responsibilities:
 *   - Google OAuth  →  supabase.auth.signInWithOAuth()
 *   - OAuth callback → supabase.auth.exchangeCodeForSession()
 *   - Session reads  → supabase.auth.getSession()
 *   - Password reset → supabase.auth.resetPasswordForEmail()
 *   - New password   → supabase.auth.updateUser()
 *
 * Everything else (DB reads/writes) goes through the FastAPI backend
 * using the service_role key.  Never put service_role here.
 *
 * Required env vars (frontend-next/.env.local  AND  Vercel project settings):
 *   NEXT_PUBLIC_SUPABASE_URL      = https://lgnaabrgdqomxuxfonqo.supabase.co
 *   NEXT_PUBLIC_SUPABASE_ANON_KEY = eyJ...   (anon public key)
 */

import { createClient, type SupabaseClient } from "@supabase/supabase-js";

const SUPABASE_URL      = process.env.NEXT_PUBLIC_SUPABASE_URL      ?? "";
const SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "";

// ── Lazy singleton ────────────────────────────────────────────────────────────
let _client: SupabaseClient | null = null;

export function getSupabaseClient(): SupabaseClient {
  if (_client) return _client;

  if (!SUPABASE_URL || !SUPABASE_ANON_KEY) {
    throw new Error(
      "Supabase is not configured.\n" +
      "Add these to frontend-next/.env.local and to Vercel → Settings → Environment Variables:\n" +
      "  NEXT_PUBLIC_SUPABASE_URL=https://lgnaabrgdqomxuxfonqo.supabase.co\n" +
      "  NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ...  ← anon public key from Supabase Dashboard → Settings → API"
    );
  }

  _client = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
    auth: {
      persistSession:    true,   // keep session across page refreshes
      autoRefreshToken:  true,   // auto-renew before expiry
      detectSessionInUrl: true,  // pick up ?code= from OAuth redirect
    },
  });

  return _client;
}

// Convenience named export — same instance, no proxy magic needed
export const supabase = {
  get auth() { return getSupabaseClient().auth; },
};
