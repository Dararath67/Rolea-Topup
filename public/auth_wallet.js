/**
 * Rolea Topup - Customer Authentication, Wallet & Balance Manager
 */
(function() {
  let currentUser = null;
  const TOKEN_KEY = 'rolea_token';

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
    .topup-amt-btn {
      position: relative; padding: 13px 8px; border: 1.5px solid #e2e8f0; border-radius: 14px;
      font-size: 14.5px; font-weight: 800; text-align: center; cursor: pointer;
      background: #f8fafc; color: #0f172a; transition: all 0.18s cubic-bezier(0.16, 1, 0.3, 1);
      font-variant-numeric: tabular-nums;
    }
    .topup-amt-btn:hover { border-color: #94a3b8; background: #ffffff; transform: translateY(-1px); box-shadow: 0 4px 12px rgba(15, 23, 42, 0.06); }
    .topup-amt-btn.selected {
      border-color: #10b981; background: #ecfdf5; color: #065f46;
      box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.14), 0 6px 14px -4px rgba(16, 185, 129, 0.22);
    }
    .wallet-balance-card {
      position: relative; overflow: hidden;
      background: linear-gradient(135deg, #064e3b 0%, #047857 55%, #059669 100%);
      border-radius: 18px; padding: 18px 20px;
      display: flex; align-items: center; justify-content: space-between;
      margin-bottom: 20px; color: #ffffff;
      box-shadow: 0 14px 28px -10px rgba(6, 78, 59, 0.45), inset 0 1px 0 rgba(255, 255, 255, 0.18);
    }
    .wallet-balance-card::after {
      content: ''; position: absolute; right: -26px; top: -28px;
      width: 110px; height: 110px; border-radius: 50%;
      background: radial-gradient(circle, rgba(255,255,255,0.18) 0%, rgba(255,255,255,0) 70%);
      pointer-events: none;
    }
    .btn-wallet-cta {
      width: 100%; padding: 13px 16px;
      background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
      color: #ffffff; border: none; border-radius: 14px;
      font-size: 14px; font-weight: 800; cursor: pointer;
      display: flex; align-items: center; justify-content: center; gap: 8px;
      box-shadow: 0 10px 22px -6px rgba(37, 99, 235, 0.45);
      transition: transform 0.16s ease, box-shadow 0.16s ease, opacity 0.16s ease;
    }
    .btn-wallet-cta:hover { transform: translateY(-1px); box-shadow: 0 14px 26px -6px rgba(37, 99, 235, 0.55); }
    .btn-wallet-cta:active { transform: scale(0.99); }
    .btn-wallet-cta:disabled { opacity: 0.7; cursor: wait; transform: none; }

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
    const t = getToken();
    if (!t) {
      currentUser = null;
      renderNavbar();
      return;
    }
    try {
      const res = await fetch('/api/auth/me', { headers: { 'Authorization': 'Bearer ' + t } });
      const j = await res.json();
      if (res.ok && j.ok && j.user) {
        currentUser = j.user;
      } else {
        currentUser = null;
        setToken(null);
      }
    } catch (e) {
      console.warn('Auth check offline');
    }
    renderNavbar();
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
    const mobileActions = document.querySelector('.app-header .header-actions');
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
        closeModals();
        renderNavbar();
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
        closeModals();
        renderNavbar();
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
        const gModal = document.getElementById('rolea-google-modal');
        if (gModal) gModal.remove();
        closeModals();
        renderNavbar();
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
      <div class="rolea-modal-card" style="max-width:420px;border-radius:24px;box-shadow:0 28px 60px -15px rgba(15,23,42,0.32)">
        <div class="rolea-modal-head" style="padding:20px 22px 16px;border-bottom:1px solid #f1f5f9">
          <div style="display:flex;align-items:center;gap:12px">
            <div style="width:40px;height:40px;border-radius:12px;background:#eff6ff;color:#2563eb;display:flex;align-items:center;justify-content:center;flex-shrink:0;border:1px solid #dbeafe">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12V7H5a2 2 0 0 1 0-4h14v4"/><path d="M3 5v14a2 2 0 0 0 2 2h16v-5"/><path d="M18 12a2 2 0 0 0 0 4h4v-4z"/></svg>
            </div>
            <div>
              <h3 style="margin:0;font-size:17px;font-weight:800;color:#0f172a;letter-spacing:-0.01em">Rolea Customer Wallet</h3>
              <span style="font-size:12px;color:#64748b;font-weight:500">Instant top-up &amp; 1-click checkout</span>
            </div>
          </div>
          <button class="rolea-modal-close" onclick="window.RoleaAuth.closeModals()" aria-label="Close">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>
        <div class="rolea-modal-body" style="padding:20px 22px 22px">
          <div class="wallet-balance-card">
            <div>
              <div style="font-size:11px;font-weight:700;color:rgba(236,253,245,0.85);text-transform:uppercase;letter-spacing:0.6px;margin-bottom:4px">Available Balance</div>
              <div style="font-size:28px;font-weight:900;letter-spacing:-0.02em;font-variant-numeric:tabular-nums" id="wallet-modal-cur-bal">$${Number(currentUser.balance || 0).toFixed(2)} <span style="font-size:14px;font-weight:700;opacity:0.85">USD</span></div>
            </div>
            <div style="display:flex;flex-direction:column;align-items:flex-end;gap:6px">
              <div style="width:42px;height:42px;border-radius:12px;background:rgba(255,255,255,0.16);backdrop-filter:blur(4px);display:flex;align-items:center;justify-content:center;color:#ffffff">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="5" width="20" height="14" rx="2"/><line x1="2" y1="10" x2="22" y2="10"/></svg>
              </div>
              <span style="font-size:10px;font-weight:700;background:rgba(255,255,255,0.16);padding:2px 8px;border-radius:999px;letter-spacing:0.3px">KHQR READY</span>
            </div>
          </div>

          <div id="wallet-step-select">
            <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px">
              <label style="font-size:12.5px;font-weight:700;color:#334155">Select Deposit Amount (USD)</label>
              <span style="font-size:11px;font-weight:600;color:#64748b">Min. $0.50</span>
            </div>
            <div class="topup-grid">
              <div class="topup-amt-btn selected" onclick="window.RoleaAuth.selectTopupAmt(1.00, this)">$1.00</div>
              <div class="topup-amt-btn" onclick="window.RoleaAuth.selectTopupAmt(2.00, this)">$2.00</div>
              <div class="topup-amt-btn" onclick="window.RoleaAuth.selectTopupAmt(5.00, this)">$5.00</div>
              <div class="topup-amt-btn" onclick="window.RoleaAuth.selectTopupAmt(10.00, this)">$10.00</div>
              <div class="topup-amt-btn" onclick="window.RoleaAuth.selectTopupAmt(20.00, this)">$20.00</div>
              <div class="topup-amt-btn" onclick="window.RoleaAuth.selectTopupAmt('custom', this)">Custom</div>
            </div>

            <div id="wallet-custom-input-box" style="display:none;margin-bottom:14px">
              <label style="display:block;font-size:12px;font-weight:700;color:#475569;margin-bottom:6px">Custom Amount ($ USD)</label>
              <div style="position:relative">
                <span style="position:absolute;left:14px;top:50%;transform:translateY(-50%);font-weight:800;color:#64748b;font-size:15px">$</span>
                <input type="number" id="wallet-custom-amt" step="0.5" min="0.5" value="15.00" style="width:100%;padding:11px 14px 11px 28px;border:1.5px solid #cbd5e1;border-radius:12px;font-size:15px;font-weight:700;box-sizing:border-box;outline:none">
              </div>
            </div>

            <button id="btn-generate-wallet-qr" class="btn-wallet-cta" onclick="window.RoleaAuth.createWalletDeposit()">
              <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><path d="M14 14h3v3h-3z"/><path d="M17 17h4v4h-4z"/><path d="M21 14v.01"/><path d="M14 21v.01"/></svg>
              Generate ABA KHQR Deposit QR
            </button>
          </div>

          <div id="wallet-step-qr" style="display:none;text-align:center">
            <div style="font-size:13px;font-weight:700;color:#334155;margin-bottom:6px">Scan with ABA Mobile or any KHQR Bank</div>
            <div style="display:inline-block;padding:4px 14px;border-radius:999px;background:#eff6ff;color:#1d4ed8;font-size:18px;font-weight:900;border:1px solid #dbeafe" id="wallet-qr-amount">$1.00 USD</div>
            <div style="margin:14px auto;width:210px;height:210px;padding:10px;border-radius:18px;border:1.5px solid #e2e8f0;background:#fff;box-shadow:0 10px 25px -10px rgba(15,23,42,0.12);display:flex;align-items:center;justify-content:center;box-sizing:border-box">
              <img id="wallet-qr-img" src="" alt="KHQR" style="width:100%;height:100%;object-fit:contain;border-radius:8px">
            </div>
            <div style="font-size:12.5px;font-weight:600;color:#475569;display:flex;align-items:center;justify-content:center;gap:7px">
              <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#10b981;animation:pulse 1.5s infinite"></span>
              Waiting for KHQR payment confirmation…
            </div>
            <div style="margin-top:16px;display:flex;gap:10px">
              <a id="wallet-aba-deeplink" href="#" class="btn-wallet-cta" style="text-decoration:none;display:none;flex:1">Open ABA App</a>
              <button class="btn-rolea-submit" style="margin-top:0;background:#f1f5f9;color:#334155;flex:1;border-radius:14px" onclick="window.RoleaAuth.backToDepositAmount()">Back</button>
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

        // Poll order status
        if (walletPollingInterval) clearInterval(walletPollingInterval);
        walletPollingInterval = setInterval(async () => {
          try {
            const stRes = await fetch(`/api/order-status/${j.order_id}`);
            const stData = await stRes.json();
            if (stData.ok && (stData.paid || stData.status === 'completed')) {
              clearInterval(walletPollingInterval);
              await checkCurrentUser();
              closeModals();
              await RoleaDialog.alert({
                title: 'Payment Confirmed!',
                message: `$${Number(amt).toFixed(2)} USD has been added to your wallet!`,
                type: 'success',
                confirmText: 'Done'
              });
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
    document.querySelectorAll('.rolea-modal-backdrop').forEach(m => m.remove());
    document.querySelectorAll('.user-menu-popover').forEach(p => p.classList.remove('active'));
  }

  function logout() {
    setToken(null);
    currentUser = null;
    closeModals();
    renderNavbar();
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

  // Export API
  window.RoleaAuth = {
    handleForgotSubmit,
    getUser: () => currentUser,
    getToken,
    getAuthHeaders,
    checkCurrentUser,
    openAuthModal,
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

  // Auto initialize on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', checkCurrentUser);
  } else {
    checkCurrentUser();
  }
})();
