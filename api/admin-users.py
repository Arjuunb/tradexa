"""GET /api/admin-users — list users (service role only)."""
from http.server import BaseHTTPRequestHandler
import json
import urllib.request
import urllib.error
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))
from _shared import json_response, json_error, set_cors, verify_supabase_jwt, is_admin, ADMIN_EMAIL

SUPABASE_URL         = os.environ.get('SUPABASE_URL', '')
SUPABASE_SERVICE_KEY = os.environ.get('SUPABASE_SERVICE_KEY', '')


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        set_cors(self)
        self.end_headers()

    def do_GET(self):
        if not SUPABASE_SERVICE_KEY:
            json_error(self, 503, 'SUPABASE_SERVICE_KEY not configured.')
            return

        payload = verify_supabase_jwt(self.headers)
        if payload is None:
            json_error(self, 401, 'Authentication required.')
            return

        if not is_admin(payload):
            json_error(self, 403, 'Admin access required.')
            return

        try:
            req = urllib.request.Request(
                f'{SUPABASE_URL}/auth/v1/admin/users?page=1&per_page=200',
                headers={
                    'Authorization': f'Bearer {SUPABASE_SERVICE_KEY}',
                    'apikey': SUPABASE_SERVICE_KEY,
                },
                method='GET',
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = json.loads(resp.read().decode('utf-8'))

            # Supabase returns { users: [...] } — normalize to flat list
            users = raw.get('users', raw) if isinstance(raw, dict) else raw

            normalized = []
            for u in users:
                meta = u.get('user_metadata') or {}
                normalized.append({
                    'id':         u.get('id'),
                    'email':      u.get('email', ''),
                    'role':       'owner' if (u.get('email','').lower() == ADMIN_EMAIL) else 'user',
                    'plan':       'elite' if (u.get('email','').lower() == ADMIN_EMAIL) else 'free',
                    'created_at': u.get('created_at', ''),
                    'last_sign_in': u.get('last_sign_in_at', ''),
                    'confirmed':  bool(u.get('email_confirmed_at')),
                    'provider':   (u.get('app_metadata') or {}).get('provider', 'email'),
                    'name':       meta.get('full_name') or meta.get('name') or '',
                })

            json_response(self, {
                'users': normalized,
                'total': len(normalized),
                'premium': sum(1 for u in normalized if u['plan'] != 'free'),
                'free': sum(1 for u in normalized if u['plan'] == 'free'),
            })

        except urllib.error.HTTPError as e:
            body = e.read().decode('utf-8') if e.fp else ''
            json_error(self, 502, f'Supabase error {e.code}: {body[:200]}')
        except Exception as e:
            json_error(self, 502, f'Could not fetch users: {str(e)}')

    def log_message(self, *_):
        pass
