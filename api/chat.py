"""POST /api/chat — Trade Bot chat via Gemini. ?stream=1 for SSE."""
from http.server import BaseHTTPRequestHandler
import json
import urllib.request
import urllib.error
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shared import (
    GEMINI_API_KEY, GEMINI_URL, GEMINI_STREAM_URL,
    json_response, json_error, read_json_body, auth_or_401, set_cors,
)

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

FALLBACK_MSG = (
    "Trade Bot is almost ready — a Gemini API key needs to be configured "
    "to activate full AI responses.\n\nIn the meantime, log some trades in the Journal."
)


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        set_cors(self)
        self.end_headers()

    def do_POST(self):
        if auth_or_401(self) is None:
            return
        data = read_json_body(self)
        if not data:
            json_error(self, 400, 'Invalid request body')
            return

        messages = data.get('messages', [])
        trade_context = data.get('tradeContext', None)
        if not messages:
            json_error(self, 400, 'No messages provided')
            return

        want_stream = '?stream=1' in self.path or '&stream=1' in self.path

        if not GEMINI_API_KEY:
            if want_stream:
                self._send_sse_fallback(FALLBACK_MSG)
            else:
                json_response(self, {'reply': FALLBACK_MSG})
            return

        system = TRADEBOT_SYSTEM
        if trade_context and trade_context.strip() and 'NO_TRADES' not in trade_context:
            system = (
                TRADEBOT_SYSTEM +
                "\n\nIMPORTANT: The following is real trade journal data for this specific user. "
                "Use it to give highly personalized, data-driven coaching.\n\n" + trade_context
            )

        contents = [
            {'role': 'user' if m.get('role') == 'user' else 'model',
             'parts': [{'text': m.get('content', '')}]}
            for m in messages
        ]
        payload = {
            'system_instruction': {'parts': [{'text': system}]},
            'contents': contents,
            'generationConfig': {'temperature': 0.7, 'maxOutputTokens': 700, 'topP': 0.95},
        }

        if want_stream:
            self._stream_chat(payload)
            return

        try:
            req = urllib.request.Request(
                f'{GEMINI_URL}?key={GEMINI_API_KEY}',
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json'},
                method='POST',
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode('utf-8'))
            text = result['candidates'][0]['content']['parts'][0]['text']
            json_response(self, {'reply': text})
        except urllib.error.HTTPError as e:
            if e.code == 429:
                json_error(self, 429, 'Trade Bot is busy — rate limit reached. Try again in a moment.')
            else:
                json_error(self, 502, 'AI service temporarily unavailable — please try again shortly')
        except Exception:
            json_error(self, 500, 'Something went wrong — please try again')

    def _send_sse_fallback(self, msg):
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('X-Accel-Buffering', 'no')
        set_cors(self)
        self.end_headers()
        self.wfile.write(b'data: ' + json.dumps({'chunk': msg}).encode() + b'\n\n')
        self.wfile.write(b'data: ' + json.dumps({'done': True}).encode() + b'\n\n')
        self.wfile.flush()

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
            set_cors(self)
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
            try:
                self.wfile.write(b'data: ' + json.dumps({'error': 'stream_failed'}).encode() + b'\n\n')
            except Exception:
                pass

    def log_message(self, *_):
        pass
