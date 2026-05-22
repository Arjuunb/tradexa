"""GET /api/public-config -- returns Supabase public credentials.

This endpoint is intentionally unauthenticated. It is called before login
to initialise the Supabase client on the frontend and MUST always return
JSON. It MUST NOT require an Authorization header. It MUST NOT return any
private keys (service role, JWT secret, Gemini key, etc.).
"""
from http.server import BaseHTTPRequestHandler
import json
import os

_CORS_HEADERS = [
    ('Access-Control-Allow-Origin',  '*'),
    ('Access-Control-Allow-Methods', 'GET, OPTIONS'),
    ('Access-Control-Allow-Headers', 'Content-Type, Authorization'),
]


class handler(BaseHTTPRequestHandler):

    def do_OPTIONS(self):
        self.send_response(200)
        for k, v in _CORS_HEADERS:
            self.send_header(k, v)
        self.end_headers()

    def do_GET(self):
        # Every code path in this method must return JSON.
        # A bare exception must never bubble up to Vercel's HTML error page.
        try:
            self._respond()
        except Exception:
            self._write_json({'error': 'Internal server error.', 'configured': False}, 500)

    # ------------------------------------------------------------------ helpers

    def _respond(self):
        # Read env vars at request time -- Vercel Python may not have them at
        # module-load time (cold start timing).
        url = os.environ.get('SUPABASE_URL', '').strip()

        # Accept either naming convention so the endpoint works across
        # Vercel, Netlify, and Next.js deployments.
        anon = (
            os.environ.get('SUPABASE_ANON_KEY', '').strip()
            or os.environ.get('NEXT_PUBLIC_SUPABASE_ANON_KEY', '').strip()
        )

        if not url or not anon:
            missing = []
            if not url:
                missing.append('SUPABASE_URL')
            if not anon:
                missing.append('SUPABASE_ANON_KEY')
            self._write_json(
                {
                    'error':         'Server configuration incomplete. Missing: ' + ', '.join(missing),
                    'configured':    False,
                    'supabaseUrl':   url,       # safe to echo even when empty
                    'supabaseAnonKey': '',
                },
                503,
                cache=0,
            )
            return

        self._write_json(
            {
                'supabaseUrl':      url,
                'supabaseAnonKey':  anon,
                'configured':       True,
            },
            200,
            cache=300,
        )

    def _write_json(self, data, status=200, cache=0):
        body = json.dumps(data).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', f'public, max-age={cache}' if cache else 'no-store')
        for k, v in _CORS_HEADERS:
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        pass
