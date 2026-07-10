import { createClient, SupabaseClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || "https://lgnaabrgdqomxuxfonqo.supabase.co";
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "";

let _client: SupabaseClient | null = null;

/**
 * Returns a Supabase client instance.
 * Only initialised when first called — prevents crashes at module load
 * when NEXT_PUBLIC_SUPABASE_ANON_KEY hasn't been configured yet.
 * Required only for Google OAuth. Password login goes through the FastAPI backend.
 */
export function getSupabaseClient(): SupabaseClient {
  if (!supabaseAnonKey) {
    throw new Error(
      "NEXT_PUBLIC_SUPABASE_ANON_KEY is not set. Add it to frontend-next/.env.local to enable Google login."
    );
  }
  if (!_client) {
    _client = createClient(supabaseUrl, supabaseAnonKey);
  }
  return _client;
}

/** Convenience re-export for code that needs the client directly */
export const supabase = {
  auth: {
    signInWithOAuth: (...args: Parameters<SupabaseClient["auth"]["signInWithOAuth"]>) =>
      getSupabaseClient().auth.signInWithOAuth(...args),
    getSession: (...args: Parameters<SupabaseClient["auth"]["getSession"]>) =>
      getSupabaseClient().auth.getSession(...args),
  },
};
