# Tradexa

Premium dark trading-journal SaaS. Vanilla HTML / CSS / JS frontend with a tiny
Python serverless API layer (Gemini 2.5 Flash for AI, Supabase for auth).
Stdlib-only Python — no `pip install` needed for local dev.

**Brand:** background `#0d0f12`, accent gold `#FFB732`.

---

## 1. Quick start (local)

```bash
cp .env.example .env        # then fill in the values
python3 server.py           # → http://localhost:5000
```

The dev server handles both static files and the `/api/*` endpoints.
For full architecture, endpoint, and skill notes see [`replit.md`](replit.md).

---

## 2. Required environment variables

| Variable                 | Required for                             | Where to get it                                                |
| ------------------------ | ---------------------------------------- | -------------------------------------------------------------- |
| `GEMINI_API_KEY`         | Trade Bot, AI Coach, Daily Digest, Weekly Review | https://aistudio.google.com/app/apikey                  |
| `SUPABASE_URL`           | Auth (login / signup / protected pages)  | Supabase dashboard → Settings → API                            |
| `SUPABASE_ANON_KEY`      | Auth (browser-side client)               | Supabase dashboard → Settings → API                            |
| `SUPABASE_JWT_SECRET`    | Server-side token verification           | Supabase dashboard → Settings → API → JWT Settings             |

All AI endpoints (`/api/chat`, `/api/insights`, `/api/weekly-review`) **fail
closed with 401** if the JWT secret is unset or the request has no valid token.

---

## 3. One-time Supabase setup

1. **Authentication → URL Configuration**
   - *Site URL:* your deployed domain (e.g. `https://your-domain.com`)
   - *Redirect URLs* allow-list (add every URL you'll auth from):
     - `https://your-domain.com/auth/callback.html`
     - `https://your-domain.com/auth/reset.html`
     - `http://localhost:5000/auth/callback.html` (for dev)
     - `http://localhost:5000/auth/reset.html`
2. **Authentication → Providers** — enable each provider you want shown:
   - **Email** — on by default. Optionally turn off "Confirm email".
   - **Google / GitHub / Discord** — paste OAuth client id + secret from each
     platform's developer console. Each platform's OAuth callback URL must be
     `https://<your-project>.supabase.co/auth/v1/callback`.
3. To remove a provider's button from the login UI, edit
   `assets/supabase-auth.js` → `var PROVIDERS = [...]`.

> **Note:** Web3 wallet login is intentionally **not** wired — Supabase has no
> native Web3 provider. Adding it would require a custom SIWE → JWT-minting
> backend.

---

## 4. Deploy to Vercel

`vercel.json` is pre-configured (Python serverless functions + CSP headers +
asset cache).

```bash
vercel deploy --prod
```

In the Vercel dashboard, set all four env vars from §2 (Project → Settings →
Environment Variables). Then re-deploy.

---

## 5. Deploy to Hostinger / any static host (no Node, no Python)

The frontend works as static files. The AI endpoints under `/api/*` won't work
on a pure-static host — they need a Python runtime. Two options:

**Option A — static-only (no AI features):**
Upload everything **except** the `api/` folder and `server.py`. The marketing
site, auth pages, and the in-app pages (dashboard, journal, analytics, etc.)
all work without the API. Trade Bot / AI Coach / Daily Digest / Weekly Review
will show graceful error messages.

**Option B — static frontend + serverless API on Vercel:**
Host the static files on Hostinger and deploy *only* the `api/` folder to a
free Vercel project. Update the API base URL (currently relative `/api/…`) in
`assets/insights.js`, `assets/tradebot.js`, `app/ai-coach.html`,
`app/daily-digest.html`, `app/weekly-reviews.html` to point at the Vercel URL,
then re-upload the static bundle.

For SPA-like clean URLs on Hostinger (Apache), the `_redirects` and
`netlify.toml` rules give you the patterns to translate into `.htaccess`.

---

## 6. Folder structure

```
server.py                  # local dev server (handles /api/* + JWT verify)
api/                       # Vercel-compatible Python serverless handlers
  _shared.py               # Gemini helpers + Supabase JWT verifier
  chat.py                  # POST  /api/chat            (Bearer JWT required)
  insights.py              # POST  /api/insights        (Bearer JWT required)
  weekly-review.py         # POST  /api/weekly-review   (Bearer JWT required)
  public-config.py         # GET   /api/public-config   (returns Supabase URL + anon)
auth/                      # login.html / register.html / callback.html / reset.html
app/                       # 19 protected app pages (all guarded client-side)
assets/                    # supabase-auth.js, nav.js, app-sidebar.js, tradebot.js,
                           #  insights.js, capital-tracker.js, brand/, etc.
index.html                 # marketing landing
product/ solutions/ problems/ resources/ tools/ legal/ company/ pricing/
vercel.json _headers netlify.toml _redirects   # hosting configs
sitemap.xml robots.txt site.webmanifest
.env.example               # copy → .env, then fill in
requirements.txt           # empty — stdlib only
```

---

## 7. Security

- All secrets live in environment variables — none are hardcoded.
- The Supabase **anon key** is intentionally public (gated by Row-Level
  Security on the data side); the **JWT secret** is server-side only.
- The `/app/*` client guard (`assets/supabase-auth.js`) is paired with a
  server-side fail-closed JWT check so neither side alone is the only line of
  defence.
- CSP headers in `vercel.json` and `_headers` lock script/style/connect/frame
  sources to only what's actually used.

---

## 8. SEO

- Meta + OpenGraph + Twitter Card tags are present on every public page.
- `sitemap.xml` and `robots.txt` ship at the root.
- The `/app/*`, `/auth/*`, `/api/*`, `/admin/*` paths are disallowed in robots.

---

## 9. Performance

- Pages have a global page-transition curtain in `assets/app-sidebar.js` /
  `assets/nav.js` — no white flash between routes.
- Hover-prefetch pre-warms the next page on link hover.
- Static assets are cached with `Cache-Control: public, max-age=31536000,
  immutable` (configured in `vercel.json` / `_headers`).
- Auth check uses an inline `<style>html.tx-auth-pending body{visibility:hidden}</style>`
  guard so protected pages never flash content before the redirect.

---

## 10. Where to look if something breaks

| Symptom                                           | Look at                                              |
| ------------------------------------------------- | ---------------------------------------------------- |
| Login page hangs / "Auth service unavailable"     | `/api/public-config` response, env vars              |
| Google/GitHub/Discord button errors immediately   | Provider not enabled in Supabase dashboard           |
| `/app/*` infinite-redirects to `/auth/login.html` | Browser console — usually a missing Supabase env var |
| AI endpoints return 401                           | `SUPABASE_JWT_SECRET` not set, or stale browser session |
| Trade Bot returns generic fallback                | `GEMINI_API_KEY` not set                             |
