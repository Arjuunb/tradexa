/**
 * assets/supabase-auth.js
 * Loads @supabase/supabase-js@2, fetches /api/public-config with defensive
 * Content-Type checking, and exposes window.TxAuth.
 * On any /app/* path it auto-runs an auth guard.
 */
(function () {
  'use strict';

  /** OAuth providers shown as buttons on auth pages. */
  const PROVIDERS = ['google', 'github', 'discord'];

  let _client = null;
  let _readyResolve, _readyReject;
  const _ready = new Promise(function (res, rej) {
    _readyResolve = res;
    _readyReject  = rej;
  });

  // ─── fetch /api/public-config with defensive JSON handling ───────────────

  async function _fetchConfig() {
    try {
      const res = await fetch('/api/public-config');

      // Guard 1: HTTP error (4xx / 5xx)
      if (!res.ok) {
        console.error('[TxAuth] /api/public-config returned HTTP ' + res.status +
          ' — endpoint may be missing or misconfigured.');
        return null;
      }

      // Guard 2: wrong Content-Type (e.g. HTML fallback from Vercel/Netlify)
      const ct = res.headers.get('content-type') || '';
      if (!ct.includes('application/json')) {
        console.error(
          '[TxAuth] /api/public-config returned non-JSON Content-Type: "' + ct + '". ' +
          'The server is likely returning an HTML error page instead of JSON. ' +
          'Check that api/public-config.py is deployed and the route is correct.'
        );
        return null;
      }

      // Guard 3: parse failure (malformed JSON)
      let data;
      try {
        data = await res.json();
      } catch (parseErr) {
        console.error('[TxAuth] /api/public-config JSON parse failed:', parseErr.message);
        return null;
      }

      return data;
    } catch (networkErr) {
      console.error('[TxAuth] /api/public-config network error:', networkErr.message);
      return null;
    }
  }

  // ─── load Supabase SDK from jsDelivr ─────────────────────────────────────

  function _loadSDK() {
    return new Promise(function (resolve, reject) {
      if (window.supabase) { resolve(); return; }
      var s = document.createElement('script');
      s.src = 'https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/dist/umd/supabase.min.js';
      s.onload  = resolve;
      s.onerror = function () { reject(new Error('Failed to load @supabase/supabase-js from jsDelivr')); };
      document.head.appendChild(s);
    });
  }

  // ─── initialise ──────────────────────────────────────────────────────────

  async function _init() {
    try {
      await _loadSDK();
    } catch (sdkErr) {
      console.error('[TxAuth]', sdkErr.message);
      _readyReject(sdkErr);
      return;
    }

    const cfg = await _fetchConfig();

    if (!cfg) {
      const err = new Error('Could not load Supabase configuration from /api/public-config.');
      _readyReject(err);
      return;
    }

    if (!cfg.supabaseUrl || !cfg.supabaseAnonKey) {
      const msg = cfg.configured === false
        ? 'SUPABASE_URL and SUPABASE_ANON_KEY are not set on the server. ' +
          'Add them to your Vercel/Netlify environment variables.'
        : '/api/public-config returned an unexpected response shape.';
      console.error('[TxAuth]', msg);
      _readyReject(new Error(msg));
      return;
    }

    _client = window.supabase.createClient(cfg.supabaseUrl, cfg.supabaseAnonKey);
    _readyResolve(_client);
    document.dispatchEvent(new CustomEvent('tx-auth-ready'));

    if (location.pathname.startsWith('/app/')) {
      _runAppGuard();
    }
  }

  // ─── /app/* guard ────────────────────────────────────────────────────────

  function _runAppGuard() {
    document.body.style.opacity = '0';
    _ready
      .then(async function () {
        const { data: { session } } = await _client.auth.getSession();
        if (session) {
          document.body.style.opacity = '';
        } else {
          const redir = encodeURIComponent(location.href);
          location.replace('/auth/login.html?redirectTo=' + redir);
        }
      })
      .catch(function () {
        location.replace('/auth/login.html');
      });
  }

  // ─── public API ──────────────────────────────────────────────────────────

  const TxAuth = {
    PROVIDERS: PROVIDERS,
    ready: _ready,

    async getUser() {
      await _ready;
      const { data: { user } } = await _client.auth.getUser();
      return user;
    },

    async getToken() {
      await _ready;
      const { data: { session } } = await _client.auth.getSession();
      return session ? session.access_token : null;
    },

    async signInWithPassword(email, password) {
      await _ready;
      return _client.auth.signInWithPassword({ email, password });
    },

    async signInWithOAuth(provider) {
      await _ready;
      const redirectTo = location.origin + '/auth/callback.html';
      return _client.auth.signInWithOAuth({ provider, options: { redirectTo } });
    },

    async signOut() {
      await _ready;
      await _client.auth.signOut();
      location.replace('/');
    },

    userKey(user) {
      return user ? user.id : null;
    },

    async resetPassword(email) {
      await _ready;
      const redirectTo = location.origin + '/auth/reset.html';
      return _client.auth.resetPasswordForEmail(email, { redirectTo });
    },

    /**
     * 3-step glass overlay (~2.6 s) then redirect.
     * Respects prefers-reduced-motion.
     */
    runLoginTransition({ user, redirectTo }) {
      const dest = redirectTo || '/app/dashboard.html';

      if (window.matchMedia('(prefers-reduced-motion:reduce)').matches) {
        location.replace(dest);
        return;
      }

      const overlay = document.createElement('div');
      overlay.style.cssText =
        'position:fixed;inset:0;z-index:9999;background:#0d0f12;' +
        'display:flex;align-items:center;justify-content:center;' +
        'flex-direction:column;opacity:1;transition:opacity .4s ease;' +
        'font-family:Inter,sans-serif;';
      overlay.innerHTML =
        '<div style="text-align:center">' +
          '<div id="_txTrIcon" style="font-size:48px;margin-bottom:12px">&#10003;</div>' +
          '<div id="_txTrMsg" style="color:#fff;font-size:18px;font-weight:700">Login successful</div>' +
          '<div id="_txTrSub" style="color:#A1A1AA;font-size:13px;margin-top:6px">Securing your session…</div>' +
        '</div>';
      document.body.appendChild(overlay);

      const icon = overlay.querySelector('#_txTrIcon');
      const msg  = overlay.querySelector('#_txTrMsg');
      const sub  = overlay.querySelector('#_txTrSub');
      const name = (user && user.email) ? user.email.split('@')[0] : 'Trader';

      setTimeout(function () {
        icon.textContent = '🔒';
        msg.textContent  = 'Session secured';
        sub.textContent  = 'Loading your dashboard…';
      }, 900);

      setTimeout(function () {
        icon.textContent = '👋';
        msg.textContent  = 'Welcome, ' + name + '!';
        sub.textContent  = 'Redirecting…';
      }, 1800);

      setTimeout(function () {
        overlay.style.opacity = '0';
        setTimeout(function () { location.replace(dest); }, 420);
      }, 2600);
    },
  };

  window.TxAuth = TxAuth;
  _init();
})();
