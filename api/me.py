"""GET /api/me — returns current user info, role, and subscription status."""
from http.server import BaseHTTPRequestHandler
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shared import json_response, set_cors, auth_or_401, is_admin


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        set_cors(self)
        self.end_headers()

    def do_GET(self):
        payload = auth_or_401(self)
        if payload is None:
            return

        admin = is_admin(payload)
        email = (payload.get('email') or '').lower()

        json_response(self, {
            'id':    payload.get('sub'),
            'email': email,
            'role':  'owner' if admin else 'user',
            # Admins bypass all subscription gates
            'subscription': {
                'plan':       'elite' if admin else 'free',
                'status':     'active',
                'isAdmin':    admin,
                'trialActive': True,
                'limits': {
                    'trades':   999999 if admin else 50,
                    'ai':       True   if admin else False,
                    'analytics': True  if admin else False,
                    'export':   True   if admin else False,
                },
            },
        })

    def log_message(self, *_):
        pass
