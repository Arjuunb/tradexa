/**
 * assets/nav.js
 * Injects the marketing site nav and swaps CTAs between
 * "Login / Start Free" (signed-out) and a user menu (signed-in).
 */
(function () {
  'use strict';

  var NAV_CSS =
    '#tx-nav{position:fixed;top:0;left:0;right:0;z-index:1000;height:64px;' +
    'background:rgba(13,15,18,.92);border-bottom:1px solid rgba(255,255,255,.07);' +
    'backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);' +
    'display:flex;align-items:center;font-family:Inter,sans-serif}' +
    '#tx-nav-inner{max-width:1300px;margin:0 auto;padding:0 28px;width:100%;' +
    'display:flex;align-items:center;justify-content:space-between}' +
    '.tx-nav-logo{display:flex;align-items:center;gap:10px;text-decoration:none}' +
    '.tx-nav-logo-mark{width:28px;height:28px;border-radius:7px;' +
    'background:linear-gradient(135deg,rgba(255,183,50,.2),rgba(94,129,172,.1));' +
    'border:1px solid rgba(255,183,50,.3);display:flex;align-items:center;' +
    'justify-content:center;font-size:15px}' +
    '.tx-nav-logo-name{font-size:16px;font-weight:800;color:#fff;letter-spacing:-.03em}' +
    '.tx-nav-links{display:flex;align-items:center;gap:4px}' +
    '.tx-nav-link{font-size:13px;font-weight:500;color:#A1A1AA;text-decoration:none;' +
    'padding:7px 14px;border-radius:6px;transition:color .15s}' +
    '.tx-nav-link:hover{color:#fff}' +
    '.tx-nav-cta{display:flex;align-items:center;gap:10px}' +
    '.tx-nav-btn-ghost{font-size:13px;font-weight:500;color:#A1A1AA;text-decoration:none;' +
    'padding:8px 16px;border-radius:6px;border:1px solid rgba(255,255,255,.1);' +
    'background:transparent;cursor:pointer;font-family:Inter,sans-serif;transition:all .15s}' +
    '.tx-nav-btn-ghost:hover{color:#fff;border-color:rgba(255,255,255,.25)}' +
    '.tx-nav-btn-primary{font-size:13px;font-weight:700;color:#0d0f12;background:#FFB732;' +
    'text-decoration:none;padding:8px 18px;border-radius:6px;transition:background .15s}' +
    '.tx-nav-btn-primary:hover{background:#b08c1f}' +
    '.tx-nav-user-email{font-size:12px;color:#525252;max-width:180px;' +
    'overflow:hidden;text-overflow:ellipsis;white-space:nowrap}' +
    '#tx-nav-spacer{height:64px}' +
    '@media(max-width:680px){.tx-nav-links{display:none}}';

  var style = document.createElement('style');
  style.textContent = NAV_CSS;
  document.head.appendChild(style);

  var navEl = document.createElement('nav');
  navEl.id = 'tx-nav';
  navEl.setAttribute('role', 'navigation');
  navEl.setAttribute('aria-label', 'Main');
  navEl.innerHTML =
    '<div id="tx-nav-inner">' +
      '<a href="/" class="tx-nav-logo">' +
        '<div class="tx-nav-logo-mark">&#128200;</div>' +
        '<span class="tx-nav-logo-name">Tradexa</span>' +
      '</a>' +
      '<div class="tx-nav-links">' +
        '<a href="/#features" class="tx-nav-link">Features</a>' +
        '<a href="/#pricing" class="tx-nav-link">Pricing</a>' +
        '<a href="/changelog.html" class="tx-nav-link">Changelog</a>' +
        '<a href="/roadmap.html" class="tx-nav-link">Roadmap</a>' +
      '</div>' +
      '<div class="tx-nav-cta" id="tx-nav-cta">' +
        '<a href="/auth/login.html" class="tx-nav-btn-ghost" id="tx-nav-login">Login</a>' +
        '<a href="/auth/register.html" class="tx-nav-btn-primary" id="tx-nav-register">Start Free</a>' +
      '</div>' +
    '</div>';

  // Spacer so page content isn't hidden behind fixed nav
  var spacer = document.createElement('div');
  spacer.id = 'tx-nav-spacer';

  document.body.insertBefore(spacer, document.body.firstChild);
  document.body.insertBefore(navEl, document.body.firstChild);

  // Swap to user menu when signed in
  function _updateNav() {
    if (!window.TxAuth) return;
    TxAuth.ready
      .then(function () { return TxAuth.getUser(); })
      .then(function (user) {
        if (!user) return;
        var cta = document.getElementById('tx-nav-cta');
        if (!cta) return;
        cta.innerHTML =
          '<span class="tx-nav-user-email">' + (user.email || '') + '</span>' +
          '<button class="tx-nav-btn-ghost" onclick="TxAuth.signOut()">Sign Out</button>';
      })
      .catch(function () {});
  }

  // TxAuth may not be ready yet — wait for the event
  document.addEventListener('tx-auth-ready', _updateNav);
  // Also try immediately in case supabase-auth.js loaded first
  if (window.TxAuth) _updateNav();
})();
