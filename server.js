const express = require('express');
const path = require('path');
const fs = require('fs');

const app = express();
const PUBLIC_DIR = path.join(__dirname, 'public');
const APSARA_BASE = (process.env.APSARA_API_URL || 'http://51.81.90.228:35507').replace(/\/+$/, '');

// Forward /api/* requests cleanly to Apsara Hosting Python FastAPI backend
app.use('/api', async (req, res) => {
  try {
    const targetUrl = APSARA_BASE + req.originalUrl;
    const headers = {};
    for (const [k, v] of Object.entries(req.headers)) {
      const lk = k.toLowerCase();
      if (['host', 'connection', 'content-length', 'transfer-encoding'].includes(lk)) continue;
      if (v !== undefined) headers[k] = Array.isArray(v) ? v.join(', ') : String(v);
    }
    const clientIp = req.headers['x-forwarded-for'] || req.socket.remoteAddress || '';
    if (clientIp && !headers['x-forwarded-for']) {
      headers['x-forwarded-for'] = String(clientIp);
    }

    const hasBody = !['GET', 'HEAD'].includes(req.method.toUpperCase());
    let bodyBuf = undefined;
    if (hasBody) {
      const chunks = [];
      for await (const chunk of req) chunks.push(chunk);
      if (chunks.length > 0) bodyBuf = Buffer.concat(chunks);
    }

    const upstream = await fetch(targetUrl, {
      method: req.method,
      headers,
      body: bodyBuf,
      redirect: 'manual',
    });

    res.status(upstream.status);
    upstream.headers.forEach((val, key) => {
      const lk = key.toLowerCase();
      if (['transfer-encoding', 'content-encoding', 'content-length', 'connection'].includes(lk)) return;
      if (lk === 'set-cookie') return;
      res.setHeader(key, val);
    });
    if (typeof upstream.headers.getSetCookie === 'function') {
      const cookies = upstream.headers.getSetCookie();
      if (cookies && cookies.length) res.setHeader('Set-Cookie', cookies);
    } else {
      const singleCookie = upstream.headers.get('set-cookie');
      if (singleCookie) res.setHeader('Set-Cookie', singleCookie);
    }

    const ab = await upstream.arrayBuffer();
    res.send(Buffer.from(ab));
  } catch (err) {
    res.status(502).json({
      ok: false,
      error: 'Unable to reach Rolea Topup Python API on Apsara Hosting',
      detail: err && err.message ? err.message : String(err),
    });
  }
});

// Serve static assets from public/
app.use(express.static(PUBLIC_DIR, { maxAge: 0 }));

// Fallback for uploaded /media/* stored only on Apsara Hosting
app.use('/media', async (req, res) => {
  try {
    const targetUrl = APSARA_BASE + req.originalUrl;
    const upstream = await fetch(targetUrl);
    if (!upstream.ok) return res.status(upstream.status).end();
    const ct = upstream.headers.get('content-type');
    if (ct) res.setHeader('Content-Type', ct);
    const ab = await upstream.arrayBuffer();
    res.send(Buffer.from(ab));
  } catch (_) {
    res.status(404).end();
  }
});

function sendHtml(res, filename) {
  const fp = path.join(PUBLIC_DIR, filename);
  if (!fs.existsSync(fp)) return res.status(404).send('Not Found');
  res.setHeader('Cache-Control', 'no-cache, no-store, must-revalidate, max-age=0');
  res.setHeader('Pragma', 'no-cache');
  res.setHeader('Expires', '0');
  return res.sendFile(fp, { dotfiles: 'allow' });
}

app.get(['/', '/games'], (_req, res) => sendHtml(res, 'index.html'));
app.get('/game/:slug', (_req, res) => sendHtml(res, 'roblox.html'));
app.get('/spin', (_req, res) => sendHtml(res, 'spin.html'));
app.get('/check-order', (_req, res) => sendHtml(res, 'check_order.html'));
app.get(['/my-account', '/profile'], (_req, res) => sendHtml(res, 'my_account.html'));
app.get(['/signin', '/login', '/register'], (_req, res) => sendHtml(res, 'signin.html'));
app.get('/order/success/:orderId', (_req, res) => sendHtml(res, 'receipt.html'));
app.get('/admin', (_req, res) => sendHtml(res, 'admin.html'));
app.get('/admin/login', (_req, res) => sendHtml(res, 'admin_login.html'));

if (require.main === module) {
  const port = Number(process.env.PORT || 3000);
  app.listen(port, '0.0.0.0', () => {
    console.log(`Rolea Topup Vercel/Express Proxy listening on port ${port} -> ${APSARA_BASE}`);
  });
}

module.exports = app;
