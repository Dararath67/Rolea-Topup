/**
 * Rolea Topup - Branded Page Preloader & Navigation Transition Overlay
 */
(function () {
  if (window.__roleaLoaderInit) return;
  window.__roleaLoaderInit = true;

  var startTime = Date.now();
  var MIN_SHOW_MS = 380;
  var MAX_WAIT_MS = 2500;
  var hidden = false;
  var hideTimer = null;
  var safetyTimer = null;
  var pageLoaded = false;
  var authResolved = false;

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

  // Festive winter snowfall effect
  if (!document.getElementById('rolea-snow-script')) {
    var snowScript = document.createElement('script');
    snowScript.id = 'rolea-snow-script';
    snowScript.src = '/snow.js?v=20261121_v2';
    snowScript.defer = true;
    (document.head || document.documentElement).appendChild(snowScript);
  }

  // Festive Winter Santa Hat on Brand Logo (Real vector SVG, crisp on all screens)
  var SANTA_HAT_SVG = '<svg viewBox="0 0 100 85" fill="none" xmlns="http://www.w3.org/2000/svg" class="rolea-santa-hat-svg"><defs><linearGradient id="rhRed" x1="20%" y1="10%" x2="80%" y2="90%"><stop offset="0%" stop-color="#f87171"/><stop offset="30%" stop-color="#ef4444"/><stop offset="70%" stop-color="#dc2626"/><stop offset="100%" stop-color="#991b1b"/></linearGradient><linearGradient id="rhRedDark" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" stop-color="#b91c1c"/><stop offset="100%" stop-color="#7f1d1d"/></linearGradient><linearGradient id="rhWhite" x1="0%" y1="0%" x2="0%" y2="100%"><stop offset="0%" stop-color="#ffffff"/><stop offset="65%" stop-color="#f8fafc"/><stop offset="100%" stop-color="#cbd5e1"/></linearGradient><radialGradient id="rhPom" cx="38%" cy="32%" r="62%"><stop offset="0%" stop-color="#ffffff"/><stop offset="60%" stop-color="#f8fafc"/><stop offset="85%" stop-color="#e2e8f0"/><stop offset="100%" stop-color="#94a3b8"/></radialGradient><filter id="rhGlow" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="1.5" stdDeviation="1.6" flood-color="rgba(0,0,0,0.25)"/></filter></defs><g filter="url(#rhGlow)"><path d="M50 12 C62 8 74 15 78 26 C82 36 86 46 88 52 C82 50 75 44 71 36 C67 28 62 18 50 12 Z" fill="url(#rhRedDark)"/><path d="M19 58 C26 38 38 18 50 12 C56 16 64 26 68 34 C60 40 46 50 19 58 Z" fill="url(#rhRed)"/></g><g filter="url(#rhGlow)"><path d="M14 60 C14 53 22 52 28 54 C34 51 44 51 50 53 C56 51 66 51 72 54 C78 52 84 54 86 61 C86 67 79 71 72 69 C65 72 53 72 48 70 C41 73 31 73 24 69 C17 67 14 64 14 60 Z" fill="url(#rhWhite)"/></g><g filter="url(#rhGlow)"><circle cx="89" cy="54" r="10.5" fill="url(#rhPom)"/><circle cx="87" cy="52" r="3" fill="#ffffff" opacity="0.85"/></g></svg>';

  function attachSantaHats() {
    var logos = document.querySelectorAll('.brand-logo, .brand > img, .brand-link > img, .side-brand > img');
    for (var i = 0; i < logos.length; i++) {
      var img = logos[i];
      if (!img || img.dataset.hasSantaHat || img.classList.contains('rolea-santa-hat-svg')) continue;
      img.dataset.hasSantaHat = '1';
      var parent = img.parentElement;
      if (!parent) continue;

      var wrap = document.createElement('span');
      wrap.className = 'rolea-logo-hat-wrap';
      img.parentNode.insertBefore(wrap, img);
      wrap.appendChild(img);

      var hat = document.createElement('span');
      hat.className = 'rolea-santa-hat';
      hat.setAttribute('aria-hidden', 'true');
      hat.innerHTML = SANTA_HAT_SVG;
      wrap.appendChild(hat);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', attachSantaHats);
  } else {
    attachSantaHats();
  }
  window.addEventListener('load', attachSantaHats);

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

  function checkCanHide() {
    if (pageLoaded && (authResolved || window.__roleaAuthReady)) {
      hide(false);
    }
  }

  function onAuthReady() {
    authResolved = true;
    checkCanHide();
  }

  document.addEventListener('rolea:auth-ready', onAuthReady);

  // Initial load completion
  if (document.readyState === 'complete') {
    pageLoaded = true;
    checkCanHide();
  } else {
    window.addEventListener('load', function () {
      pageLoaded = true;
      checkCanHide();
    }, { once: true });
  }

  // Auth readiness fallback timer (max 650ms to ensure screen never hangs if offline or no auth)
  setTimeout(function () {
    authResolved = true;
    checkCanHide();
  }, 650);

  // Absolute safety timeout
  safetyTimer = setTimeout(function () { hide(true); }, MAX_WAIT_MS);

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

  // Instant Link Prefetching on Hover & Touch (Loads next page into cache before user finishes clicking)
  var prefetched = new Set();
  function prefetchUrl(url) {
    if (!url || prefetched.has(url)) return;
    prefetched.add(url);
    var l = document.createElement('link');
    l.rel = 'prefetch';
    l.href = url;
    l.as = 'document';
    (document.head || document.documentElement).appendChild(l);
  }

  function onPointerOver(e) {
    var a = e.target && e.target.closest ? e.target.closest('a[href]') : null;
    if (!a) return;
    var raw = a.getAttribute('href') || '';
    if (!raw || raw.charAt(0) === '#' || raw.indexOf('javascript:') === 0 || a.hasAttribute('download')) return;
    try {
      var u = new URL(a.href, window.location.href);
      if (u.origin === window.location.origin) {
        prefetchUrl(u.href);
      }
    } catch (_) {}
  }

  document.addEventListener('mouseover', onPointerOver, { passive: true });
  document.addEventListener('touchstart', onPointerOver, { passive: true });

  window.RoleaLoader = { show: show, hide: hide, onAuthReady: onAuthReady };
})();
