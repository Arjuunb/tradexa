"""GET /api/public-config — returns Supabase URL + anon key (both public)."""
from http.server import BaseHTTPRequestHandler
import json
import os


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()

    def do_GET(self):
        supabase_url  = os.environ.get('SUPABASE_URL', '')
        supabase_anon = os.environ.get('SUPABASE_ANON_KEY', '')
        body = json.dumps({
            'supabaseUrl':     supabase_url,
            'supabaseAnonKey': supabase_anon,
            'configured':      bool(supabase_url and supabase_anon),
        }).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'public, max-age=300')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        pass
