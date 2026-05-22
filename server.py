#!/usr/bin/env python3
"""
Tradexa local dev server.

Endpoints:
  GET  /api/public-config  — returns Supabase URL + anon key (both public)
  POST /api/chat           — Trade Bot chat (Gemini). ?stream=1 → SSE stream
  POST /api/weekly-review  — Real Gemini-generated weekly review (JSON)
  POST /api/insights       — Shared "AI insights" panel data (JSON mode)

All POST endpoints require a valid Supabase JWT in `Authorization: Bearer ...`
when SUPABASE_JWT_SECRET is set. /app/* pages are gated client-side by
assets/supabase-auth.js (and re-checked server-side at the API layer).
"""
import http.server
import socketserver
import os
import json
import time
import hmac
import hashlib
import base64
import urllib.request
import urllib.error

PORT = 5000
DIRECTORY = os.path.dirname(os.path.abspath(__file__))

GEMINI_API_KEY      = os.environ.get('GEMINI_API_KEY', '')
GEMINI_MODEL        = 'gemini-2.5-flash'
GEMINI_BASE         = f'https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}'
GEMINI_URL          = f'{GEMINI_BASE}:generateContent'
GEMINI_STREAM_URL   = f'{GEMINI_BASE}:streamGenerateContent'

SUPABASE_URL         = os.environ.get('SUPABASE_URL', '')
SUPABASE_ANON_KEY    = os.environ.get('SUPABASE_ANON_KEY', '')
SUPABASE_JWT_SECRET  = os.environ.get('SUPABASE_JWT_SECRET', '')

ALLOWED_ORIGINS      = [o.strip() for o in os.environ.get('ALLOWED_ORIGINS', 'http://localhost:5000').split(',') if o.strip()]


# ──────────────────────────── Supabase JWT verify ────────────────────────────

def _b64url_decode(s):
    s += '=' * (-len(s) % 4)
    return base64.urlsafe_b64decode(s)


def verify_supabase_jwt(headers):
    """Verify HS256 Supabase JWT from Authorization: Bearer header.
    Returns payload dict on success, None on any failure / missing config."""
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
        if not hmac.compare_digest(expected, actual): return None
        if json.loads(_b64url_decode(h_b64)).get('alg') != 'HS256': return None
        payload = json.loads(_b64url_decode(p_b64))
        if payload.get('exp', 0) < (time.time() - 5): return None
        if payload.get('aud') and payload.get('aud') != 'authenticated': return None
        return payload
    except Exception:
        return None


# ──────────────────────────── Prompts ────────────────────────────

TRADEBOT_SYSTEM = (
    "You are Trade Bot, the AI assistant built into Tradexa — a professional trading journal "
    "and performance analytics platform. You help traders understand their journal data, "
    "analyze performance, identify behavioral mistakes, and improve consistency.\n\n"
    "CAPABILITIES:\n"
    "- Explain trading metrics: Sharpe ratio, R:R, max drawdown, expectancy, win rate, profit factor\n"
    "- Analyze behavioral patterns: FOMO entries, revenge trading, overtrading, emotional decisions\n"
    "- Review recent trades and suggest discipline improvements\n"
    "- Help users navigate the Tradexa platform\n"
    "- Generate weekly performance review summaries and action steps\n"
    "- Identify repeated mistakes and how to fix them\n\n"
    "RULES:\n"
    "- Never provide live trade signals or specific buy/sell recommendations\n"
    "- Never guarantee profits or predict market direction\n"
    "- Always frame advice as educational analysis, not financial advice\n"
    "- Be concise, direct, and actionable — like a real trading coach\n"
    "- If no trade data is provided in the conversation, encourage the user to log trades first\n"
    "- Use bullet points for clarity when listing multiple insights\n"
    "- Keep responses under 300 words unless a detailed analysis is explicitly requested\n\n"
    "TONE: Professional, calm, honest. Like a coach who respects the trader's intelligence."
)

WEEKLY_REVIEW_SYSTEM = (
    "You are Tradexa's weekly performance reviewer. You analyze a trader's week and produce "
    "a brutally honest, specific, structured review. Reference real numbers from the data. "
    "Wins must cite actual trades or behaviors. Mistakes must reference specific trades or patterns. "
    "Focus items must be concrete actions for next week, not platitudes. "
    "If data is sparse, say so honestly instead of inventing detail."
)

WEEKLY_REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "title":   {"type": "string"},
        "score":   {"type": "integer"},
        "summary": {"type": "string"},
        "wins": {
            "type": "array",
            "items": {"type":"object","properties":{"title":{"type":"string"},"detail":{"type":"string"}},"required":["title","detail"]}
        },
        "mistakes": {
            "type": "array",
            "items": {"type":"object","properties":{"title":{"type":"string"},"detail":{"type":"string"},"severity":{"type":"string","enum":["red","yellow"]}},"required":["title","detail","severity"]}
        },
        "focus": {
            "type": "array",
            "items": {"type":"object","properties":{"title":{"type":"string"},"detail":{"type":"string"}},"required":["title","detail"]}
        }
    },
    "required": ["title","score","summary","wins","mistakes","focus"]
}

INSIGHTS_SYSTEM = (
    "You are Tradexa's insights engine. Given a trader's journal data, return a tight, "
    "specific insight panel for the requested scope. Cite real numbers. Be direct. "
    "Never invent metrics that aren't in the data."
)

INSIGHTS_SCHEMA = {
    "type": "object",
    "properties": {
        "headline":     {"type": "string"},
        "strength":     {"type": "string"},
        "weakness":     {"type": "string"},
        "suggestion":   {"type": "string"},
        "focus_metric": {"type": "string"}
    },
    "required": ["headline","strength","weakness","suggestion","focus_metric"]
}


# ──────────────────────────── Gemini helper ────────────────────────────

def _gemini_payload(system_prompt, user_text, *, json_mode=False, schema=None,
                    temperature=0.4, max_tokens=900):
    cfg = {'temperature': temperature, 'maxOutputTokens': max_tokens, 'topP': 0.95}
    if json_mode:
        cfg['responseMimeType'] = 'application/json'
        if schema:
            cfg['responseSchema'] = schema
    return {
        'system_instruction': {'parts': [{'text': system_prompt}]},
        'contents': [{'role': 'user', 'parts': [{'text': user_text}]}],
        'generationConfig': cfg,
    }


def _gemini_call(payload, timeout=30):
    req = urllib.request.Request(
        f'{GEMINI_URL}?key={GEMINI_API_KEY}',
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        result = json.loads(resp.read().decode('utf-8'))
    candidates = result.get('candidates', [])
    if not candidates:
        raise ValueError('No candidates returned from Gemini')
    return candidates[0]['content']['parts'][0]['text']


# ──────────────────────────── HTTP handler ────────────────────────────

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def log_message(self, format, *args):
        print(f"{self.address_string()} - {format % args}")

    def do_OPTIONS(self):
        if not self._is_origin_allowed():
            self.send_response(403)
            self.end_headers()
            return
        self.send_response(200)
        self._set_cors()
        self.end_headers()

    def do_GET(self):
        if not self._is_origin_allowed():
            self.send_response(403)
            self.end_headers()
            return
        path = self.path.split('?')[0]
        if path == '/api/public-config':
            self._handle_public_config(); return
        return super().do_GET()

    def do_POST(self):
        if not self._is_origin_allowed():
            self.send_response(403)
            self.end_headers()
            return
        path = self.path.split('?')[0]
        if path == '/api/chat':
            self._handle_chat()
        elif path == '/api/weekly-review':
            self._handle_weekly_review()
        elif path == '/api/insights':
            self._handle_insights()
        else:
            self.send_response(404)
            self._set_cors()
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': 'Not found'}).encode())

    def _is_origin_allowed(self):
        origin = self.headers.get('Origin')
        if not origin:
            return True # Allow direct requests (e.g., from server itself or curl without origin)
        return origin in ALLOWED_ORIGINS

    def _set_cors(self):
        origin = self.headers.get('Origin')
        if origin and origin in ALLOWED_ORIGINS:
            self.send_header('Access-Control-Allow-Origin', origin)
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')

    def _read_json_body(self):
        try:
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            return json.loads(body)
        except Exception:
            return None

    def _gemini_or_503(self):
        if not GEMINI_API_KEY:
            self._json_error(503, 'AI is not configured on this server.')
            return False
        return True

    def _auth_or_401(self):
        """Returns the JWT payload if valid, else writes 401 and returns None."""
        payload = verify_supabase_jwt(self.headers)
        if payload is None:
            self._json_error(401, 'Authentication required.')
            return None
        return payload

    # ──────────────────── /api/public-config ────────────────────
    def _handle_public_config(self):
        body = json.dumps({
            'supabaseUrl':     SUPABASE_URL,
            'supabaseAnonKey': SUPABASE_ANON_KEY,
            'configured':      bool(SUPABASE_URL and SUPABASE_ANON_KEY),
        }).encode('utf-8')
        self.send_response(200)
        self._set_cors()
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'public, max-age=300')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # ──────────────────── /api/chat ────────────────────
    def _handle_chat(self):
        if self._auth_or_401() is None: return
        data = self._read_json_body()
        if data is None:
            self._json_error(400, 'Invalid request body'); return

        messages      = data.get('messages', [])
        trade_context = data.get('tradeContext', None)
        if not messages:
            self._json_error(400, 'No messages provided'); return

        want_stream = '?stream=1' in self.path or '&stream=1' in self.path

        if not GEMINI_API_KEY:
            fallback_msg = (
                "Trade Bot is almost ready — a Gemini API key needs to be configured "
                "to activate full AI responses.\n\nIn the meantime, log some trades in the Journal."
            )
            if want_stream:
                self.send_response(200)
                self.send_header('Content-Type', 'text/event-stream')
                self.send_header('Cache-Control', 'no-cache')
                self.send_header('X-Accel-Buffering', 'no')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(b'data: ' + json.dumps({'chunk': fallback_msg}).encode() + b'\n\n')
                self.wfile.write(b'data: ' + json.dumps({'done': True}).encode() + b'\n\n')
                self.wfile.flush()
                return
            self._json_response({'reply': fallback_msg})
            return

        system_prompt = TRADEBOT_SYSTEM
        if trade_context and trade_context.strip() and 'NO_TRADES' not in trade_context:
            system_prompt = (
                TRADEBOT_SYSTEM +
                "\n\nIMPORTANT: The following is real trade journal data for this specific user. "
                "Use it to give highly personalized, data-driven coaching. "
                "Reference their actual numbers, setups, emotions, and patterns directly.\n\n" +
                trade_context
            )

        gemini_contents = [
            {'role': 'user' if m.get('role') == 'user' else 'model',
             'parts': [{'text': m.get('content', '')}]}
            for m in messages
        ]
        payload = {
            'system_instruction': {'parts': [{'text': system_prompt}]},
            'contents': gemini_contents,
            'generationConfig': {'temperature': 0.7, 'maxOutputTokens': 700, 'topP': 0.95},
        }

        if want_stream:
            self._stream_chat(payload)
            return

        try:
            reply_text = _gemini_call(payload)
            self._json_response({'reply': reply_text})
        except urllib.error.HTTPError as e:
            err_body = e.read().decode('utf-8') if e.fp else ''
            print(f'Gemini HTTP error {e.code}: {err_body}')
            if e.code == 429:
                self._json_error(429, 'Trade Bot is busy — rate limit reached. Try again in a moment.')
            else:
                self._json_error(502, 'AI service temporarily unavailable — please try again shortly')
        except Exception as e:
            print(f'Chat error: {e}')
            self._json_error(500, 'Something went wrong — please try again')

    def _stream_chat(self, payload):
        try:
            req = urllib.request.Request(
                f'{GEMINI_STREAM_URL}?alt=sse&key={GEMINI_API_KEY}',
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json'},
                method='POST',
            )
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('X-Accel-Buffering', 'no')
            self._set_cors()
            self.end_headers()

            with urllib.request.urlopen(req, timeout=60) as resp:
                for raw in resp:
                    line = raw.decode('utf-8', errors='ignore').strip()
                    if not line.startswith('data:'):
                        continue
                    body = line[5:].strip()
                    if not body:
                        continue
                    try:
                        obj = json.loads(body)
                    except Exception:
                        continue
                    cands = obj.get('candidates', [])
                    if not cands:
                        continue
                    parts = cands[0].get('content', {}).get('parts', [])
                    text = ''.join(p.get('text', '') for p in parts)
                    if text:
                        self.wfile.write(b'data: ' + json.dumps({'chunk': text}).encode() + b'\n\n')
                        self.wfile.flush()
            self.wfile.write(b'data: ' + json.dumps({'done': True}).encode() + b'\n\n')
            self.wfile.flush()
        except Exception as e:
            print(f'Stream error: {e}')
            try:
                self.wfile.write(b'data: ' + json.dumps({'error': 'stream_failed'}).encode() + b'\n\n')
            except Exception:
                pass

    # ──────────────────── /api/weekly-review ────────────────────
    def _handle_weekly_review(self):
        if self._auth_or_401() is None: return
        if not self._gemini_or_503(): return
        data = self._read_json_body()
        if data is None:
            self._json_error(400, 'Invalid request body'); return

        week_start = data.get('weekStart', '')
        week_end   = data.get('weekEnd', '')
        stats      = data.get('stats', {})
        trades     = data.get('trades', []) or []

        if not trades:
            self._json_error(400, 'No trades in the requested week'); return

        packet_lines = [
            f'WEEK: {week_start} → {week_end}',
            f'Trades: {len(trades)}',
            f'Win rate: {stats.get("winRate","?")}%',
            f'Net P&L: ${stats.get("totalPnl","?")}',
            f'Avg R:R: {stats.get("avgRR","?")}',
            f'Profit factor: {stats.get("profitFactor","?")}',
            f'Calm: {stats.get("calmCount",0)}, FOMO: {stats.get("fomoCount",0)}, '
            f'Revenge: {stats.get("revengeCount",0)}, Greedy: {stats.get("greedyCount",0)}',
            '',
            'TRADES THIS WEEK:'
        ]
        for t in trades[:40]:
            outcome = f'+${t.get("pnl",0)}' if (t.get('pnl') or 0) > 0 else f'${t.get("pnl",0)}'
            packet_lines.append(
                f'- {(t.get("date") or "")[:10]} {t.get("asset","?")} '
                f'{(t.get("direction") or "").upper()} | '
                f'setup: {",".join(t.get("setup") or [])} | '
                f'emotion: {",".join(t.get("emotion") or [])} | '
                f'{outcome} | R:R {t.get("rr",0)} | rating {t.get("rating",0)}/5 | '
                f'note: "{(t.get("notes") or "")[:120]}"'
            )
        packet = '\n'.join(packet_lines)

        user_text = (
            'Generate a structured weekly performance review for this trader. '
            'Cite specific trades, emotions, and numbers from the data. Be honest about both wins and mistakes.\n\n'
            + packet
        )
        payload = _gemini_payload(
            WEEKLY_REVIEW_SYSTEM, user_text,
            json_mode=True, schema=WEEKLY_REVIEW_SCHEMA,
            temperature=0.5, max_tokens=1400,
        )
        try:
            text = _gemini_call(payload, timeout=45)
            review = json.loads(text)
            review['weekStart'] = week_start
            review['weekEnd']   = week_end
            review['tradeCount']= len(trades)
            review['netPnl']    = stats.get('totalPnl', 0)
            self._json_response(review)
        except urllib.error.HTTPError as e:
            err_body = e.read().decode('utf-8') if e.fp else ''
            print(f'Weekly review Gemini error {e.code}: {err_body}')
            self._json_error(502, 'AI review service temporarily unavailable')
        except Exception as e:
            print(f'Weekly review error: {e}')
            self._json_error(500, 'Could not generate review — please try again')

    # ──────────────────── /api/insights ────────────────────
    def _handle_insights(self):
        if self._auth_or_401() is None: return
        if not self._gemini_or_503(): return
        data = self._read_json_body()
        if data is None:
            self._json_error(400, 'Invalid request body'); return

        scope         = (data.get('scope') or 'dashboard').strip()
        trade_context = (data.get('tradeContext') or '').strip()
        if not trade_context or 'NO_TRADES' in trade_context:
            self._json_response({
                'headline':     'Log a few trades to unlock insights',
                'strength':     'No trades yet — your insight engine activates after 5+ logged trades.',
                'weakness':     'Without data, AI can only give generic advice.',
                'suggestion':   'Open the Journal and log your most recent trade.',
                'focus_metric': 'Trades logged: 0',
                'empty':        True,
            })
            return

        scope_hint = {
            'dashboard': 'Focus on overall performance and the single biggest pattern.',
            'journal':   'Focus on recent trades and immediate behavioral patterns.',
            'analytics': 'Focus on setup/asset edges and statistical leaks.',
        }.get(scope, 'Give a balanced overview.')

        user_text = (
            f'Scope: {scope}. {scope_hint}\n\n'
            'Return a tight insight panel for this trader based on the journal data below.\n\n'
            + trade_context
        )
        payload = _gemini_payload(
            INSIGHTS_SYSTEM, user_text,
            json_mode=True, schema=INSIGHTS_SCHEMA,
            temperature=0.4, max_tokens=600,
        )
        try:
            text = _gemini_call(payload, timeout=25)
            self._json_response(json.loads(text))
        except urllib.error.HTTPError as e:
            err_body = e.read().decode('utf-8') if e.fp else ''
            print(f'Insights Gemini error {e.code}: {err_body}')
            self._json_error(502, 'AI insights service temporarily unavailable')
        except Exception as e:
            print(f'Insights error: {e}')
            self._json_error(500, 'Could not generate insights — please try again')

    # ──────────────────── helpers ────────────────────
    def _json_response(self, data, status=200):
        body = json.dumps(data).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self._set_cors()
        self.end_headers()
        self.wfile.write(body)

    def _json_error(self, status, message):
        self._json_response({'error': message}, status)


socketserver.TCPServer.allow_reuse_address = True

with socketserver.TCPServer(("0.0.0.0", PORT), Handler) as httpd:
    print(f"Serving at http://0.0.0.0:{PORT}")
    if GEMINI_API_KEY:
        print(f"Gemini API key loaded — {GEMINI_MODEL} active")
    else:
        print("WARN: GEMINI_API_KEY not set — AI endpoints will return fallback messages")
    if SUPABASE_URL and SUPABASE_ANON_KEY:
        print(f"Supabase configured — URL {SUPABASE_URL}")
    else:
        print("WARN: SUPABASE_URL / SUPABASE_ANON_KEY not set — auth will not work")
    if SUPABASE_JWT_SECRET:
        print("Supabase JWT verification: ACTIVE — /api/* endpoints fail-closed")
    else:
        print("WARN: SUPABASE_JWT_SECRET not set — /api/* endpoints will REJECT all requests as unauthorized")
    print("Endpoints: /api/public-config (GET), /api/chat (+ ?stream=1), /api/weekly-review, /api/insights")
    httpd.serve_forever()
