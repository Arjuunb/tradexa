# Tradexa

Premium dark trading-journal SaaS — vanilla HTML/CSS/JS frontend, Python `http.server` backend, Vercel-compatible `/api/*.py` serverless handlers, Gemini 2.5 Flash for AI features.

**Brand:** background `#0d0f12`, accent gold `#FFB732`.
**Run:** `python3 server.py` on port 5000.

## Auth — Supabase

Auth is implemented with **Supabase** (Google OAuth + email/password). No Clerk.

**Required Replit Secrets:**
- `SUPABASE_URL` — e.g. `https://xxx.supabase.co`
- `SUPABASE_ANON_KEY` — public anon key (safe in browser)
- `SUPABASE_JWT_SECRET` — HS256 signing secret used by the API to verify tokens
- `GEMINI_API_KEY` — for AI endpoints

**Architecture**
- `assets/supabase-auth.js` — loads `@supabase/supabase-js@2` from jsDelivr, fetches `/api/public-config` for the URL+anon key, exposes `window.TxAuth` (`ready / getUser / getToken / signIn* / signOut / userKey`). On any `/app/*` path it auto-runs a guard that hides the body and redirects to `/auth/login.html` if there's no session.
- `auth/login.html`, `auth/register.html`, `auth/callback.html`, `auth/reset.html` — branded glassmorphism auth pages.
  - **Providers shown:** controlled by `TxAuth.PROVIDERS` array at the top of `assets/supabase-auth.js` (default: `['google','github','discord']`). Edit that array to remove a provider's button. Web3 wallet is **not** wired (Supabase has no native Web3 provider).
  - **Forgot password:** inline reveal under the password field on the login page → `TxAuth.resetPassword(email)` calls Supabase `resetPasswordForEmail`. The email link lands on `/auth/reset.html`, which uses the recovery session to update the password via `updateUser`.
  - **Post-login transition:** `TxAuth.runLoginTransition({user, redirectTo})` renders a 3-step glass overlay (success ✔ → securing ring → welcome card) over ~2.6s, then fades out and redirects. Used by login, register, callback, and reset flows. Honours `prefers-reduced-motion`.
- Every `/app/*.html` page has a `<!-- tx-auth-guard-v3 -->` block injected at the top of `<head>` that hides body until the session is verified.
- `assets/nav.js` swaps the marketing-nav CTAs between **Login / Start Free** (signed-out) and a **user menu with Sign Out** (signed-in).
- `assets/app-sidebar.js` reads the real user from Supabase and updates the header avatar/initials. Click the avatar to sign out.
- All AI fetches (`tradebot.js`, `insights.js`, `app/ai-coach.html`, `app/daily-digest.html`, `app/weekly-reviews.html`) attach `Authorization: Bearer <supabase-access-token>`.

**Server-side verification.** `server.py` and each `api/*.py` handler call `verify_supabase_jwt(headers)`, a stdlib HMAC-SHA256 verifier (no PyJWT dep) that checks signature, expiry, and `aud='authenticated'`. Any AI endpoint without a valid token returns **401**. If `SUPABASE_JWT_SECRET` is unset, the verifier fails closed (all requests rejected).

**One-time Supabase / Google setup the user must do once:**
1. **Supabase → Authentication → URL Configuration**
   - *Site URL:* the deployed domain, e.g. `https://your-project.replit.app` (or the Replit dev URL while testing)
   - *Redirect URLs* (allow-list): add both `https://<your-domain>/auth/callback.html` and `http://localhost:5000/auth/callback.html`
2. **Supabase → Authentication → Providers → Google** — enable, paste the Google OAuth client id + secret. The callback URL Supabase expects in Google Cloud is `https://<project>.supabase.co/auth/v1/callback`.
3. **Google Cloud Console → APIs & Services → Credentials → OAuth 2.0 Client** — add the same Supabase callback URL above as an *Authorized redirect URI*.
4. *(Optional)* Email confirmations: turn off in Supabase Auth → Providers → Email if you want immediate sign-up without verifying email.

## Endpoints

| Endpoint | Method | Auth | Purpose |
| --- | --- | --- | --- |
| `/api/public-config` | GET | none | Returns `{supabaseUrl, supabaseAnonKey, configured}`. Both values are public. |
| `/api/chat` | POST | Bearer JWT | Trade Bot chat. `?stream=1` returns SSE. |
| `/api/insights` | POST | Bearer JWT | "AI insights" panel data (JSON-mode Gemini). |
| `/api/weekly-review` | POST | Bearer JWT | Gemini-generated weekly performance review. |

All AI endpoints require `GEMINI_API_KEY` to be set.

## Layout

```
server.py                # local dev server (handles /api/* + Supabase JWT verify)
api/                     # Vercel serverless handlers
  _shared.py             # Gemini helper + prompts + verify_supabase_jwt()
  chat.py                # POST — Bearer JWT required
  insights.py            # POST — Bearer JWT required
  weekly-review.py       # POST — Bearer JWT required
  public-config.py       # GET  — Supabase URL + anon key (public)
auth/                    # login.html, register.html, callback.html
app/                     # 19 protected-app pages, all guarded by tx-auth-guard-v3
assets/
  supabase-auth.js       # Supabase client + window.TxAuth + /app/* guard
  nav.js                 # marketing nav (auth-aware Login / user menu)
  app-sidebar.js         # in-app sidebar; reads real user via TxAuth
  tradebot.js insights.js   # attach Bearer token to /api/* fetches
  brand/
index.html               # marketing landing
product/ solutions/ problems/ resources/ tools/ legal/ company/ pricing/
vercel.json _headers netlify.toml _redirects   # hosting configs (CSP allows *.supabase.co)
requirements.txt         # empty — stdlib only (HS256 hand-verified)
```

## Brand assets

- `assets/brand/tradexa-logo-full.png` — multi-color wordmark with candlesticks + blue arrow
- `assets/brand/tradexa-logo-icon.png` — square icon variant
- `assets/favicon.svg`, `favicon.ico`, `apple-touch-icon.png`

## Recent changes

- **Removed Clerk auth entirely.** Deleted `auth/`, `assets/clerk-auth.js`, `api/config.py`, `scripts/patch_app_guard.py`. Stripped JWT verification + `/api/config` route from `server.py` and `api/_shared.py`. Removed `<!-- tx-auth-guard-v2 -->` blocks and inline `TxAuth.*` calls from all 19 `/app/*.html` pages and from `assets/{nav,app-sidebar,tradebot,insights}.js`. Rewrote 39 marketing pages to retarget any `/auth/login.html` or `/auth/register.html` links to `/app/dashboard.html`. Tightened CSP in `vercel.json`, `_headers`, `netlify.toml` to drop the Clerk hosts. Dropped `pyjwt` from `requirements.txt`.
- Integrated multi-color Tradexa logo (candlesticks + blue arrow + white wordmark) site-wide via `tradexa-logo-full.png` / `tradexa-logo-icon.png` / favicon set.
