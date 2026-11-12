// Real Google OAuth 2.0 Integration & Account Chooser
// Google Cloud Client ID: 220196407393-n5m72vbjquni5g4uuo9bfpdrmmn41c24.apps.googleusercontent.com

(function () {
  const GOOGLE_CLIENT_ID = '220196407393-n5m72vbjquni5g4uuo9bfpdrmmn41c24.apps.googleusercontent.com';

  let googleTokenClient = null;
  let gsiLoaded = false;

  // Load Google Identity Services SDK dynamically
  function loadGoogleSDK() {
    if (document.getElementById('google-gsi-script')) return;
    const script = document.createElement('script');
    script.id = 'google-gsi-script';
    script.src = 'https://accounts.google.com/gsi/client';
    script.async = true;
    script.defer = true;
    script.onload = () => {
      gsiLoaded = true;
      initGoogleClients();
    };
    document.head.appendChild(script);
  }

  function initGoogleClients() {
    if (!window.google || !window.google.accounts) return;

    try {
      // 1. Google OAuth2 Token Client (Opens real accounts.google.com popup with account chooser)
      googleTokenClient = window.google.accounts.oauth2.initTokenClient({
        client_id: GOOGLE_CLIENT_ID,
        scope: 'openid email profile',
        prompt: 'select_account',
        callback: async (tokenResponse) => {
          if (tokenResponse.error) {
            console.warn('Google OAuth response error:', tokenResponse);
            if (tokenResponse.error === 'popup_closed_by_user') return;
            showOriginGuidance(tokenResponse.error_description || tokenResponse.error);
            return;
          }

          if (tokenResponse.access_token) {
            await handleGoogleAccessToken(tokenResponse.access_token);
          }
        },
        error_callback: (err) => {
          console.warn('Google Token Client error:', err);
          if (err && (err.type === 'popup_closed' || err.message === 'Popup window closed')) {
            // User closed the popup window normally, do not display warning banner
            return;
          }
          showOriginGuidance(err.message || 'OAuth error');
        }
      });

      // 2. Google Identity Services ID Token (One Tap / Credential)
      window.google.accounts.id.initialize({
        client_id: GOOGLE_CLIENT_ID,
        callback: handleGoogleIdCredential,
        auto_select: false,
        cancel_on_tap_outside: true
      });
    } catch (e) {
      console.warn('Error initializing Google clients:', e);
    }
  }

  // Handle Google OAuth Access Token
  async function handleGoogleAccessToken(accessToken) {
    try {
      // Fetch verified profile from Google's userinfo API
      const res = await fetch('https://www.googleapis.com/oauth2/v3/userinfo', {
        headers: { Authorization: `Bearer ${accessToken}` }
      });
      const profile = await res.json();

      if (profile && profile.email) {
        await authenticateWithBackend({
          access_token: accessToken,
          email: profile.email,
          name: profile.name || profile.email.split('@')[0],
          avatar: profile.picture || '',
          google_id: profile.sub || ''
        });
      }
    } catch (err) {
      console.error('Error fetching Google userinfo:', err);
      alert('Failed to retrieve Google profile. Please try again.');
    }
  }

  // Handle Google ID Token (Credential)
  async function handleGoogleIdCredential(response) {
    if (response && response.credential) {
      await authenticateWithBackend({ credential: response.credential });
    }
  }

  // Send Google Auth payload to Rolea FastAPI backend
  async function authenticateWithBackend(payload) {
    try {
      const res = await fetch('/api/auth/google', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();

      if (res.ok && data.ok) {
        localStorage.setItem('rolea_token', data.token);
        localStorage.setItem('rolea_user', JSON.stringify(data.user));
        if (payload.email) localStorage.setItem('rolea_google_email', payload.email);

        closeChooser();

        // Redirect
        const urlParams = new URLSearchParams(window.location.search);
        const redirect = urlParams.get('redirect') || '/my-account';
        window.location.replace(redirect);
      } else {
        alert(data.error || 'Google sign-in failed');
      }
    } catch (err) {
      alert('Network error connecting to Rolea server.');
    }
  }

  // Show Guidance if Google Cloud Console requires origin whitelist
  function showOriginGuidance(errDetail) {
    const existing = document.getElementById('google-origin-banner');
    if (existing) existing.remove();

    const banner = document.createElement('div');
    banner.id = 'google-origin-banner';
    banner.style.cssText = `
      position: fixed;
      bottom: 24px;
      left: 50%;
      transform: translateX(-50%);
      background: #1e1f20;
      color: #e3e3e3;
      border: 1.5px solid #f59e0b;
      border-radius: 16px;
      padding: 18px 24px;
      max-width: 580px;
      width: 90%;
      box-shadow: 0 16px 40px rgba(0,0,0,0.5);
      z-index: 100001;
      font-family: sans-serif;
      font-size: 13px;
      line-height: 1.5;
    `;

    banner.innerHTML = `
      <div style="display:flex;align-items:flex-start;gap:12px">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#f59e0b" stroke-width="2.2" style="flex-shrink:0;margin-top:2px"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
        <div style="flex:1">
          <div style="font-weight:700;font-size:14px;color:#fef3c7;margin-bottom:4px">Google Cloud Console Configuration Note</div>
          <div style="color:#d1d5db">In <a href="https://console.cloud.google.com/apis/credentials" target="_blank" style="color:#60a5fa;text-decoration:underline">Google Cloud Console</a>, ensure:</div>
          <div style="margin:6px 0;background:#111;padding:8px 12px;border-radius:8px;font-family:monospace;font-size:12px;color:#93c5fd">
            Authorized JavaScript origins:<br>
            • http://localhost:3000<br>
            • http://localhost
          </div>
          <div style="font-size:12px;color:#9ca3af">Error detail: ${errDetail || 'Origin not yet saved in Google Console'}</div>
        </div>
        <button onclick="this.closest('#google-origin-banner').remove()" style="background:transparent;border:none;color:#9ca3af;cursor:pointer;font-size:18px">&times;</button>
      </div>
    `;

    document.body.appendChild(banner);
  }

  // Trigger Real Google Sign In
  function triggerRealGoogleAuth() {
    if (window.google && window.google.accounts && window.google.accounts.oauth2) {
      if (!googleTokenClient) {
        initGoogleClients();
      }
      if (googleTokenClient) {
        // Launches Google's official popup at accounts.google.com
        googleTokenClient.requestAccessToken({ prompt: 'select_account' });
        return;
      }
    }

    // Direct OAuth Redirect URL as standard fallback
    const origin = window.location.origin;
    const redirectUri = encodeURIComponent(`${origin}/api/auth/google/callback`);
    const authUrl = `https://accounts.google.com/o/oauth2/v2/auth?client_id=${GOOGLE_CLIENT_ID}&redirect_uri=${redirectUri}&response_type=token&scope=openid%20profile%20email&prompt=select_account`;

    const popup = window.open(authUrl, 'GoogleAuthPopup', 'width=520,height=620,menubar=no,toolbar=no');
    if (!popup || popup.closed) {
      window.location.href = authUrl;
    }
  }

  // Shared Account Chooser / Dialog fallback
  function renderDialog() {
    // Priority: trigger real Google Sign In popup first
    triggerRealGoogleAuth();
  }

  function closeChooser() {
    const el = document.getElementById('google-account-chooser-overlay');
    if (el) el.remove();
    const banner = document.getElementById('google-origin-banner');
    if (banner) banner.remove();
  }

  // Listen for OAuth postMessage callback
  window.addEventListener('message', async (event) => {
    if (event.origin !== window.location.origin) return;
    if (event.data && event.data.type === 'GOOGLE_AUTH_CALLBACK') {
      const rawHash = String(event.data.hash || '').replace(/^#/, '');
      if (rawHash) {
        const params = new URLSearchParams(rawHash);
        const token = params.get('access_token');
        if (token) {
          await handleGoogleAccessToken(token);
        }
      }
    }
  });

  // Check if page redirected back from Google OAuth with access_token in URL hash
  async function checkUrlHashAuth() {
    if (window.location.hash && window.location.hash.includes('access_token=')) {
      const hash = window.location.hash.substring(1);
      const params = new URLSearchParams(hash);
      const token = params.get('access_token');
      if (token) {
        history.replaceState(null, null, window.location.pathname + window.location.search);
        await handleGoogleAccessToken(token);
      }
    }
  }
  checkUrlHashAuth();

  // Initialize on load
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', loadGoogleSDK);
  } else {
    loadGoogleSDK();
  }

  // Public API
  window.RoleaGoogleChooser = {
    open: triggerRealGoogleAuth,
    triggerRealGoogleAuth: triggerRealGoogleAuth,
    close: closeChooser,
    select: (email, name, avatar) => authenticateWithBackend({ email, name, avatar }),
    clientId: GOOGLE_CLIENT_ID
  };
})();
