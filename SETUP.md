# AQI Alert System — Deployment Setup Guide

Complete checklist to connect Railway backend ↔ Vercel frontend ↔ Supabase OAuth.

---

## 1. Supabase — Run the SQL Schema

1. Go to **https://supabase.com/dashboard/project/lgnaabrgdqomxuxfonqo/sql/new**
2. Paste the entire contents of `backend/schema.sql`
3. Click **Run** — all tables, RLS policies, triggers, and functions will be created

---

## 2. Supabase — Get Your Anon Key

1. Go to **https://supabase.com/dashboard/project/lgnaabrgdqomxuxfonqo/settings/api**
2. Under **Project API keys**, copy the **`anon` `public`** key (starts with `eyJ...`)
3. You will need this in steps 3 and 4 below

---

## 3. Supabase — Enable Google OAuth

1. Go to **https://supabase.com/dashboard/project/lgnaabrgdqomxuxfonqo/auth/providers**
2. Find **Google** and toggle it **Enabled**
3. You need a Google OAuth Client ID and Secret:
   - Open **https://console.cloud.google.com/apis/credentials**
   - Create a project (or use existing)
   - Click **Create Credentials → OAuth 2.0 Client ID**
   - Application type: **Web application**
   - Under **Authorised redirect URIs** add exactly:
     ```
     https://lgnaabrgdqomxuxfonqo.supabase.co/auth/v1/callback
     ```
   - Copy the **Client ID** and **Client Secret**
4. Back in Supabase Google provider settings:
   - Paste the **Client ID** and **Client Secret**
   - Click **Save**

---

## 4. Supabase — Set Redirect URLs (allow Vercel + localhost)

1. Go to **https://supabase.com/dashboard/project/lgnaabrgdqomxuxfonqo/auth/url-configuration**
2. Set **Site URL** to your Vercel URL:
   ```
   https://your-app.vercel.app
   ```
3. Under **Redirect URLs** add ALL of these (one per line):
   ```
   https://your-app.vercel.app/auth/callback
   https://your-app.vercel.app/reset-password
   http://localhost:3000/auth/callback
   http://localhost:3000/reset-password
   ```
4. Click **Save**

---

## 5. Vercel — Add Environment Variables

1. Go to **https://vercel.com** → your project → **Settings → Environment Variables**
2. Add these three variables for **Production**, **Preview**, and **Development**:

   | Key | Value |
   |-----|-------|
   | `NEXT_PUBLIC_SUPABASE_URL` | `https://lgnaabrgdqomxuxfonqo.supabase.co` |
   | `NEXT_PUBLIC_SUPABASE_ANON_KEY` | `eyJ...` ← the anon key from step 2 |
   | `NEXT_PUBLIC_API_URL` | `https://your-backend.up.railway.app` ← your Railway URL |

3. After adding variables, go to **Deployments → Redeploy** (the env vars only take effect on fresh builds)

---

## 6. Railway — Add Environment Variables

1. Go to **https://railway.app** → your project → your backend service → **Variables**
2. Add or update these:

   | Key | Value |
   |-----|-------|
   | `SUPABASE_URL` | `https://lgnaabrgdqomxuxfonqo.supabase.co` |
   | `SUPABASE_SERVICE_KEY` | your service_role key from Supabase Settings → API |
   | `CORS_ORIGINS` | `https://your-app.vercel.app` ← your Vercel URL (no trailing slash) |
   | `WAQI_TOKEN` | your WAQI token |
   | `OWM_API_KEY` | your OpenWeatherMap key |

3. Railway auto-redeploys when variables are saved

---

## 7. Local Development

Update `frontend-next/.env.local`:

```env
NEXT_PUBLIC_SUPABASE_URL=https://lgnaabrgdqomxuxfonqo.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ...   ← paste your actual anon key here
NEXT_PUBLIC_API_URL=https://your-backend.up.railway.app
```

Then run:
```bash
cd frontend-next
npm run dev
```

---

## 8. Verify the Full OAuth Flow

1. Open your Vercel URL → click **Login**
2. Click **Continue with Google**
3. You should be redirected to Google's consent screen
4. After approving, Google redirects to:
   ```
   https://lgnaabrgdqomxuxfonqo.supabase.co/auth/v1/callback
   ```
5. Supabase redirects to:
   ```
   https://your-app.vercel.app/auth/callback?code=...
   ```
6. `/auth/callback` exchanges the code for a session and redirects to `/dashboard`
7. Dashboard loads with the Supabase `user.id` as `user_id`

---

## 9. Auth Flow Summary

```
User clicks "Continue with Google"
  │
  ▼
supabase.auth.signInWithOAuth({ provider: "google", redirectTo: "/auth/callback" })
  │
  ▼
Google consent screen
  │
  ▼
Supabase /auth/v1/callback  (exchanges Google code for Supabase session)
  │
  ▼
Your /auth/callback?code=...
  │
  ▼
exchangeCodeForSession(code)  →  session stored in localStorage
  │
  ▼
/dashboard?user_id=<supabase_user_id>
```

---

## 10. Password Reset Flow

```
User clicks "Forgot password?" on /login
  │
  ▼
/forgot-password  →  supabase.auth.resetPasswordForEmail(email, { redirectTo: "/auth/callback" })
  │
  ▼
Supabase sends email with link:
  https://your-app.vercel.app/auth/callback?type=recovery&code=...
  │
  ▼
/auth/callback detects type=recovery  →  exchangeCodeForSession(code)  →  /reset-password
  │
  ▼
/reset-password  →  supabase.auth.updateUser({ password: newPassword })  →  /login
```
