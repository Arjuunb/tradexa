/**
 * assets/tradebot.js
 * Attaches a Bearer token to /api/chat, /api/insights, and /api/weekly-review
 * fetches.  Exposed as window.TxFetch for app pages.
 */
(function () {
  'use strict';

  async function _authedFetch(url, options) {
    options = options || {};
    if (window.TxAuth) {
      try {
        const token = await TxAuth.getToken();
        if (token) {
          options.headers = Object.assign({}, options.headers, {
            'Authorization': 'Bearer ' + token,
          });
        }
      } catch (_) {}
    }
    const res = await fetch(url, options);

    // Defensive: guard against HTML error pages returned as "JSON"
    const ct = res.headers.get('content-type') || '';
    if (!res.ok) {
      let errMsg = 'Request failed (' + res.status + ')';
      if (ct.includes('application/json')) {
        try {
          const body = await res.json();
          if (body && body.error) errMsg = body.error;
        } catch (_) {}
      }
      throw new Error(errMsg);
    }
    if (!ct.includes('application/json') && !ct.includes('text/event-stream')) {
      throw new Error('Unexpected response type from ' + url + ': ' + ct);
    }
    return res;
  }

  /**
   * POST /api/chat
   * @param {Array} messages  [{role:'user'|'assistant', content:'...'}]
   * @param {string} [tradeContext]
   * @returns {Promise<{reply: string}>}
   */
  async function chat(messages, tradeContext) {
    const res = await _authedFetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages, tradeContext }),
    });
    return res.json();
  }

  /**
   * POST /api/insights
   * @param {string} scope  'dashboard' | 'journal' | 'analytics'
   * @param {string} tradeContext
   */
  async function insights(scope, tradeContext) {
    const res = await _authedFetch('/api/insights', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scope, tradeContext }),
    });
    return res.json();
  }

  /**
   * POST /api/weekly-review
   */
  async function weeklyReview(payload) {
    const res = await _authedFetch('/api/weekly-review', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return res.json();
  }

  window.TxFetch = { chat, insights, weeklyReview, authedFetch: _authedFetch };
})();
