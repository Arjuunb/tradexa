"""POST /api/weekly-review — Gemini-generated weekly performance review."""
from http.server import BaseHTTPRequestHandler
import json
import urllib.request
import urllib.error
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shared import (
    GEMINI_API_KEY, GEMINI_URL,
    json_response, json_error, read_json_body, auth_or_401, set_cors,
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
            "items": {"type": "object", "properties": {"title": {"type": "string"}, "detail": {"type": "string"}}, "required": ["title", "detail"]},
        },
        "mistakes": {
            "type": "array",
            "items": {"type": "object", "properties": {"title": {"type": "string"}, "detail": {"type": "string"}, "severity": {"type": "string", "enum": ["red", "yellow"]}}, "required": ["title", "detail", "severity"]},
        },
        "focus": {
            "type": "array",
            "items": {"type": "object", "properties": {"title": {"type": "string"}, "detail": {"type": "string"}}, "required": ["title", "detail"]},
        },
    },
    "required": ["title", "score", "summary", "wins", "mistakes", "focus"],
}


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        set_cors(self)
        self.end_headers()

    def do_POST(self):
        if auth_or_401(self) is None:
            return
        if not GEMINI_API_KEY:
            json_error(self, 503, 'AI is not configured on this server.')
            return
        data = read_json_body(self)
        if not data:
            json_error(self, 400, 'Invalid request body')
            return

        week_start = data.get('weekStart', '')
        week_end   = data.get('weekEnd', '')
        stats      = data.get('stats', {})
        trades     = data.get('trades', []) or []

        if not trades:
            json_error(self, 400, 'No trades in the requested week')
            return

        lines = [
            f'WEEK: {week_start} → {week_end}',
            f'Trades: {len(trades)}',
            f'Win rate: {stats.get("winRate","?")}%',
            f'Net P&L: ${stats.get("totalPnl","?")}',
            f'Avg R:R: {stats.get("avgRR","?")}',
            f'Profit factor: {stats.get("profitFactor","?")}',
            f'Calm: {stats.get("calmCount",0)}, FOMO: {stats.get("fomoCount",0)}, '
            f'Revenge: {stats.get("revengeCount",0)}, Greedy: {stats.get("greedyCount",0)}',
            '', 'TRADES THIS WEEK:',
        ]
        for t in trades[:40]:
            pnl = t.get('pnl', 0) or 0
            outcome = f'+${pnl}' if pnl > 0 else f'${pnl}'
            lines.append(
                f'- {(t.get("date") or "")[:10]} {t.get("asset","?")} '
                f'{(t.get("direction") or "").upper()} | '
                f'setup: {",".join(t.get("setup") or [])} | '
                f'emotion: {",".join(t.get("emotion") or [])} | '
                f'{outcome} | R:R {t.get("rr",0)} | rating {t.get("rating",0)}/5 | '
                f'note: "{(t.get("notes") or "")[:120]}"'
            )

        user_text = (
            'Generate a structured weekly performance review for this trader. '
            'Cite specific trades, emotions, and numbers from the data.\n\n'
            + '\n'.join(lines)
        )
        payload = {
            'system_instruction': {'parts': [{'text': WEEKLY_REVIEW_SYSTEM}]},
            'contents': [{'role': 'user', 'parts': [{'text': user_text}]}],
            'generationConfig': {
                'temperature': 0.5, 'maxOutputTokens': 1400, 'topP': 0.95,
                'responseMimeType': 'application/json',
                'responseSchema': WEEKLY_REVIEW_SCHEMA,
            },
        }

        try:
            req = urllib.request.Request(
                f'{GEMINI_URL}?key={GEMINI_API_KEY}',
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json'},
                method='POST',
            )
            with urllib.request.urlopen(req, timeout=45) as resp:
                result = json.loads(resp.read().decode('utf-8'))
            text = result['candidates'][0]['content']['parts'][0]['text']
            review = json.loads(text)
            review['weekStart']  = week_start
            review['weekEnd']    = week_end
            review['tradeCount'] = len(trades)
            review['netPnl']     = stats.get('totalPnl', 0)
            json_response(self, review)
        except urllib.error.HTTPError:
            json_error(self, 502, 'AI review service temporarily unavailable')
        except Exception:
            json_error(self, 500, 'Could not generate review — please try again')

    def log_message(self, *_):
        pass
