"""GET /api/admin-users — list users (service role only)."""
from http.server import BaseHTTPRequestHandler
import json
import urllib.request
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))
from _shared import json_response, json_error, set_cors, verify_supabase_jwt

SUPABASE_URL         = os.environ.get('SUPABASE_URL', '')
SUPABASE_SERVICE_KEY = os.environ.get('SUPABASE_SERVICE_KEY', '')


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        set_cors(self)
        self.end_headers()

    def do_GET(self):
        if not SUPABASE_SERVICE_KEY:
            json_error(self, 503, 'Admin endpoint not configured.')
            return
        payload = verify_supabase_jwt(self.headers)
        if payload is None:
            json_error(self, 401, 'Authentication required.')
            return
        try:
            req = urllib.request.Request(
                f'{SUPABASE_URL}/auth/v1/admin/users?page=1&per_page=50',
                headers={
                    'Authorization': f'Bearer {SUPABASE_SERVICE_KEY}',
                    'apikey': SUPABASE_SERVICE_KEY,
                },
                method='GET',
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode('utf-8'))
            json_response(self, data)
        except Exception as e:
            json_error(self, 502, 'Could not fetch users')

    def log_message(self, *_):
        pass
