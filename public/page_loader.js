/**
 * Rolea Topup - Branded Page Preloader & Navigation Transition Overlay
 */
(function () {
  if (window.__roleaLoaderInit) return;
  window.__roleaLoaderInit = true;

  var startTime = Date.now();
  var MIN_SHOW_MS = 350;
  var MAX_WAIT_MS = 2400;
  var hidden = false;
  var hideTimer = null;
  var safetyTimer = null;

  var style = document.createElement('style');
  style.id = 'rolea-preloader-style';
  style.textContent = [
    '#rolea-preloader{position:fixed;inset:0;z-index:999999;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:14px;background:#ffffff;color:#0f172a;font-family:"Plus Jakarta Sans","Inter",system-ui,-apple-system,sans-serif;opacity:1;visibility:visible;transition:opacity .26s cubic-bezier(.16,1,.3,1),transform .26s cubic-bezier(.16,1,.3,1),visibility .26s linear;-webkit-font-smoothing:antialiased;}',
    'html[data-store-theme="dark"] #rolea-preloader{background:#0b1629;color:#f1f5f9;}',
    '#rolea-preloader.is-hidden{opacity:0;transform:scale(1.015);visibility:hidden;pointer-events:none;}',
    '.rl-loader-ring-wrap{position:relative;width:78px;height:78px;display:flex;align-items:center;justify-content:center;}',
    '.rl-loader-ring{position:absolute;inset:0;border-radius:50%;background:conic-gradient(from 0deg,#2563eb 0deg,#38bdf8 130deg,rgba(37,99,235,.12) 230deg,rgba(37,99,235,.06) 360deg);-webkit-mask:radial-gradient(farthest-side,transparent calc(100% - 3.5px),#000 calc(100% - 3px));mask:radial-gradient(farthest-side,transparent calc(100% - 3.5px),#000 calc(100% - 3px));animation:rlSpin .9s linear infinite;}',
    '.rl-loader-logo{width:58px;height:58px;border-radius:50%;object-fit:cover;box-shadow:0 6px 18px rgba(37,99,235,.16);background:#fff;}',
    '.rl-loader-title{font-size:16px;font-weight:800;letter-spacing:-.02em;margin-top:2px;}',
    '.rl-loader-sub{font-size:12px;font-weight:600;color:#64748b;letter-spacing:.01em;margin-top:-8px;}',
    'html[data-store-theme="dark"] .rl-loader-sub{color:#94a3b8;}',
    '.rl-loader-bar{width:132px;height:3.5px;border-radius:999px;background:#e2e8f0;overflow:hidden;position:relative;}',
    'html[data-store-theme="dark"] .rl-loader-bar{background:#1e293b;}',
    '.rl-loader-bar-fill{position:absolute;top:0;bottom:0;left:-45%;width:45%;border-radius:999px;background:linear-gradient(90deg,#2563eb,#38bdf8);animation:rlBarSlide 1.05s cubic-bezier(.4,0,.2,1) infinite;}',
    '@keyframes rlSpin{to{transform:rotate(360deg);}}',
    '@keyframes rlBarSlide{0%{left:-45%;width:42%;}50%{left:35%;width:52%;}100%{left:105%;width:38%;}}'
  ].join('');
  (document.head || document.documentElement).appendChild(style);

  var overlay = document.createElement('div');
  overlay.id = 'rolea-preloader';
  overlay.setAttribute('aria-live', 'polite');
  overlay.setAttribute('aria-label', 'Loading page');
  overlay.innerHTML =
    '<div class="rl-loader-ring-wrap">' +
      '<div class="rl-loader-ring"></div>' +
      '<img class="rl-loader-logo" src="/media/rolea-logo.webp" alt="Rolea Topup">' +
    '</div>' +
    '<div class="rl-loader-title">Rolea Topup</div>' +
    '<div class="rl-loader-sub" id="rl-loader-sub">Loading…</div>' +
    '<div class="rl-loader-bar"><div class="rl-loader-bar-fill"></div></div>';

  document.documentElement.appendChild(overlay);

  function setLabel(text) {
    var sub = document.getElementById('rl-loader-sub');
    if (sub && text) sub.textContent = text;
  }

  function show(text) {
    clearTimeout(hideTimer);
    clearTimeout(safetyTimer);
    hidden = false;
    startTime = Date.now();
    if (text) setLabel(text);
    overlay.style.display = 'flex';
    overlay.classList.remove('is-hidden');
    safetyTimer = setTimeout(function () { hide(true); }, 3500);
  }

  function hide(immediate) {
    if (hidden) return;
    clearTimeout(hideTimer);
    clearTimeout(safetyTimer);
    var elapsed = Date.now() - startTime;
    var wait = immediate ? 0 : Math.max(0, MIN_SHOW_MS - elapsed);
    hideTimer = setTimeout(function () {
      hidden = true;
      overlay.classList.add('is-hidden');
      setTimeout(function () {
        if (hidden) overlay.style.display = 'none';
      }, 280);
    }, wait);
  }

  // Initial load completion + safety timeout
  if (document.readyState === 'complete') {
    hide(false);
  } else {
    window.addEventListener('load', function () { hide(false); }, { once: true });
    safetyTimer = setTimeout(function () { hide(true); }, MAX_WAIT_MS);
  }

  // Handle back/forward cache restore cleanly so loader never gets stuck
  window.addEventListener('pageshow', function (e) {
    if (e.persisted) hide(true);
  });

  // Smooth transition on same-origin internal page navigation
  document.addEventListener('click', function (e) {
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    var link = e.target && e.target.closest ? e.target.closest('a[href]') : null;
    if (!link) return;
    if (link.target && link.target !== '_self') return;
    if (link.hasAttribute('download')) return;

    var rawHref = link.getAttribute('href') || '';
    if (!rawHref || rawHref.charAt(0) === '#' || rawHref.indexOf('javascript:') === 0 || rawHref.indexOf('mailto:') === 0 || rawHref.indexOf('tel:') === 0) return;

    try {
      var targetUrl = new URL(link.href, window.location.href);
      if (targetUrl.origin !== window.location.origin) return;
      if (targetUrl.pathname === window.location.pathname && targetUrl.search === window.location.search && targetUrl.hash) return;
      show('Opening page…');
    } catch (_) {}
  });

  window.RoleaLoader = { show: show, hide: hide };
})();
