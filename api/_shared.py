"""Shared utilities for Vercel Python API handlers."""
import os
import json
import time
import hmac
import hashlib
import base64

SUPABASE_URL        = os.environ.get('SUPABASE_URL', '')
SUPABASE_ANON_KEY   = os.environ.get('SUPABASE_ANON_KEY', '')
SUPABASE_JWT_SECRET = os.environ.get('SUPABASE_JWT_SECRET', '')
GEMINI_API_KEY      = os.environ.get('GEMINI_API_KEY', '')
ADMIN_EMAIL         = os.environ.get('ADMIN_EMAIL', '').lower().strip()
GEMINI_MODEL        = 'gemini-2.5-flash'
GEMINI_BASE         = f'https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}'
GEMINI_URL          = f'{GEMINI_BASE}:generateContent'
GEMINI_STREAM_URL   = f'{GEMINI_BASE}:streamGenerateContent'


def _b64url_decode(s):
    s += '=' * (-len(s) % 4)
    return base64.urlsafe_b64decode(s)


def verify_supabase_jwt(headers):
    """Verify HS256 Supabase JWT. Returns payload on success, None on failure."""
    if not SUPABASE_JWT_SECRET:
        return None
    auth = headers.get('Authorization') or headers.get('authorization') or ''
    if not auth.startswith('Bearer '):
        return None
    token = auth[7:].strip()
    try:
        h_b64, p_b64, sig_b64 = token.split('.')
        msg = (h_b64 + '.' + p_b64).encode('ascii')
        expected = hmac.new(SUPABASE_JWT_SECRET.encode('utf-8'), msg, hashlib.sha256).digest()
        actual = _b64url_decode(sig_b64)
        if not hmac.compare_digest(expected, actual):
            return None
        if json.loads(_b64url_decode(h_b64)).get('alg') != 'HS256':
            return None
        payload = json.loads(_b64url_decode(p_b64))
        if payload.get('exp', 0) < (time.time() - 5):
            return None
        if payload.get('aud') and payload.get('aud') != 'authenticated':
            return None
        return payload
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
    if not ADMIN_EMAIL or not payload:
        return False
    email = (payload.get('email') or '').lower().strip()
    return email == ADMIN_EMAIL


def auth_or_401(h):
    """Returns JWT payload if valid, writes 401 and returns None otherwise."""
    if not SUPABASE_JWT_SECRET:
        json_error(h, 503, 'SUPABASE_JWT_SECRET is not set on the server. Add it to Vercel environment variables.')
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
