/**
 * Rolea Topup - Customer Authentication, Wallet & Balance Manager
 */
(function() {
  let currentUser = null;
  const TOKEN_KEY = 'rolea_token';
  const USER_CACHE_KEY = 'rolea_user_cache';

  function getCachedUser() {
    try {
      const raw = localStorage.getItem(USER_CACHE_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch(e) { return null; }
  }

  function setCachedUser(u) {
    try {
      if (u) localStorage.setItem(USER_CACHE_KEY, JSON.stringify(u));
      else localStorage.removeItem(USER_CACHE_KEY);
    } catch(e) {}
  }

  function notifyAuthReady() {
    window.__roleaAuthReady = true;
    try {
      document.dispatchEvent(new CustomEvent('rolea:auth-ready', { detail: { user: currentUser } }));
    } catch(e) {}
    if (window.RoleaLoader && typeof window.RoleaLoader.onAuthReady === 'function') {
      try { window.RoleaLoader.onAuthReady(); } catch(e) {}
    }
  }

  // Inject Styles
  const style = document.createElement('style');
  style.textContent = `
    .nav-auth-container { display: flex; align-items: center; gap: 8px; margin-left: 12px; flex-shrink: 0; }
    .btn-nav-auth { padding: 6px 14px; border-radius: 999px; font-size: 13px; font-weight: 600; cursor: pointer; border: 1.5px solid #0056b3; background: transparent; color: #0056b3; transition: all 0.2s; text-decoration: none; display: inline-flex; align-items: center; justify-content: center; white-space: nowrap; flex-shrink: 0; }
    .btn-nav-auth:hover { background: #f0f7ff; }
    .btn-nav-auth.primary { background: #0056b3; color: #fff; }
    .btn-nav-auth.primary:hover { background: #004494; }
    .btn-nav-auth-mobile {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      height: 34px;
      padding: 0 13px;
      background: linear-gradient(135deg, #1d4ed8 0%, #0284c7 100%);
      color: #ffffff !important;
      border-radius: 999px;
      font-size: 12.5px;
      font-weight: 700;
      text-decoration: none !important;
      box-shadow: 0 2px 7px rgba(29, 78, 216, 0.32);
      white-space: nowrap;
      letter-spacing: -0.2px;
      border: 1px solid rgba(255, 255, 255, 0.22);
      transition: all 0.15s cubic-bezier(0.4, 0, 0.2, 1);
      -webkit-tap-highlight-color: transparent;
    }
    .btn-nav-auth-mobile:hover {
      opacity: 0.96;
      transform: translateY(-1px);
      box-shadow: 0 4px 12px rgba(29, 78, 216, 0.42);
    }
    .btn-nav-auth-mobile:active {
      transform: scale(0.95);
      box-shadow: 0 1px 3px rgba(29, 78, 216, 0.25);
    }

    .nav-wallet-chip { display: inline-flex; align-items: center; gap: 6px; padding: 5px 12px; background: #ecfdf5; border: 1.5px solid #a7f3d0; border-radius: 999px; cursor: pointer; font-size: 13px; font-weight: 700; color: #065f46; transition: all 0.2s; }
    .nav-wallet-chip:hover { background: #d1fae5; transform: translateY(-1px); }
    .nav-wallet-chip .wallet-add { background: #10b981; color: #fff; border-radius: 50%; width: 18px; height: 18px; display: inline-flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 900; margin-left: 4px; }

    .nav-user-dropdown { position: relative; }
    .nav-user-pill { display: flex; align-items: center; gap: 8px; padding: 4px 10px 4px 6px; background: #f8fafc; border: 1.5px solid #e2e8f0; border-radius: 999px; cursor: pointer; transition: all 0.2s; }
    .nav-user-pill:hover { border-color: #cbd5e1; background: #fff; }
    .nav-user-pill img { width: 26px; height: 26px; border-radius: 50%; object-fit: cover; }
    .nav-user-pill span { font-size: 13px; font-weight: 600; color: #0f172a; max-width: 100px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

    .app-header { z-index: 45 !important; }
    .user-menu-popover { position: absolute; top: calc(100% + 8px); right: 0; background: #fff; border: 1.5px solid #e2e8f0; border-radius: 16px; box-shadow: 0 14px 35px rgba(0,0,0,0.14); width: 230px; padding: 10px; z-index: 9999; display: none; }
    .user-menu-popover.active { display: block; animation: popoverSlide 0.2s cubic-bezier(0.16, 1, 0.3, 1); }
    @keyframes popoverSlide { from { opacity: 0; transform: translateY(-6px); } to { opacity: 1; transform: translateY(0); } }

    .user-menu-header { padding: 8px 10px 12px; border-bottom: 1px solid #f1f5f9; margin-bottom: 6px; }
    .user-menu-header .uname { font-size: 14px; font-weight: 800; color: #0f172a; }
    .user-menu-header .uemail { font-size: 11px; color: #64748b; margin-top: 2px; }
    .user-menu-header .ubal { font-size: 13px; font-weight: 700; color: #059669; margin-top: 6px; }

    .user-menu-item { display: flex; align-items: center; gap: 10px; padding: 8px 10px; font-size: 13px; font-weight: 600; color: #334155; border-radius: 10px; cursor: pointer; text-decoration: none; transition: background 0.15s; }
    .user-menu-item:hover { background: #f8fafc; color: #0f172a; }
    .user-menu-item.logout { color: #dc2626; border-top: 1px solid #f1f5f9; margin-top: 6px; border-radius: 0 0 10px 10px; }
    .user-menu-item.logout:hover { background: #fef2f2; }

    /* Auth & Wallet Modals */
    .rolea-modal-backdrop { position: fixed; inset: 0; background: rgba(15, 23, 42, 0.65); backdrop-filter: blur(5px); z-index: 99999; display: flex; align-items: center; justify-content: center; padding: 16px; animation: modalFade 0.2s ease; }
    @keyframes modalFade { from { opacity: 0; } to { opacity: 1; } }
    .rolea-modal-card { background: #fff; width: 100%; max-width: 420px; border-radius: 24px; box-shadow: 0 25px 60px rgba(0,0,0,0.2); overflow: hidden; animation: modalZoom 0.25s cubic-bezier(0.16, 1, 0.3, 1); }
    @keyframes modalZoom { from { transform: scale(0.95); opacity: 0; } to { transform: scale(1); opacity: 1; } }

    .rolea-modal-head { display: flex; align-items: center; justify-content: space-between; padding: 20px 24px 16px; border-bottom: 1px solid #f1f5f9; }
    .rolea-modal-head h3 { margin: 0; font-size: 18px; font-weight: 800; color: #0f172a; }
    .rolea-modal-close { background: #f1f5f9; border: none; width: 32px; height: 32px; border-radius: 50%; font-size: 16px; cursor: pointer; display: flex; align-items: center; justify-content: center; color: #64748b; }
    .rolea-modal-close:hover { background: #e2e8f0; color: #0f172a; }

    .rolea-modal-body { padding: 20px 24px; }
    .rolea-tabs { display: flex; background: #f1f5f9; border-radius: 12px; padding: 4px; margin-bottom: 20px; }
    .rolea-tab { flex: 1; text-align: center; padding: 8px; font-size: 13px; font-weight: 700; border-radius: 8px; cursor: pointer; color: #64748b; transition: all 0.2s; }
    .rolea-tab.active { background: #fff; color: #0f172a; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }

    .rolea-field { margin-bottom: 14px; }
    .rolea-field label { display: block; font-size: 12px; font-weight: 700; color: #475569; margin-bottom: 6px; }
    .rolea-field input { width: 100%; padding: 10px 14px; border: 1.5px solid #cbd5e1; border-radius: 10px; font-size: 14px; box-sizing: border-box; }
    .rolea-field input:focus { border-color: #0056b3; outline: none; box-shadow: 0 0 0 3px rgba(0, 86, 179, 0.12); }

    .btn-rolea-submit { width: 100%; padding: 12px; background: #0056b3; color: #fff; border: none; border-radius: 12px; font-size: 14px; font-weight: 700; cursor: pointer; transition: background 0.2s; margin-top: 10px; }
    .btn-rolea-submit:hover { background: #004494; }

    /* Top-up amounts */
    .topup-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 16px; }
    .topup-amt-btn { padding: 12px 8px; border: 1.5px solid #e2e8f0; border-radius: 12px; font-size: 14px; font-weight: 700; text-align: center; cursor: pointer; background: #f8fafc; color: #0f172a; transition: all 0.2s; }
    .topup-amt-btn:hover, .topup-amt-btn.selected { border-color: #10b981; background: #ecfdf5; color: #065f46; }

    .btn-google-auth { width: 100%; display: flex; align-items: center; justify-content: center; gap: 10px; background: #ffffff; border: 1.5px solid #cbd5e1; border-radius: 12px; padding: 11px 16px; font-size: 13.5px; font-weight: 700; color: #1e293b; cursor: pointer; transition: all 0.15s ease; box-shadow: 0 1px 3px rgba(0,0,0,0.04); font-family: inherit; margin-bottom: 14px; }
    .btn-google-auth:hover { background: #f8fafc; border-color: #94a3b8; box-shadow: 0 2px 6px rgba(0,0,0,0.08); }
    .auth-divider { display: flex; align-items: center; text-align: center; color: #94a3b8; font-size: 11px; font-weight: 700; margin: 12px 0 16px; text-transform: uppercase; letter-spacing: 0.5px; }
    .auth-divider::before, .auth-divider::after { content: ''; flex: 1; border-bottom: 1px solid #e2e8f0; }
    .auth-divider span { padding: 0 10px; }
    .google-account-pill:hover { background: #f1f5f9 !important; border-color: #cbd5e1 !important; transform: translateY(-1px); }
  `;
  document.head.appendChild(style);

  // Authentication Helpers
  function getToken() {
    return localStorage.getItem(TOKEN_KEY) || '';
  }

  function setToken(token) {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  }

  function getAuthHeaders() {
    const t = getToken();
    return t ? { 'Authorization': 'Bearer ' + t } : {};
  }

  async function checkCurrentUser() {
    let t = getToken();

    // 1. If we already have a local token, verify it with /api/auth/me
    if (t) {
      try {
        const res = await fetch('/api/auth/me', {
          headers: { 'Authorization': 'Bearer ' + t },
          credentials: 'include'
        });
        const j = await res.json();
        if (res.ok && j.ok && j.user) {
          currentUser = j.user;
          setCachedUser(j.user);
          renderNavbar();
          notifyAuthReady();
          return;
        } else {
          currentUser = null;
          setCachedUser(null);
          setToken(null);
          t = null;
        }
      } catch (e) {
        console.warn('Auth check offline');
        if (currentUser) {
          notifyAuthReady();
          return;
        }
      }
    }

    // 2. If no local token, check if authenticated via Cookie rolea_token
    try {
      const cRes = await fetch('/api/auth/me', { credentials: 'include' });
      const cJ = await cRes.json();
      if (cRes.ok && cJ.ok && cJ.user) {
        currentUser = cJ.user;
        setCachedUser(cJ.user);
        if (cJ.token) setToken(cJ.token);
        renderNavbar();
        notifyAuthReady();
        return;
      }
    } catch (e) {}

    // 3. Auto-Login when admin refund and guest opens website again (ANY PAGE):
    // Cryptographically verified via secret receipt token stored in localStorage
    try {
      const candidateOrders = [];
      const tokensMap = {};
      try {
        const rawPuti = JSON.parse(localStorage.getItem('puti_reach_my_orders_v22') || '[]');
        if (Array.isArray(rawPuti)) {
          rawPuti.forEach(x => {
            if (x && x.order_id) {
              candidateOrders.push(x.order_id);
              if (x.token) tokensMap[x.order_id] = x.token;
            }
          });
        }
      } catch (e) {}
      try {
        const rawRec = JSON.parse(localStorage.getItem('rolea_recent_orders') || '[]');
        if (Array.isArray(rawRec)) candidateOrders.push(...rawRec);
      } catch (e) {}

      const uniqueOrderIds = Array.from(new Set(candidateOrders.filter(Boolean))).slice(0, 10);
      if (uniqueOrderIds.length > 0) {
        const refRes = await fetch('/api/auth/check-refund-autologin', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({ order_ids: uniqueOrderIds, tokens: tokensMap })
        });
        if (refRes.ok) {
          const refData = await refRes.json();
          if (refData.ok && refData.auto_login_token && refData.user) {
            setToken(refData.auto_login_token);
            document.cookie = `rolea_token=${refData.auto_login_token}; path=/; max-age=2592000; SameSite=Lax`;
            currentUser = refData.user;
            setCachedUser(refData.user);
            renderNavbar();
            notifyAuthReady();
            return;
          }
        }
      }
    } catch (e) {}

    currentUser = null;
    setCachedUser(null);
    renderNavbar();
    notifyAuthReady();
  }

  // Render Navbar Items
  function buildUserPopoverHtml(popoverId) {
    return `
      <div class="user-menu-popover" id="${popoverId}">
        <div class="user-menu-header">
          <div class="uname">${currentUser.username}</div>
          <div class="uemail">${currentUser.email || 'Verified Customer'}</div>
          <div class="ubal">Balance: $${Number(currentUser.balance || 0).toFixed(2)} USD</div>
        </div>
        <a class="user-menu-item" href="/my-account">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg> My Account & Orders
        </a>
        <div class="user-menu-item" onclick="window.RoleaAuth.openWalletModal()">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 1v22M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg> Top up Wallet
        </div>
        <div class="user-menu-item logout" onclick="window.RoleaAuth.logout()">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg> Sign Out
        </div>
      </div>
    `;
  }

  function renderNavbar() {
    // Desktop Nav
    const desktopLinks = document.querySelector('.desktop-nav .nav-links');
    if (desktopLinks) {
      let authBox = document.getElementById('rolea-desktop-auth');
      if (!authBox) {
        authBox = document.createElement('div');
        authBox.id = 'rolea-desktop-auth';
        authBox.className = 'nav-auth-container';
        desktopLinks.appendChild(authBox);
      }

      if (currentUser) {
        authBox.innerHTML = `
          <div class="nav-wallet-chip" onclick="window.RoleaAuth.openWalletModal()" title="Click to Top up Wallet">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#065f46" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0"><path d="M20 7H4a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2z"/><path d="M16 3H8a2 2 0 0 0-2 2v2h12V5a2 2 0 0 0-2-2z"/><circle cx="16" cy="14" r="1.5" fill="#065f46"/></svg>
            <span class="wallet-val">$${Number(currentUser.balance || 0).toFixed(2)}</span>
            <span class="wallet-add" title="Deposit funds">+</span>
          </div>
          <div class="nav-user-dropdown" id="nav-user-dropdown">
            <div class="nav-user-pill" onclick="window.RoleaAuth.toggleUserMenu('user-menu-popover')">
              <img src="${currentUser.avatar || '/media/rolea-logo.webp'}" alt="${currentUser.username}">
              <span>${currentUser.username}</span>
            </div>
            ${buildUserPopoverHtml('user-menu-popover')}
          </div>
        `;
      } else {
        authBox.innerHTML = `
          <a href="/signin" class="btn-nav-auth primary" style="display:inline-flex;align-items:center;gap:7px;height:38px;padding:0 18px;font-weight:700;font-size:13.5px;text-decoration:none;border-radius:12px;background:linear-gradient(135deg, #0056b3 0%, #0284c7 100%);color:#fff;box-shadow:0 3px 10px rgba(0,86,179,0.25);">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
            <span>Sign In</span>
          </a>
        `;
      }
    }

    // Mobile Header Actions
    const mobileActions = document.querySelector('.header-actions, .app-header .header-actions, .crash-header .header-actions, .games-header .header-actions');
    if (mobileActions) {
      let mobBox = document.getElementById('rolea-mobile-auth');
      if (!mobBox) {
        mobBox = document.createElement('div');
        mobBox.id = 'rolea-mobile-auth';
        mobBox.style.display = 'inline-flex';
        mobBox.style.alignItems = 'center';
        mobBox.style.gap = '6px';
        mobileActions.insertBefore(mobBox, mobileActions.firstChild);
      }

      if (currentUser) {
        mobBox.innerHTML = `
          <div class="nav-wallet-chip" style="height:34px;padding:0 10px;font-size:12px;font-weight:800;border-radius:999px;display:inline-flex;align-items:center;gap:5px;box-shadow:0 1px 4px rgba(0,0,0,0.05);" onclick="window.RoleaAuth.openWalletModal()">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#059669" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0"><path d="M20 7H4a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2z"/><path d="M16 3H8a2 2 0 0 0-2 2v2h12V5a2 2 0 0 0-2-2z"/><circle cx="16" cy="14" r="1.5" fill="#059669"/></svg>
            <span>$${Number(currentUser.balance || 0).toFixed(2)}</span>
          </div>
          <div class="nav-user-dropdown" id="nav-user-dropdown-mobile">
            <button type="button" class="nav-user-pill" aria-label="Account menu" style="height:34px;width:34px;padding:0;border-radius:999px;display:inline-flex;align-items:center;justify-content:center;border:1.5px solid #2563eb;overflow:hidden;box-shadow:0 2px 6px rgba(37,99,235,0.25);cursor:pointer;background:#fff;" onclick="window.RoleaAuth.toggleUserMenu('user-menu-popover-mobile')">
              <img src="${currentUser.avatar || '/media/rolea-logo.webp'}" style="width:100%;height:100%;border-radius:50%;object-fit:cover" alt="${currentUser.username}">
            </button>
            ${buildUserPopoverHtml('user-menu-popover-mobile')}
          </div>
        `;
      } else {
        mobBox.innerHTML = `
          <a href="/signin" class="btn-nav-auth-mobile">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
            <span>Sign In</span>
          </a>
        `;
      }
    }

    // Bottom Nav Account link handler
    const btmAcc = document.getElementById('nav-item-account');
    if (btmAcc) {
      btmAcc.href = currentUser ? '/my-account' : '/signin';
      btmAcc.onclick = null;
    }

    // Notify any page listeners (e.g., checkout page wallet balance button)
    window.dispatchEvent(new CustomEvent('rolea-auth-change', { detail: { user: currentUser } }));
  }

  // Auth Modal
  function openAuthModal(initialTab = 'login') {
    closeModals();
    const modal = document.createElement('div');
    modal.id = 'rolea-auth-modal';
    modal.className = 'rolea-modal-backdrop';
    modal.onclick = (e) => { if (e.target === modal) closeModals(); };

    modal.innerHTML = `
      <div class="rolea-modal-card">
        <div class="rolea-modal-head">
          <h3 id="auth-modal-title">${initialTab === 'login' ? 'Customer Sign In' : 'Create Account'}</h3>
          <button class="rolea-modal-close" onclick="window.RoleaAuth.closeModals()">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>
        <div class="rolea-modal-body">
          <!-- Google Sign In Button -->
          <button class="btn-google-auth" type="button" onclick="window.RoleaAuth.loginWithGoogle()">
            <svg width="19" height="19" viewBox="0 0 48 48">
              <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>
              <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>
              <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/>
              <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/>
            </svg>
            <span>Continue with Google</span>
          </button>

          <div class="auth-divider">
            <span>or continue with email</span>
          </div>

          <div class="rolea-tabs">
            <div class="rolea-tab ${initialTab === 'login' ? 'active' : ''}" onclick="window.RoleaAuth.switchAuthTab('login')">Sign In</div>
            <div class="rolea-tab ${initialTab === 'register' ? 'active' : ''}" onclick="window.RoleaAuth.switchAuthTab('register')">Register</div>
          </div>

          <!-- Form: Login -->
          <form id="form-auth-login" style="display:${initialTab === 'login' ? 'block' : 'none'}" onsubmit="window.RoleaAuth.handleLogin(event)">
            <div class="rolea-field">
              <label>Username or Email</label>
              <input type="text" id="auth-login-username" placeholder="e.g. reach2026" required autocomplete="username">
            </div>
            <div class="rolea-field">
              <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px">
                <label style="margin-bottom:0">Password</label>
                <a href="javascript:void(0)" onclick="window.RoleaAuth.switchAuthTab('forgot')" style="font-size:11.5px;font-weight:700;color:#0284c7;text-decoration:none">Forgot password?</a>
              </div>
              <input type="password" id="auth-login-password" placeholder="••••••••" required autocomplete="current-password">
            </div>
            <div id="auth-login-error" style="color:#dc2626;font-size:12px;font-weight:600;margin-bottom:8px"></div>
            <button class="btn-rolea-submit" type="submit">Sign In to Store</button>
          </form>

          <!-- Form: Forgot Password -->
          <form id="form-auth-forgot" style="display:none" onsubmit="window.RoleaAuth.handleForgotSubmit(event)">
            <div class="rolea-field">
              <label>Registered Email or Username</label>
              <input type="text" id="auth-fp-identifier" placeholder="Enter your email or username" required>
            </div>
            <div id="auth-fp-step2" style="display:none">
              <div class="rolea-field">
                <label>6-Digit Verification Code</label>
                <input type="text" id="auth-fp-code" placeholder="123456" maxlength="6" inputmode="numeric">
              </div>
            </div>
            <div id="auth-fp-step3" style="display:none">
              <div class="rolea-field">
                <label>New Password (min 6 characters)</label>
                <input type="password" id="auth-fp-pw" placeholder="••••••••" minlength="6">
              </div>
              <div class="rolea-field">
                <label>Confirm New Password</label>
                <input type="password" id="auth-fp-conf" placeholder="••••••••" minlength="6">
              </div>
            </div>
            <div id="auth-fp-msg" style="font-size:12px;font-weight:600;margin-bottom:8px"></div>
            <button class="btn-rolea-submit" id="auth-fp-btn" type="submit">Send Verification Code</button>
            <div style="text-align:center;margin-top:10px">
              <a href="javascript:void(0)" onclick="window.RoleaAuth.switchAuthTab('login')" style="font-size:12px;font-weight:700;color:#64748b;text-decoration:none">← Back to Sign In</a>
            </div>
          </form>

          <!-- Form: Register -->
          <form id="form-auth-register" style="display:${initialTab === 'register' ? 'block' : 'none'}" onsubmit="window.RoleaAuth.handleRegister(event)">
            <div class="rolea-field">
              <label>Choose Username</label>
              <input type="text" id="auth-reg-username" placeholder="e.g. reach2026" required minlength="3">
            </div>
            <div class="rolea-field">
              <label>Email Address (Optional)</label>
              <input type="email" id="auth-reg-email" placeholder="customer@gmail.com">
            </div>
            <div class="rolea-field">
              <label>Password (min 6 characters)</label>
              <input type="password" id="auth-reg-password" placeholder="••••••••" required minlength="6">
            </div>
            <div id="auth-reg-error" style="color:#dc2626;font-size:12px;font-weight:600;margin-bottom:8px"></div>
            <button class="btn-rolea-submit" type="submit">Create Customer Account</button>
          </form>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
  }

  let _modalFpStage = 1;
  let _modalResetToken = '';
  function switchAuthTab(tab) {
    const isLogin = tab === 'login';
    const isForgot = tab === 'forgot';
    document.getElementById('auth-modal-title').textContent = isForgot ? 'Reset Password' : (isLogin ? 'Customer Sign In' : 'Create Account');
    document.querySelectorAll('.rolea-tab').forEach((el, i) => {
      el.classList.toggle('active', (i === 0 && isLogin) || (i === 1 && tab === 'register'));
    });
    document.getElementById('form-auth-login').style.display = isLogin ? 'block' : 'none';
    document.getElementById('form-auth-register').style.display = tab === 'register' ? 'block' : 'none';
    const fpForm = document.getElementById('form-auth-forgot');
    if (fpForm) {
      fpForm.style.display = isForgot ? 'block' : 'none';
      if (isForgot) {
        _modalFpStage = 1;
        _modalResetToken = '';
        document.getElementById('auth-fp-identifier').readOnly = false;
        document.getElementById('auth-fp-step2').style.display = 'none';
        document.getElementById('auth-fp-step3').style.display = 'none';
        document.getElementById('auth-fp-code').value = '';
        document.getElementById('auth-fp-code').required = false;
        document.getElementById('auth-fp-pw').required = false;
        document.getElementById('auth-fp-conf').required = false;
        document.getElementById('auth-fp-msg').textContent = '';
        document.getElementById('auth-fp-btn').textContent = 'Send Verification Code';
      }
    }
  }

  async function handleForgotSubmit(e) {
    e.preventDefault();
    const msg = document.getElementById('auth-fp-msg');
    const btn = document.getElementById('auth-fp-btn');
    const identifier = document.getElementById('auth-fp-identifier').value.trim();
    msg.textContent = '';
    btn.disabled = true;
    try {
      if (_modalFpStage === 1) {
        const res = await fetch('/api/auth/forgot-password', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ identifier })
        });
        const j = await res.json();
        if (res.ok && j.ok) {
          _modalFpStage = 2;
          document.getElementById('auth-fp-identifier').readOnly = true;
          document.getElementById('auth-fp-step2').style.display = 'block';
          document.getElementById('auth-fp-code').required = true;
          btn.textContent = 'Verify 6-Digit Code';
          msg.style.color = '#0369a1';
          msg.textContent = j.message || 'Verification code sent!';
        } else {
          msg.style.color = '#dc2626';
          msg.textContent = j.error || 'Account not found';
        }
      } else if (_modalFpStage === 2) {
        const code = document.getElementById('auth-fp-code').value.trim();
        const res = await fetch('/api/auth/verify-reset-code', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ identifier, code })
        });
        const j = await res.json();
        if (res.ok && j.ok && j.reset_token) {
          _modalFpStage = 3;
          _modalResetToken = j.reset_token;
          document.getElementById('auth-fp-step2').style.display = 'none';
          document.getElementById('auth-fp-step3').style.display = 'block';
          document.getElementById('auth-fp-code').required = false;
          document.getElementById('auth-fp-pw').required = true;
          document.getElementById('auth-fp-conf').required = true;
          btn.textContent = 'Save New Password';
          msg.style.color = '#15803d';
          msg.textContent = j.message || 'Code verified! Enter new password.';
        } else {
          msg.style.color = '#dc2626';
          msg.textContent = j.error || 'Incorrect verification code';
        }
      } else if (_modalFpStage === 3) {
        const new_password = document.getElementById('auth-fp-pw').value;
        const confirm_password = document.getElementById('auth-fp-conf').value;
        const res = await fetch('/api/auth/reset-password', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ identifier, reset_token: _modalResetToken, new_password, confirm_password })
        });
        const j = await res.json();
        if (res.ok && j.ok) {
          msg.style.color = '#15803d';
          msg.textContent = j.message || 'Password updated!';
          setTimeout(() => { switchAuthTab('login'); }, 1400);
        } else {
          msg.style.color = '#dc2626';
          msg.textContent = j.error || 'Reset failed';
        }
      }
    } catch (err) {
      msg.style.color = '#dc2626';
      msg.textContent = 'Network error. Try again.';
    } finally {
      btn.disabled = false;
    }
  }

  async function handleLogin(e) {
    e.preventDefault();
    const errBox = document.getElementById('auth-login-error');
    errBox.textContent = '';
    const username = document.getElementById('auth-login-username').value.trim();
    const password = document.getElementById('auth-login-password').value;

    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
      });
      const j = await res.json();
      if (res.ok && j.ok) {
        setToken(j.token);
        currentUser = j.user;
        setCachedUser(j.user);
        closeModals();
        renderNavbar();
        notifyAuthReady();
        if (typeof showToast === 'function') showToast(`Welcome back, ${currentUser.username}!`);
      } else {
        errBox.textContent = j.error || 'Login failed';
      }
    } catch (err) {
      errBox.textContent = 'Network error. Please try again.';
    }
  }

  async function handleRegister(e) {
    e.preventDefault();
    const errBox = document.getElementById('auth-reg-error');
    errBox.textContent = '';
    const username = document.getElementById('auth-reg-username').value.trim();
    const email = document.getElementById('auth-reg-email').value.trim();
    const password = document.getElementById('auth-reg-password').value;

    try {
      const res = await fetch('/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, email, password })
      });
      const j = await res.json();
      if (res.ok && j.ok) {
        setToken(j.token);
        currentUser = j.user;
        setCachedUser(j.user);
        closeModals();
        renderNavbar();
        notifyAuthReady();
        if (typeof showToast === 'function') showToast(`Account created! Welcome, ${currentUser.username}!`);
      } else {
        errBox.textContent = j.error || 'Registration failed';
      }
    } catch (err) {
      errBox.textContent = 'Network error. Please try again.';
    }
  }
  // Google Authentication (Dark Theme Account Chooser)
  function loginWithGoogle() {
    closeModals();
    if (window.RoleaGoogleChooser) {
      window.RoleaGoogleChooser.open();
    } else {
      // Lazy load google_chooser.js if not yet loaded
      const s = document.createElement('script');
      s.src = '/google_chooser.js?v=20261110_v2';
      s.onload = () => { if (window.RoleaGoogleChooser) window.RoleaGoogleChooser.open(); };
      document.body.appendChild(s);
    }
  }

  async function executeGoogleAuth(email, name) {
    if (!email) return;
    localStorage.setItem('rolea_google_email', email);
    if (name) localStorage.setItem('rolea_google_name', name);
    try {
      const res = await fetch('/api/auth/google', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, name })
      });
      const j = await res.json();
      if (res.ok && j.ok) {
        setToken(j.token);
        currentUser = j.user;
        setCachedUser(j.user);
        const gModal = document.getElementById('rolea-google-modal');
        if (gModal) gModal.remove();
        closeModals();
        renderNavbar();
        notifyAuthReady();
        if (typeof showToast === 'function') showToast(`Signed in as ${currentUser.username}!`);
      } else {
        RoleaDialog.alert({
          title: 'Google Sign-In Failed',
          message: j.error || 'Google login failed.',
          type: 'error'
        });
      }
    } catch (err) {
      RoleaDialog.alert({
        title: 'Connection Error',
        message: 'Network error connecting to Google Auth. Please try again.',
        type: 'error'
      });
    }
  }

  function handleCustomGoogle(e) {
    e.preventDefault();
    const email = document.getElementById('custom-google-email').value.trim();
    const name = document.getElementById('custom-google-name').value.trim();
    if (!email) return;
    executeGoogleAuth(email, name || email.split('@')[0]);
  }


  // Wallet Modal (Top-up balance via KHQR)
  let walletPollingInterval = null;
  let walletTtlInterval = null;

  function openWalletModal() {
    if (!currentUser) {
      openAuthModal('login');
      return;
    }
    closeModals();
    const modal = document.createElement('div');
    modal.id = 'rolea-wallet-modal';
    modal.className = 'rolea-modal-backdrop';
    modal.onclick = (e) => { if (e.target === modal) closeModals(); };

    modal.innerHTML = `
      <div class="rolea-modal-card">
        <div class="rolea-modal-head">
          <div>
            <h3 style="display:flex;align-items:center;gap:10px">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#2563eb" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0"><path d="M21 12V7H5a2 2 0 0 1 0-4h14v4"/><path d="M3 5v14a2 2 0 0 0 2 2h16v-5"/><path d="M18 12a2 2 0 0 0 0 4h4v-4z"/></svg>
              Rolea Customer Wallet
            </h3>
            <span style="font-size:12px;color:#64748b">Instant top-up & 1-click checkout</span>
          </div>
          <button class="rolea-modal-close" onclick="window.RoleaAuth.closeModals()">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>
        <div class="rolea-modal-body">
          <div style="position:relative;overflow:hidden;background:linear-gradient(135deg,#065f46 0%,#059669 60%,#10b981 100%);border-radius:16px;padding:18px 20px;display:flex;align-items:center;justify-content:space-between;margin-bottom:18px;box-shadow:0 12px 24px -8px rgba(5,150,105,0.4),inset 0 1px 0 rgba(255,255,255,0.2)">
            <div style="position:relative;z-index:1">
              <div style="font-size:11px;font-weight:700;color:rgba(236,253,245,0.88);text-transform:uppercase;letter-spacing:0.6px;margin-bottom:4px">Current Balance</div>
              <div style="font-size:27px;font-weight:900;color:#ffffff;letter-spacing:-0.02em;font-variant-numeric:tabular-nums" id="wallet-modal-cur-bal">$${Number(currentUser.balance || 0).toFixed(2)} <span style="font-size:14px;font-weight:700;opacity:0.9">USD</span></div>
            </div>
            <div style="position:relative;z-index:1;width:46px;height:46px;border-radius:14px;background:rgba(255,255,255,0.18);border:1px solid rgba(255,255,255,0.25);display:flex;align-items:center;justify-content:center;color:#ffffff;flex-shrink:0">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="5" width="20" height="14" rx="2"/><line x1="2" y1="10" x2="22" y2="10"/></svg>
            </div>
          </div>

          <div id="wallet-step-select">
            <label style="display:block;font-size:12px;font-weight:700;color:#475569;margin-bottom:8px">Select Deposit Amount (USD)</label>
            <div class="topup-grid">
              <div class="topup-amt-btn selected" onclick="window.RoleaAuth.selectTopupAmt(1.00, this)">$1.00</div>
              <div class="topup-amt-btn" onclick="window.RoleaAuth.selectTopupAmt(2.00, this)">$2.00</div>
              <div class="topup-amt-btn" onclick="window.RoleaAuth.selectTopupAmt(5.00, this)">$5.00</div>
              <div class="topup-amt-btn" onclick="window.RoleaAuth.selectTopupAmt(10.00, this)">$10.00</div>
              <div class="topup-amt-btn" onclick="window.RoleaAuth.selectTopupAmt(20.00, this)">$20.00</div>
              <div class="topup-amt-btn" onclick="window.RoleaAuth.selectTopupAmt('custom', this)">Custom</div>
            </div>

            <div id="wallet-custom-input-box" style="display:none;margin-bottom:14px">
              <label style="font-size:12px;font-weight:700;color:#475569">Custom Amount ($ USD)</label>
              <input type="number" id="wallet-custom-amt" step="0.5" min="0.5" value="15.00" style="width:100%;padding:10px 14px;border:1.5px solid #cbd5e1;border-radius:10px;font-size:16px;box-sizing:border-box">
            </div>

            <button class="btn-rolea-submit" onclick="window.RoleaAuth.createWalletDeposit()">
              Generate ABA KHQR Deposit QR
            </button>
          </div>

          <div id="wallet-step-qr" style="display:none;text-align:center">
            <div style="font-size:13px;font-weight:700;color:#0f172a;margin-bottom:6px">Scan with ABA Mobile or any KHQR Bank</div>
            <div style="font-size:20px;font-weight:900;color:#0056b3" id="wallet-qr-amount">$1.00 USD</div>
            <div style="margin:14px auto;width:200px;height:200px;border-radius:16px;overflow:hidden;border:2px solid #e2e8f0;background:#fff;display:flex;align-items:center;justify-content:center">
              <img id="wallet-qr-img" src="" alt="KHQR" style="width:100%;height:100%;object-fit:contain">
            </div>
            <div id="wallet-qr-status" style="font-size:12px;color:#64748b;display:flex;align-items:center;justify-content:center;gap:6px">
              <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#10b981;animation:pulse 1.5s infinite"></span>
              Waiting for KHQR payment confirmation…
            </div>
            <div id="wallet-qr-ttl" style="margin-top:8px;display:inline-block;padding:4px 12px;border-radius:999px;background:#f1f5f9;color:#475569;font-size:11.5px;font-weight:700;font-variant-numeric:tabular-nums">Expires in 10:00</div>
            <div style="margin-top:14px;display:flex;gap:10px">
              <a id="wallet-aba-deeplink" href="#" class="btn-rolea-submit" style="background:#0056b3;text-decoration:none;display:none;flex:1;text-align:center">Open ABA App</a>
              <button class="btn-rolea-submit" style="background:#f1f5f9;color:#334155;flex:1" onclick="window.RoleaAuth.backToDepositAmount()">Cancel</button>
            </div>
          </div>

        </div>
      </div>
    `;
    document.body.appendChild(modal);
  }

  let selectedDepositAmount = 1.00;

  function selectTopupAmt(amt, btn) {
    document.querySelectorAll('.topup-amt-btn').forEach(b => b.classList.remove('selected'));
    btn.classList.add('selected');
    const customBox = document.getElementById('wallet-custom-input-box');
    if (amt === 'custom') {
      customBox.style.display = 'block';
      selectedDepositAmount = 'custom';
    } else {
      customBox.style.display = 'none';
      selectedDepositAmount = amt;
    }
  }

  async function createWalletDeposit() {
    let amt = selectedDepositAmount;
    if (amt === 'custom') {
      amt = parseFloat(document.getElementById('wallet-custom-amt').value);
    }
    if (!amt || isNaN(amt) || amt < 0.5) {
      RoleaDialog.alert({
        title: 'Minimum Amount Required',
        message: 'Please enter an amount of at least $0.50 USD.',
        type: 'warning'
      });
      return;
    }

    try {
      const res = await fetch('/api/wallet/topup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        body: JSON.stringify({ amount: amt })
      });
      const j = await res.json();
      if (res.ok && j.ok) {
        document.getElementById('wallet-step-select').style.display = 'none';
        document.getElementById('wallet-step-qr').style.display = 'block';
        document.getElementById('wallet-qr-amount').textContent = `$${Number(amt).toFixed(2)} USD`;
        document.getElementById('wallet-qr-img').src = j.qr_url;

        const deepBtn = document.getElementById('wallet-aba-deeplink');
        if (j.aba_deeplink && deepBtn) {
          deepBtn.href = j.aba_deeplink;
          deepBtn.style.display = 'inline-block';
        }

        // Start live TTL countdown
        if (walletTtlInterval) clearInterval(walletTtlInterval);
        const ttlEl = document.getElementById('wallet-qr-ttl');
        const statusEl = document.getElementById('wallet-qr-status');
        const expMs = j.expires_at ? new Date(j.expires_at).getTime() : (Date.now() + 10 * 60 * 1000);
        const updateWalletTtl = () => {
          const sec = Math.max(0, Math.floor((expMs - Date.now()) / 1000));
          const mm = String(Math.floor(sec / 60)).padStart(2, '0');
          const ss = String(sec % 60).padStart(2, '0');
          if (ttlEl) {
            if (sec <= 0) {
              ttlEl.textContent = 'QR Expired';
              ttlEl.style.background = '#fef2f2';
              ttlEl.style.color = '#dc2626';
            } else {
              ttlEl.textContent = `Expires in ${mm}:${ss}`;
              ttlEl.style.background = sec <= 60 ? '#fffbeb' : '#f1f5f9';
              ttlEl.style.color = sec <= 60 ? '#d97706' : '#475569';
            }
          }
          if (sec <= 0) {
            if (walletPollingInterval) clearInterval(walletPollingInterval);
            if (walletTtlInterval) clearInterval(walletTtlInterval);
            if (statusEl) statusEl.textContent = 'QR code expired. Click Cancel to generate a new QR.';
          }
        };
        updateWalletTtl();
        walletTtlInterval = setInterval(updateWalletTtl, 1000);

        // Poll order status
        if (walletPollingInterval) clearInterval(walletPollingInterval);
        walletPollingInterval = setInterval(async () => {
          try {
            const stRes = await fetch(`/api/order-status/${j.order_id}`);
            const stData = await stRes.json();
            if (stData.ok && (stData.paid || stData.status === 'completed')) {
              clearInterval(walletPollingInterval);
              if (walletTtlInterval) clearInterval(walletTtlInterval);
              await checkCurrentUser();
              closeModals();
              await RoleaDialog.alert({
                title: 'Payment Confirmed!',
                message: `$${Number(amt).toFixed(2)} USD has been added to your wallet!`,
                type: 'success',
                confirmText: 'Done'
              });
            } else if (stData.status === 'expired') {
              clearInterval(walletPollingInterval);
              if (walletTtlInterval) clearInterval(walletTtlInterval);
              if (ttlEl) {
                ttlEl.textContent = 'QR Expired';
                ttlEl.style.background = '#fef2f2';
                ttlEl.style.color = '#dc2626';
              }
              if (statusEl) statusEl.textContent = 'QR code expired. Click Cancel to generate a new QR.';
            }
          } catch (e) {}
        }, 2500);

      } else {
        RoleaDialog.alert({
          title: 'Deposit Failed',
          message: j.error || 'Failed to create deposit QR.',
          type: 'error'
        });
      }
    } catch (e) {
      RoleaDialog.alert({
        title: 'Connection Error',
        message: 'Network error creating deposit. Please try again.',
        type: 'error'
      });
    }
  }

  function backToDepositAmount() {
    if (walletPollingInterval) clearInterval(walletPollingInterval);
    if (walletTtlInterval) clearInterval(walletTtlInterval);
    document.getElementById('wallet-step-select').style.display = 'block';
    document.getElementById('wallet-step-qr').style.display = 'none';
  }

  function toggleUserMenu(targetId) {
    const id = targetId || 'user-menu-popover';
    document.querySelectorAll('.user-menu-popover').forEach(el => {
      if (el.id !== id) el.classList.remove('active');
    });
    const p = document.getElementById(id);
    if (p) p.classList.toggle('active');
  }

  function closeModals() {
    if (walletPollingInterval) clearInterval(walletPollingInterval);
    if (walletTtlInterval) clearInterval(walletTtlInterval);
    document.querySelectorAll('.rolea-modal-backdrop').forEach(m => m.remove());
    document.querySelectorAll('.user-menu-popover').forEach(p => p.classList.remove('active'));
  }

  function logout() {
    setToken(null);
    setCachedUser(null);
    currentUser = null;
    closeModals();
    renderNavbar();
    notifyAuthReady();
    fetch('/api/auth/logout', { method: 'POST' }).catch(() => {});
  }

  // Global click listener to close popover
  document.addEventListener('click', (e) => {
    if (!e.target.closest('.nav-user-dropdown')) {
      document.querySelectorAll('.user-menu-popover').forEach(p => p.classList.remove('active'));
    }
  });

  // Sleek Custom Dialog System (replaces native browser alert/confirm/prompt)
  const RoleaDialog = (() => {
    const STYLE_ID = 'rolea-dialog-styles';
    const BACKDROP_ID = 'rolea-dialog-backdrop';

    function ensureStyles() {
      if (document.getElementById(STYLE_ID)) return;
      const st = document.createElement('style');
      st.id = STYLE_ID;
      st.textContent = `
        #${BACKDROP_ID} {
          position: fixed; inset: 0; z-index: 999999;
          display: flex; align-items: center; justify-content: center;
          padding: 16px;
          background: rgba(15, 23, 42, 0.56);
          backdrop-filter: blur(6px);
          -webkit-backdrop-filter: blur(6px);
          opacity: 0;
          transition: opacity 0.2s ease;
          font-family: 'Plus Jakarta Sans', 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        }
        #${BACKDROP_ID}.open { opacity: 1; }
        #${BACKDROP_ID} .rd-card {
          width: 100%; max-width: 390px;
          background: #ffffff;
          border: 1px solid rgba(226, 232, 240, 0.9);
          border-radius: 22px;
          padding: 28px 24px 22px;
          box-shadow: 0 24px 54px -12px rgba(15, 23, 42, 0.28), 0 0 0 1px rgba(15, 23, 42, 0.04);
          text-align: center;
          transform: scale(0.92) translateY(10px);
          opacity: 0;
          transition: transform 0.28s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.22s ease;
        }
        #${BACKDROP_ID}.open .rd-card {
          transform: scale(1) translateY(0);
          opacity: 1;
        }
        #${BACKDROP_ID} .rd-icon {
          width: 56px; height: 56px; border-radius: 18px;
          margin: 0 auto 16px;
          display: flex; align-items: center; justify-content: center;
        }
        #${BACKDROP_ID} .rd-icon.success { background: #ecfdf5; color: #10b981; box-shadow: inset 0 0 0 1px rgba(16, 185, 129, 0.2); }
        #${BACKDROP_ID} .rd-icon.error   { background: #fef2f2; color: #ef4444; box-shadow: inset 0 0 0 1px rgba(239, 68, 68, 0.18); }
        #${BACKDROP_ID} .rd-icon.warning { background: #fffbeb; color: #f59e0b; box-shadow: inset 0 0 0 1px rgba(245, 158, 11, 0.2); }
        #${BACKDROP_ID} .rd-icon.info    { background: #eff6ff; color: #2563eb; box-shadow: inset 0 0 0 1px rgba(37, 99, 235, 0.18); }
        #${BACKDROP_ID} .rd-title {
          margin: 0 0 8px; font-size: 18px; font-weight: 800;
          color: #0f172a; letter-spacing: -0.02em; line-height: 1.3;
        }
        #${BACKDROP_ID} .rd-msg {
          margin: 0 0 22px; font-size: 14px; font-weight: 500;
          color: #475569; line-height: 1.55; white-space: pre-line; word-break: break-word;
        }
        #${BACKDROP_ID} .rd-input {
          width: 100%; box-sizing: border-box;
          margin: -8px 0 18px; padding: 11px 14px;
          border-radius: 12px; border: 1.5px solid #cbd5e1;
          font-size: 14px; color: #0f172a; outline: none;
          transition: border-color 0.15s ease, box-shadow 0.15s ease;
        }
        #${BACKDROP_ID} .rd-input:focus {
          border-color: #2563eb;
          box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.15);
        }
        #${BACKDROP_ID} .rd-actions {
          display: flex; gap: 10px; justify-content: center;
        }
        #${BACKDROP_ID} .rd-btn {
          flex: 1; padding: 12px 18px; border-radius: 12px;
          font-size: 14px; font-weight: 700; cursor: pointer;
          border: none; transition: transform 0.15s ease, box-shadow 0.15s ease, background 0.15s ease;
        }
        #${BACKDROP_ID} .rd-btn:active { transform: scale(0.98); }
        #${BACKDROP_ID} .rd-btn-cancel {
          background: #f1f5f9; color: #475569;
        }
        #${BACKDROP_ID} .rd-btn-cancel:hover { background: #e2e8f0; color: #0f172a; }
        #${BACKDROP_ID} .rd-btn-primary {
          background: linear-gradient(135deg, #2563eb, #1d4ed8);
          color: #ffffff;
          box-shadow: 0 8px 20px -6px rgba(37, 99, 235, 0.45);
        }
        #${BACKDROP_ID} .rd-btn-primary:hover { transform: translateY(-1px); box-shadow: 0 10px 24px -6px rgba(37, 99, 235, 0.55); }
        #${BACKDROP_ID} .rd-btn-primary.success {
          background: linear-gradient(135deg, #10b981, #059669);
          box-shadow: 0 8px 20px -6px rgba(16, 185, 129, 0.45);
        }
        #${BACKDROP_ID} .rd-btn-primary.success:hover { box-shadow: 0 10px 24px -6px rgba(16, 185, 129, 0.55); }
        #${BACKDROP_ID} .rd-btn-primary.error {
          background: linear-gradient(135deg, #ef4444, #dc2626);
          box-shadow: 0 8px 20px -6px rgba(239, 68, 68, 0.45);
        }
      `;
      document.head.appendChild(st);
    }

    const ICONS = {
      success: '<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>',
      error: '<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>',
      warning: '<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
      info: '<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>'
    };

    function open(opts) {
      ensureStyles();
      const prev = document.getElementById(BACKDROP_ID);
      if (prev) prev.remove();

      const {
        mode = 'alert',
        title = 'Notice',
        message = '',
        type = 'info',
        confirmText = 'OK',
        cancelText = 'Cancel',
        placeholder = '',
        defaultValue = ''
      } = (typeof opts === 'string' ? { message: opts } : (opts || {}));

      return new Promise((resolve) => {
        const backdrop = document.createElement('div');
        backdrop.id = BACKDROP_ID;

        const card = document.createElement('div');
        card.className = 'rd-card';
        card.setAttribute('role', 'dialog');
        card.setAttribute('aria-modal', 'true');

        const iconEl = document.createElement('div');
        iconEl.className = `rd-icon ${ICONS[type] ? type : 'info'}`;
        iconEl.innerHTML = ICONS[type] || ICONS.info;

        const titleEl = document.createElement('h3');
        titleEl.className = 'rd-title';
        titleEl.textContent = title;

        const msgEl = document.createElement('p');
        msgEl.className = 'rd-msg';
        msgEl.textContent = message;

        card.appendChild(iconEl);
        card.appendChild(titleEl);
        if (message) card.appendChild(msgEl);

        let inputEl = null;
        if (mode === 'prompt') {
          inputEl = document.createElement('input');
          inputEl.className = 'rd-input';
          inputEl.type = 'text';
          inputEl.placeholder = placeholder;
          inputEl.value = defaultValue;
          card.appendChild(inputEl);
        }

        const actions = document.createElement('div');
        actions.className = 'rd-actions';

        function close(val) {
          document.removeEventListener('keydown', onKey);
          backdrop.classList.remove('open');
          setTimeout(() => {
            backdrop.remove();
            resolve(val);
          }, 180);
        }

        if (mode === 'confirm' || mode === 'prompt') {
          const cancelBtn = document.createElement('button');
          cancelBtn.type = 'button';
          cancelBtn.className = 'rd-btn rd-btn-cancel';
          cancelBtn.textContent = cancelText;
          cancelBtn.onclick = () => close(mode === 'prompt' ? null : false);
          actions.appendChild(cancelBtn);
        }

        const okBtn = document.createElement('button');
        okBtn.type = 'button';
        okBtn.className = `rd-btn rd-btn-primary ${type === 'success' || type === 'error' ? type : ''}`;
        okBtn.textContent = confirmText;
        okBtn.onclick = () => close(mode === 'prompt' ? inputEl.value : true);
        actions.appendChild(okBtn);

        card.appendChild(actions);
        backdrop.appendChild(card);
        document.body.appendChild(backdrop);

        backdrop.addEventListener('click', (e) => {
          if (e.target === backdrop) {
            close(mode === 'confirm' ? false : (mode === 'prompt' ? null : true));
          }
        });

        function onKey(e) {
          if (e.key === 'Escape') {
            close(mode === 'confirm' ? false : (mode === 'prompt' ? null : true));
          } else if (e.key === 'Enter') {
            e.preventDefault();
            close(mode === 'prompt' ? inputEl.value : true);
          }
        }
        document.addEventListener('keydown', onKey);

        requestAnimationFrame(() => {
          backdrop.classList.add('open');
          if (inputEl) inputEl.focus();
          else okBtn.focus();
        });
      });
    }

    return {
      alert: (opts) => open(typeof opts === 'string' ? { message: opts, mode: 'alert' } : { ...opts, mode: 'alert' }),
      confirm: (opts) => open(typeof opts === 'string' ? { message: opts, mode: 'confirm' } : { ...opts, mode: 'confirm' }),
      prompt: (opts) => open(typeof opts === 'string' ? { message: opts, mode: 'prompt' } : { ...opts, mode: 'prompt' })
    };
  })();

  window.RoleaDialog = RoleaDialog;

  // ==========================================
  // FLOATING LIVE SUPPORT & FAQ DRAWER WIDGET
  // ==========================================
  const RoleaSupport = (() => {
    let settingsCache = { telegram_handle: 'Rothzz3', support_widget_enabled: true };

    function ensureSupportStyles() {
      if (document.getElementById('rolea-support-styles')) return;
      const st = document.createElement('style');
      st.id = 'rolea-support-styles';
      st.textContent = `
        /* Floating Support Trigger Bubble - Circular Telegram Button */
        #rolea-support-bubble {
          position: fixed;
          bottom: 24px;
          right: 22px;
          z-index: 99998;
          width: 52px;
          height: 52px;
          border-radius: 50%;
          background: linear-gradient(135deg, #2AABEE 0%, #229ED9 100%);
          color: #ffffff;
          box-shadow: 0 6px 20px rgba(34, 158, 217, 0.45), 0 0 0 1px rgba(255, 255, 255, 0.25) inset;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
          user-select: none;
        }
        #rolea-support-bubble:hover {
          transform: translateY(-3px) scale(1.08);
          box-shadow: 0 10px 26px rgba(34, 158, 217, 0.6);
        }
        #rolea-support-bubble .tg-icon-wrap {
          position: relative;
          width: 100%;
          height: 100%;
          display: flex;
          align-items: center;
          justify-content: center;
        }
        #rolea-support-bubble .tg-icon-wrap svg {
          width: 27px;
          height: 27px;
          transform: translate(-1.5px, 0.5px);
        }
        #rolea-support-bubble .online-dot {
          position: absolute;
          top: 1px;
          right: 1px;
          width: 12px;
          height: 12px;
          background: #10b981;
          border: 2.5px solid #ffffff;
          border-radius: 50%;
          box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.4);
          animation: rSupportPulse 2s infinite;
        }
        @keyframes rSupportPulse {
          0% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.6); }
          70% { box-shadow: 0 0 0 6px rgba(16, 185, 129, 0); }
          100% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
        }
        @media (max-width: 640px) {
          #rolea-support-bubble {
            bottom: 78px;
            right: 16px;
            width: 48px;
            height: 48px;
          }
          #rolea-support-bubble .tg-icon-wrap svg {
            width: 24px;
            height: 24px;
          }
          #rolea-support-bubble .online-dot {
            width: 11px;
            height: 11px;
            top: 0px;
            right: 0px;
          }
        }

        /* Drawer Overlay */
        #rolea-support-overlay {
          position: fixed;
          inset: 0;
          z-index: 999999;
          background: rgba(15, 23, 42, 0.48);
          backdrop-filter: blur(5px);
          -webkit-backdrop-filter: blur(5px);
          opacity: 0;
          visibility: hidden;
          transition: opacity 0.26s ease, visibility 0.26s;
          display: flex;
          justify-content: flex-end;
          align-items: flex-end;
          font-family: 'Plus Jakarta Sans', 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        }
        #rolea-support-overlay.open {
          opacity: 1;
          visibility: visible;
        }

        /* Drawer Panel */
        #rolea-support-drawer {
          width: 100%;
          max-width: 410px;
          height: 100%;
          max-height: 100vh;
          background: #ffffff;
          display: flex;
          flex-direction: column;
          transform: translateX(100%);
          transition: transform 0.32s cubic-bezier(0.16, 1, 0.3, 1);
          box-shadow: -10px 0 35px rgba(15, 23, 42, 0.2);
          overflow: hidden;
        }
        #rolea-support-overlay.open #rolea-support-drawer {
          transform: translateX(0);
        }
        @media (max-width: 640px) {
          #rolea-support-drawer {
            max-width: 100%;
            height: 88vh;
            border-top-left-radius: 24px;
            border-top-right-radius: 24px;
            transform: translateY(100%);
          }
          #rolea-support-overlay.open #rolea-support-drawer {
            transform: translateY(0);
          }
        }

        /* Drawer Components */
        .rsd-header {
          padding: 20px 22px;
          background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%);
          color: #ffffff;
          display: flex;
          align-items: center;
          justify-content: space-between;
          position: relative;
        }
        .rsd-close-btn {
          width: 32px;
          height: 32px;
          border-radius: 50%;
          background: rgba(255, 255, 255, 0.18);
          border: none;
          color: #ffffff;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 16px;
          transition: background 0.15s;
        }
        .rsd-close-btn:hover { background: rgba(255, 255, 255, 0.3); }

        .rsd-body {
          flex: 1;
          overflow-y: auto;
          padding: 20px 22px;
          display: flex;
          flex-direction: column;
          gap: 16px;
        }

        .rsd-contact-card {
          background: #f8fafc;
          border: 1.5px solid #e2e8f0;
          border-radius: 16px;
          padding: 16px;
          text-align: center;
        }
        .rsd-tg-btn {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 9px;
          width: 100%;
          padding: 12px 18px;
          background: linear-gradient(135deg, #0088cc 0%, #0077b6 100%);
          color: #ffffff;
          border-radius: 12px;
          font-weight: 800;
          font-size: 13.5px;
          text-decoration: none;
          box-shadow: 0 4px 14px rgba(0, 136, 204, 0.35);
          transition: transform 0.15s;
          box-sizing: border-box;
          margin-top: 10px;
        }
        .rsd-tg-btn:hover { transform: translateY(-1.5px); }

        .rsd-quick-order {
          background: #f1f5f9;
          border-radius: 14px;
          padding: 14px;
        }
        .rsd-order-input-wrap {
          display: flex;
          gap: 8px;
          margin-top: 8px;
        }
        .rsd-order-input {
          flex: 1;
          padding: 9px 12px;
          border: 1.5px solid #cbd5e1;
          border-radius: 10px;
          font-size: 13px;
          font-family: inherit;
          outline: none;
          background: #ffffff;
          box-sizing: border-box;
        }
        .rsd-order-btn {
          padding: 9px 14px;
          background: #0f172a;
          color: #ffffff;
          border: none;
          border-radius: 10px;
          font-weight: 700;
          font-size: 12.5px;
          cursor: pointer;
        }

        /* FAQ Accordion */
        .rsd-faq-item {
          border: 1px solid #e2e8f0;
          border-radius: 12px;
          overflow: hidden;
          background: #ffffff;
          transition: border-color 0.15s;
        }
        .rsd-faq-item.active {
          border-color: #0284c7;
        }
        .rsd-faq-q {
          padding: 12px 14px;
          font-weight: 700;
          font-size: 13px;
          color: #0f172a;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 8px;
          user-select: none;
          background: #fcfcfd;
        }
        .rsd-faq-a {
          display: none;
          padding: 10px 14px 14px;
          font-size: 12.5px;
          color: #475569;
          line-height: 1.55;
          border-top: 1px solid #f1f5f9;
          background: #ffffff;
        }
        .rsd-faq-item.active .rsd-faq-a {
          display: block;
        }
      `;
      document.head.appendChild(st);
    }

    function buildSupportHtml(handle, user) {
      const safeHandle = (handle || 'Rothzz3').replace(/^@/, '');
      const greeting = user && user.username
        ? encodeURIComponent(`សួស្តី Admin @${safeHandle}! ខ្ញុំឈ្មោះ @${user.username} ពី Rolea Topup។ ខ្ញុំត្រូវការជំនួយទាក់ទងនឹង៖ `)
        : encodeURIComponent(`សួស្តី Admin @${safeHandle}! ខ្ញុំជាភ្ញៀវ Rolea Topup ត្រូវការជំនួយទាក់ទងនឹង៖ `);
      const tgUrl = `https://t.me/${safeHandle}?text=${greeting}`;

      return `
        <div id="rolea-support-bubble" onclick="window.RoleaSupport.openSupport()" title="Telegram Support 24/7" aria-label="Telegram Support">
          <div class="tg-icon-wrap">
            <svg width="27" height="27" viewBox="0 0 24 24" fill="currentColor">
              <path d="M20.665 3.717l-17.73 6.837c-1.21.486-1.203 1.161-.222 1.462l4.552 1.42 10.532-6.645c.498-.303.953-.14.579.192l-8.533 7.701h-.002l-.313 4.674c.458 0 .66-.21.916-.457l2.199-2.138 4.574 3.379c.843.464 1.45.225 1.66-.782l2.996-14.116c.307-1.23-.47-1.787-1.208-1.527z"/>
            </svg>
            <span class="online-dot"></span>
          </div>
        </div>

        <div id="rolea-support-overlay" onclick="if(event.target===this) window.RoleaSupport.closeSupport()">
          <div id="rolea-support-drawer">
            <div class="rsd-header">
              <div style="display:flex;align-items:center;gap:11px">
                <div style="width:38px;height:38px;border-radius:12px;background:rgba(255,255,255,0.2);display:flex;align-items:center;justify-content:center;color:#ffffff">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                  </svg>
                </div>
                <div>
                  <div style="font-weight:800;font-size:15px;letter-spacing:0.2px">Rolea Support 24/7</div>
                  <div style="font-size:11.5px;opacity:0.9;display:flex;align-items:center;gap:5px">
                    <span style="width:7px;height:7px;border-radius:50%;background:#4ade80;display:inline-block"></span>
                    <span>Admin Online (ឆ្លើយតបរហ័ស)</span>
                  </div>
                </div>
              </div>
              <button class="rsd-close-btn" onclick="window.RoleaSupport.closeSupport()" aria-label="Close">✕</button>
            </div>

            <div class="rsd-body">
              <!-- Contact Card -->
              <div class="rsd-contact-card">
                <div style="font-size:13px;font-weight:700;color:#0f172a">ត្រូវការជំនួយផ្ទាល់?</div>
                <div style="font-size:12px;color:#64748b;margin:3px 0 10px">ឆាតមកកាន់ក្រុមការងារ Admin តាម Telegram ឆ្លើយតបក្នុង ១-៥ នាទី</div>
                <a href="${tgUrl}" target="_blank" rel="noopener noreferrer" class="rsd-tg-btn">
                  <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3"><path d="M21 3L10 14"/><path d="M21 3l-7 18-4-7-7-4z"/></svg>
                  <span>ឆាតជាមួយ Admin (@${safeHandle})</span>
                </a>
                <a href="https://t.me/RothzStore_bot" target="_blank" rel="noopener noreferrer" class="rsd-tg-btn" style="margin-top:8px;background:linear-gradient(135deg, #0284c7 0%, #0369a1 100%);box-shadow:0 4px 14px rgba(2,132,199,0.35)">
                  <svg width="17" height="17" viewBox="0 0 24 24" fill="currentColor"><path d="M20.665 3.717l-17.73 6.837c-1.21.486-1.203 1.161-.222 1.462l4.552 1.42 10.532-6.645c.498-.303.953-.14.579.192l-8.533 7.701h-.002l-.313 4.674c.458 0 .66-.21.916-.457l2.199-2.138 4.574 3.379c.843.464 1.45.225 1.66-.782l2.996-14.116c.307-1.23-.47-1.787-1.208-1.527z"/></svg>
                  <span>បើក Telegram Bot (@RothzStore_bot)</span>
                </a>
              </div>

              <!-- Quick Order Tracker -->
              <div class="rsd-quick-order">
                <div style="font-size:12.5px;font-weight:800;color:#0f172a">ពិនិត្យស្ថានភាពកុម្ម៉ង់ (Track Order)</div>
                <div class="rsd-order-input-wrap">
                  <input type="text" id="rsd-order-query" class="rsd-order-input" placeholder="ឧ. PR1234567..." onkeydown="if(event.key==='Enter') window.RoleaSupport.trackOrderFromDrawer()">
                  <button type="button" class="rsd-order-btn" onclick="window.RoleaSupport.trackOrderFromDrawer()">ពិនិត្យ</button>
                </div>
              </div>

              <!-- FAQs -->
              <div>
                <div style="font-size:13px;font-weight:800;color:#0f172a;margin-bottom:10px">សំណួរដែលសួរញឹកញាប់ (FAQs)</div>
                <div style="display:flex;flex-direction:column;gap:8px">
                  <div class="rsd-faq-item active" onclick="this.classList.toggle('active')">
                    <div class="rsd-faq-q">
                      <span>តើទិញ Robux រួចរង់ចាំប៉ុន្មាននាទី?</span>
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3"><polyline points="6 9 12 15 18 9"/></svg>
                    </div>
                    <div class="rsd-faq-a">
                      ប្រព័ន្ធនឹងធ្វើការបាញ់ Robux ជូនភ្លាមៗក្នុងរយៈពេល <b>១ ទៅ ៥ នាទី</b> បន្ទាប់ពីលោកអ្នកបានស្កេនទូទាត់ជោគជ័យ។
                    </div>
                  </div>

                  <div class="rsd-faq-item" onclick="this.classList.toggle('active')">
                    <div class="rsd-faq-q">
                      <span>តើបង្វិលកង់ Daily Free Spin យ៉ាងដូចម្តេច?</span>
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3"><polyline points="6 9 12 15 18 9"/></svg>
                    </div>
                    <div class="rsd-faq-a">
                      គ្រាន់តែចុះឈ្មោះគណនី Rolea Account និង Sign In ចូល លោកអ្នកអាចចុចបង្វិលយករង្វាន់ Robux ដោយឥតគិតថ្លៃបាន <b>១ ដងរៀងរាល់ ២៤ ម៉ោង</b>!
                    </div>
                  </div>

                  <div class="rsd-faq-item" onclick="this.classList.toggle('active')">
                    <div class="rsd-faq-q">
                      <span>ចុះប្រសិនបើ Order ត្រូវបាន Refund?</span>
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3"><polyline points="6 9 12 15 18 9"/></svg>
                    </div>
                    <div class="rsd-faq-a">
                      ទឹកប្រាក់នឹងត្រូវបាន <b>បង្វិលសងចូលក្នុង Rolea Wallet របស់អ្នក ១០០% ដោយស្វ័យប្រវត្តិភ្លាមៗ</b> ហើយប្រព័ន្ធនឹង Auto-Login ចូលគណនីជូនអ្នកតែម្ដង។
                    </div>
                  </div>

                  <div class="rsd-faq-item" onclick="this.classList.toggle('active')">
                    <div class="rsd-faq-q">
                      <span>តើត្រូវបញ្ចូលលុយចូល Wallet យ៉ាងដូចម្តេច?</span>
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3"><polyline points="6 9 12 15 18 9"/></svg>
                    </div>
                    <div class="rsd-faq-a">
                      ចុចលើរូបកាបូបលុយនៅខាងលើជ្រើសរើសចំនួនទឹកប្រាក់ ហើយស្កេន ABA KHQR នោះលុយនឹងចូលក្នុង Rolea Wallet ភ្លាមៗតែម្ដង។
                    </div>
                  </div>
                </div>
              </div>

              <!-- Trust footer -->
              <div style="margin-top:auto;padding-top:12px;border-top:1px solid #f1f5f9;text-align:center;font-size:11.5px;color:#94a3b8">
                ដំណើរការស្វ័យប្រវត្ត ២៤ ម៉ោង / ៧ ថ្ងៃ • ទំនុកចិត្ត ១០០%
              </div>
            </div>
          </div>
        </div>
      `;
    }

    async function init() {
      // Don't mount in admin panel
      if (window.location.pathname.startsWith('/admin')) return;

      ensureSupportStyles();
      try {
        const res = await fetch('/api/settings');
        if (res.ok) {
          const j = await res.json();
          if (j.telegram_handle) settingsCache.telegram_handle = j.telegram_handle;
          if (j.support_widget_enabled !== undefined) settingsCache.support_widget_enabled = !!j.support_widget_enabled;

          // Real-time Store Logo & Branding Sync across all pages
          const logoUrl = j.store_logo || j.logo;
          if (logoUrl) {
            document.querySelectorAll('.brand-logo').forEach(img => {
              if (img.getAttribute('src') !== logoUrl) img.src = logoUrl;
            });
          }
          if (j.store_name) {
            document.querySelectorAll('.brand-name').forEach(el => {
              el.textContent = j.store_name;
            });
          }
        }
      } catch (e) {}

      if (!settingsCache.support_widget_enabled) return;

      let el = document.getElementById('rolea-support-container');
      if (!el) {
        el = document.createElement('div');
        el.id = 'rolea-support-container';
        document.body.appendChild(el);
      }
      el.innerHTML = buildSupportHtml(settingsCache.telegram_handle, currentUser);
    }

    function openSupport() {
      const ov = document.getElementById('rolea-support-overlay');
      if (ov) ov.classList.add('open');
    }

    function closeSupport() {
      const ov = document.getElementById('rolea-support-overlay');
      if (ov) ov.classList.remove('open');
    }

    function trackOrderFromDrawer() {
      const inp = document.getElementById('rsd-order-query');
      if (!inp) return;
      const val = inp.value.trim().lstrip ? inp.value.trim().lstrip('#') : inp.value.trim().replace(/^#/, '');
      if (val) {
        window.location.assign('/check-order?order_id=' + encodeURIComponent(val));
      }
    }

    return {
      init,
      openSupport,
      closeSupport,
      trackOrderFromDrawer
    };
  })();

  window.RoleaSupport = RoleaSupport;

  // Export API
  window.RoleaAuth = {
    handleForgotSubmit,
    getUser: () => currentUser,
    setCurrentUser: (u) => {
      currentUser = u;
      setCachedUser(u);
      try { renderNavbar(); } catch(e) {}
      notifyAuthReady();
    },
    getToken,
    getAuthHeaders,
    checkCurrentUser,
    refreshUser: checkCurrentUser,
    openAuthModal,
    openLoginModal: () => openAuthModal('login'),
    openWalletModal,
    loginWithGoogle,
    executeGoogleAuth,
    handleCustomGoogle,
    selectTopupAmt,
    createWalletDeposit,
    backToDepositAmount,
    switchAuthTab,
    handleLogin,
    handleRegister,
    toggleUserMenu,
    closeModals,
    logout
  };

  // Instant Fast Render from local state (Prevents blank navbar layout shift)
  function initFastRender() {
    try {
      const t = getToken();
      const cached = t ? getCachedUser() : null;
      if (cached) {
        currentUser = cached;
        renderNavbar();
      } else if (!t) {
        currentUser = null;
        renderNavbar();
      }
    } catch(e) {}
  }

  if (document.readyState !== 'loading') {
    initFastRender();
  } else {
    document.addEventListener('DOMContentLoaded', initFastRender, { once: true });
  }

  // Auto initialize on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      checkCurrentUser();
      try { RoleaSupport.init(); } catch(e) {}
    });
  } else {
    checkCurrentUser();
    try { RoleaSupport.init(); } catch(e) {}
  }
})();
