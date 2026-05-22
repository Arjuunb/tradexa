"""POST /api/insights — AI insights panel via Gemini (JSON mode)."""
from http.server import BaseHTTPRequestHandler
import json
import urllib.request
import urllib.error
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shared import (
    GEMINI_URL,
    json_response, json_error, read_json_body, auth_or_401, set_cors, _env,
)

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
        "focus_metric": {"type": "string"},
    },
    "required": ["headline", "strength", "weakness", "suggestion", "focus_metric"],
}


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        set_cors(self)
        self.end_headers()

    def do_POST(self):
        if auth_or_401(self) is None:
            return
        if not _env('GEMINI_API_KEY'):
            json_error(self, 503, 'AI is not configured on this server.')
            return
        data = read_json_body(self)
        if not data:
            json_error(self, 400, 'Invalid request body')
            return

        scope         = (data.get('scope') or 'dashboard').strip()
        trade_context = (data.get('tradeContext') or '').strip()

        if not trade_context or 'NO_TRADES' in trade_context:
            json_response(self, {
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
        payload = {
            'system_instruction': {'parts': [{'text': INSIGHTS_SYSTEM}]},
            'contents': [{'role': 'user', 'parts': [{'text': user_text}]}],
            'generationConfig': {
                'temperature': 0.4, 'maxOutputTokens': 600, 'topP': 0.95,
                'responseMimeType': 'application/json',
                'responseSchema': INSIGHTS_SCHEMA,
            },
        }

        try:
            req = urllib.request.Request(
                f'{GEMINI_URL}?key={_env('GEMINI_API_KEY')}',
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json'},
                method='POST',
            )
            with urllib.request.urlopen(req, timeout=25) as resp:
                result = json.loads(resp.read().decode('utf-8'))
            text = result['candidates'][0]['content']['parts'][0]['text']
            json_response(self, json.loads(text))
        except urllib.error.HTTPError as e:
            json_error(self, 502, 'AI insights service temporarily unavailable')
        except Exception:
            json_error(self, 500, 'Could not generate insights — please try again')

    def log_message(self, *_):
        pass
