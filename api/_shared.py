"""Shared utilities for Vercel Python API handlers."""
import os
import json
import base64
import urllib.request

GEMINI_MODEL      = 'gemini-2.5-flash'
GEMINI_BASE       = f'https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}'
GEMINI_URL        = f'{GEMINI_BASE}:generateContent'
GEMINI_STREAM_URL = f'{GEMINI_BASE}:streamGenerateContent'


def _env(key, default=''):
    """Read env var at request time — avoids Vercel module-load timing issues."""
    return os.environ.get(key, default)


def _b64url_decode(s):
    s += '=' * (-len(s) % 4)
    return base64.urlsafe_b64decode(s)


def verify_supabase_jwt(headers):
    """Verify token by calling Supabase /auth/v1/user.
    Works with all signing algorithms (HS256, ECC P-256, etc).
    Returns payload dict on success, None on failure."""
    auth = headers.get('Authorization') or headers.get('authorization') or ''
    if not auth.startswith('Bearer '):
        return None
    token = auth[7:].strip()
    supabase_url = _env('SUPABASE_URL')
    supabase_anon_key = _env('SUPABASE_ANON_KEY')
    if not supabase_url or not supabase_anon_key:
        return None
    try:
        req = urllib.request.Request(
            f'{supabase_url}/auth/v1/user',
            headers={
                'Authorization': f'Bearer {token}',
                'apikey': supabase_anon_key,
            },
            method='GET',
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            user = json.loads(resp.read().decode('utf-8'))
        if not user.get('id'):
            return None
        return {
            'sub':   user.get('id'),
            'email': user.get('email', ''),
            'role':  user.get('role', 'authenticated'),
            'aud':   'authenticated',
        }
    except Exception:
        return None


def set_cors(h):
    h.send_header('Access-Control-Allow-Origin', '*')
    h.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
    h.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')


def json_response(h, data, status=200):
    body = json.dumps(data).encode('utf-8')
    h.send_response(status)
    h.send_header('Content-Type', 'application/json')
    h.send_header('Content-Length', str(len(body)))
    set_cors(h)
    h.end_headers()
    h.wfile.write(body)


def json_error(h, status, message):
    json_response(h, {'error': message}, status)


def read_json_body(h):
    try:
        length = int(h.headers.get('Content-Length', 0))
        return json.loads(h.rfile.read(length))
    except Exception:
        return None


def is_admin(payload):
    """Returns True if the JWT payload belongs to the admin email."""
    admin_email = _env('ADMIN_EMAIL', '').lower().strip()
    if not admin_email or not payload:
        return False
    email = (payload.get('email') or '').lower().strip()
    return email == admin_email


def auth_or_401(h):
    """Returns JWT payload if valid, writes 401 and returns None otherwise."""
    supabase_url = _env('SUPABASE_URL')
    supabase_anon_key = _env('SUPABASE_ANON_KEY')
    if not supabase_url or not supabase_anon_key:
        json_error(h, 503, 'SUPABASE_URL or SUPABASE_ANON_KEY not set on the server.')
        return None
    auth = h.headers.get('Authorization') or h.headers.get('authorization') or ''
    if not auth.startswith('Bearer '):
        json_error(h, 401, 'No auth token sent. Make sure you are logged in.')
        return None
    payload = verify_supabase_jwt(h.headers)
    if payload is None:
        json_error(h, 401, 'Token invalid or expired. Please sign out and sign back in.')
        return None
    return payload
