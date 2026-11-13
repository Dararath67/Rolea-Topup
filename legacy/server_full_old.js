const express = require('express');
const cors = require('cors');
const QRCode = require('qrcode');
const path = require('path');
const fs = require('fs');
const crypto = require('crypto');

const app = express();
const PORT = process.env.PORT || 3000;

app.use(cors());
app.use(express.json({ limit: '25mb' }));
app.use(express.urlencoded({ extended: true, limit: '25mb' }));

// Serve static directory
const publicDir = path.join(__dirname, 'public');
app.use(express.static(publicDir, { dotfiles: 'allow' }));

// Database persistence paths
const dbPath = path.join(__dirname, 'data', 'orders.json');
const packagesPath = path.join(__dirname, 'data', 'packages.json');
const settingsPath = path.join(__dirname, 'data', 'settings.json');
const gamesPath = path.join(__dirname, 'data', 'games.json');
const usersPath = path.join(__dirname, 'data', 'users.json');
const couponsPath = path.join(__dirname, 'data', 'coupons.json');
const reviewsPath = path.join(__dirname, 'data', 'reviews.json');
const walletTxPath = path.join(__dirname, 'data', 'wallet_transactions.json');

let orders = [];
let packages = [];
let games = {
  roblox: { id: "roblox", name: "Roblox Robux Send", category: "Roblox Robux", kicker: "ROBLOX · ROBUX SEND", unit: "Robux", type: "roblox", enabled: true, logo: "/media/rolea-logo.webp", banner: "/media/roblox-banner.webp", badge: "HOT" },
  mlbb: { id: "mlbb", name: "Mobile Legends: Bang Bang", category: "Mobile Game", kicker: "MOONTON · DIAMONDS", unit: "Diamonds", type: "mlbb", enabled: true, logo: "/media/mlbb-thumb.svg", banner: "/media/banner1.webp", badge: "POPULAR" },
  tiktok: { id: "tiktok", name: "TikTok SMM Services", category: "Social Media", kicker: "TIKTOK · FOLLOWERS & LIKES", unit: "Followers", type: "smm", enabled: true, logo: "/media/tiktok-thumb.svg", banner: "/media/banner1.webp", badge: "PROMO" },
  freefire: { id: "freefire", name: "Free Fire Diamonds", category: "Mobile Game", kicker: "GARENA · DIAMONDS", unit: "Diamonds", type: "freefire", enabled: true, logo: "/media/freefire-thumb.svg", banner: "/media/banner1.webp", badge: "FAST" }
};
let settings = {
  store_name: "Rolea Topup",
  telegram_handle: "putireach",
  khqr_merchant_name: "Rolea",
  khqr_account: "bakong@rolea",
  khqrpay_api_key: "sk_52b3f4ed679f5de854a6dfae6a500a368a6e11e77670c8e7",
  khqrpay_base_url: "https://khqrpay.site",
  home_banner: "/media/banner1.webp",
  roblox_banner: "/media/roblox-banner.webp",
  auto_deliver: true,
  telegram_bot_token: (process.env.TELEGRAM_BOT_TOKEN || ""),
  telegram_chat_id: "-5315869838"
};
let users = [];
let coupons = [];
let reviews = [];
let walletTransactions = [];
const sessions = new Map(); // token -> { userId, expiresAt }

try {
  if (fs.existsSync(dbPath)) orders = JSON.parse(fs.readFileSync(dbPath, 'utf8'));
  if (fs.existsSync(packagesPath)) packages = JSON.parse(fs.readFileSync(packagesPath, 'utf8'));
  if (fs.existsSync(settingsPath)) settings = JSON.parse(fs.readFileSync(settingsPath, 'utf8'));
  if (fs.existsSync(gamesPath)) games = JSON.parse(fs.readFileSync(gamesPath, 'utf8'));
  if (fs.existsSync(usersPath)) users = JSON.parse(fs.readFileSync(usersPath, 'utf8'));
  if (fs.existsSync(couponsPath)) coupons = JSON.parse(fs.readFileSync(couponsPath, 'utf8'));
  if (fs.existsSync(reviewsPath)) reviews = JSON.parse(fs.readFileSync(reviewsPath, 'utf8'));
  if (fs.existsSync(walletTxPath)) walletTransactions = JSON.parse(fs.readFileSync(walletTxPath, 'utf8'));
} catch (e) {
  console.error('Error loading data:', e);
}

function saveOrders() {
  try { fs.writeFileSync(dbPath, JSON.stringify(orders, null, 2), 'utf8'); } catch (e) { console.error(e); }
}
function savePackages() {
  try { fs.writeFileSync(packagesPath, JSON.stringify(packages, null, 2), 'utf8'); } catch (e) { console.error(e); }
}
function saveSettings() {
  try { fs.writeFileSync(settingsPath, JSON.stringify(settings, null, 2), 'utf8'); } catch (e) { console.error(e); }
}
function saveGames() {
  try { fs.writeFileSync(gamesPath, JSON.stringify(games, null, 2), 'utf8'); } catch (e) { console.error(e); }
}
function saveUsers() {
  try { fs.writeFileSync(usersPath, JSON.stringify(users, null, 2), 'utf8'); } catch (e) { console.error(e); }
}
function saveCoupons() {
  try { fs.writeFileSync(couponsPath, JSON.stringify(coupons, null, 2), 'utf8'); } catch (e) { console.error(e); }
}
function saveReviews() {
  try { fs.writeFileSync(reviewsPath, JSON.stringify(reviews, null, 2), 'utf8'); } catch (e) { console.error(e); }
}
function saveWalletTx() {
  try { fs.writeFileSync(walletTxPath, JSON.stringify(walletTransactions, null, 2), 'utf8'); } catch (e) { console.error(e); }
}

// User Authentication Helpers
function hashPassword(password) {
  return crypto.createHash('sha256').update(password + 'ROLEA_SECURE_SALT_2026').digest('hex');
}

function getUserFromReq(req) {
  let token = null;
  const authHeader = req.headers.authorization;
  if (authHeader && authHeader.startsWith('Bearer ')) {
    token = authHeader.slice(7).trim();
  } else if (req.headers['x-auth-token']) {
    token = String(req.headers['x-auth-token']).trim();
  } else if (req.headers.cookie) {
    const match = req.headers.cookie.match(/rolea_token=([^;]+)/);
    if (match) token = match[1].trim();
  }
  if (!token) return null;
  const sess = sessions.get(token);
  if (!sess) return null;
  if (sess.expiresAt && sess.expiresAt < Date.now()) {
    sessions.delete(token);
    return null;
  }
  return users.find(u => u.id === sess.userId) || null;
}

// Telegram Bot Alert Function (Alert only when order is paid ready, NO EMOJIS)
async function sendTelegramPaidAlert(order) {
  if (!order || order.telegram_alerted) return;
  order.telegram_alerted = true;
  saveOrders();

  const token = settings.telegram_bot_token || (process.env.TELEGRAM_BOT_TOKEN || '');
  const chatId = settings.telegram_chat_id || '-5315869838';
  if (!token || !chatId) return;

  const g = games[order.game] || {};
  const gameName = g.name || order.game || 'Rolea Topup';
  const customer = order.roblox_username || order.username || order.display_name || 'Customer';
  const amount = Number(order.amount || order.price || 0).toFixed(2);
  const pkgName = order.package || `${order.robux_amount || ''} ${g.unit || 'Units'}`.trim();
  const time = new Date(order.created_at || Date.now()).toLocaleString('en-US', { timeZone: 'Asia/Phnom_Penh' });

  // Formatted text with emojis for Telegram alert
  const message = [
    `🔔 <b>[PAID ORDER NOTIFICATION]</b>`,
    `🏪 <b>Store:</b> ${settings.store_name || 'Rolea Topup'}`,
    `🆔 <b>Order ID:</b> <code>${order.order_id}</code>`,
    `🎮 <b>Game:</b> ${gameName}`,
    `👤 <b>Account:</b> ${customer}`,
    `📦 <b>Package:</b> ${pkgName}`,
    `💵 <b>Amount:</b> $${amount} USD`,
    `💳 <b>Payment Gateway:</b> ABA KHQR`,
    `⚡ <b>Status:</b> PAID - READY FOR FULFILLMENT`,
    `🕒 <b>Time:</b> ${time}`
  ].join('\n');

  try {
    const url = `https://api.telegram.org/bot${token}/sendMessage`;
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        chat_id: chatId,
        text: message,
        parse_mode: 'HTML',
        reply_markup: {
          inline_keyboard: [
            [
              { text: '✅ Complete Order', callback_data: `complete:${order.order_id}` },
              { text: '❌ Reject & Refund', callback_data: `reject:${order.order_id}` }
            ]
          ]
        }
      })
    });
    const j = await res.json();
    if (j && j.ok) {
      console.log(`Telegram paid alert with action buttons sent for order ${order.order_id}`);
    } else {
      console.error('Telegram alert response error:', j);
    }
  } catch (err) {
    console.error('Telegram alert request failed:', err.message);
  }
}

// Telegram Callback Handlers (Admin Complete or Reject & Refund)
async function answerCallbackQuery(token, queryId, text) {
  try {
    await fetch(`https://api.telegram.org/bot${token}/answerCallbackQuery`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ callback_query_id: queryId, text, show_alert: false })
    });
  } catch (e) {}
}

async function editTelegramMessage(token, chatId, messageId, text) {
  try {
    await fetch(`https://api.telegram.org/bot${token}/editMessageText`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        chat_id: chatId,
        message_id: messageId,
        text,
        parse_mode: 'HTML'
      })
    });
  } catch (e) {}
}

async function handleTelegramCallbackQuery(query, token) {
  const queryId = query.id;
  const data = query.data || '';
  const fromId = String(query.from && query.from.id);
  const fromUname = String(query.from && query.from.username || '').toLowerCase();
  const msgChatId = String(query.message && query.message.chat && query.message.chat.id || '');
  const targetChatId = String(settings.telegram_chat_id || '-5315869838');
  const isAdmin = (fromId === '8710759437' || fromId === targetChatId || msgChatId === targetChatId || msgChatId === '-5315869838' || fromUname === 'rothzz3');

  if (!isAdmin) {
    await answerCallbackQuery(token, queryId, 'Unauthorized: Admin action only.');
    return;
  }

  const parts = data.split(':');
  const action = parts[0];
  const orderId = parts[1];

  if (!action || !orderId) {
    await answerCallbackQuery(token, queryId, 'Invalid request data.');
    return;
  }

  const order = orders.find(o => o.order_id === orderId);
  if (!order) {
    await answerCallbackQuery(token, queryId, 'Order not found.');
    return;
  }

  const timeStr = new Date().toLocaleString('en-US', { timeZone: 'Asia/Phnom_Penh' });
  const g = games[order.game] || {};
  const gameName = g.name || order.game || 'Rolea Topup';
  const customer = order.roblox_username || order.username || order.display_name || 'Customer';
  const amount = Number(order.amount || order.price || 0).toFixed(2);
  const pkgName = order.package || `${order.robux_amount || ''} ${g.unit || 'Units'}`.trim();
  const adminName = query.from.username ? `@${query.from.username}` : (query.from.first_name || 'Admin');

  if (action === 'complete') {
    order.paid = true;
    order.delivered = true;
    order.status = 'completed';
    order.step = 'delivered';
    order.label = 'Order fulfilled and confirmed by Admin via Telegram';
    saveOrders();

    await answerCallbackQuery(token, queryId, `✅ Order #${orderId} marked as Completed!`);

    const updatedText = [
      `✅ <b>[ORDER COMPLETED BY ADMIN]</b>`,
      `🏪 <b>Store:</b> ${settings.store_name || 'Rolea Topup'}`,
      `🆔 <b>Order ID:</b> <code>${order.order_id}</code>`,
      `🎮 <b>Game:</b> ${gameName}`,
      `👤 <b>Account:</b> ${customer}`,
      `📦 <b>Package:</b> ${pkgName}`,
      `💵 <b>Amount:</b> $${amount} USD`,
      `🎉 <b>Status:</b> COMPLETED & DELIVERED`,
      `👮 <b>Action By:</b> ${adminName}`,
      `🕒 <b>Action Time:</b> ${timeStr}`
    ].join('\n');

    if (query.message) {
      await editTelegramMessage(token, query.message.chat.id, query.message.message_id, updatedText);
    }
  } else if (action === 'reject') {
    order.status = 'refunded';
    order.step = 'refunded';
    order.delivered = false;
    order.label = 'Order rejected and refunded to customer by Admin';
    saveOrders();

    await answerCallbackQuery(token, queryId, `⚠️ Order #${orderId} Rejected & Refunded!`);

    const updatedText = [
      `❌ <b>[ORDER REJECTED & REFUNDED]</b>`,
      `🏪 <b>Store:</b> ${settings.store_name || 'Rolea Topup'}`,
      `🆔 <b>Order ID:</b> <code>${order.order_id}</code>`,
      `🎮 <b>Game:</b> ${gameName}`,
      `👤 <b>Account:</b> ${customer}`,
      `📦 <b>Package:</b> ${pkgName}`,
      `💵 <b>Amount:</b> $${amount} USD`,
      `🚫 <b>Status:</b> REJECTED & REFUNDED`,
      `👮 <b>Action By:</b> ${adminName}`,
      `🕒 <b>Action Time:</b> ${timeStr}`
    ].join('\n');

    if (query.message) {
      await editTelegramMessage(token, query.message.chat.id, query.message.message_id, updatedText);
    }
  }
}

// Telegram Bot Polling Loop
let telegramOffset = 0;
let isPollingTelegram = false;

async function pollTelegramUpdates() {
  if (isPollingTelegram) return;
  isPollingTelegram = true;

  const token = settings.telegram_bot_token || (process.env.TELEGRAM_BOT_TOKEN || '');
  if (!token) {
    isPollingTelegram = false;
    return;
  }

  try {
    const url = `https://api.telegram.org/bot${token}/getUpdates?offset=${telegramOffset}&timeout=5`;
    const resp = await fetch(url, { signal: AbortSignal.timeout(8000) });
    const j = await resp.json();

    if (j && j.ok && Array.isArray(j.result)) {
      for (const update of j.result) {
        telegramOffset = update.update_id + 1;
        if (update.callback_query) {
          await handleTelegramCallbackQuery(update.callback_query, token);
        }
      }
    }
  } catch (err) {
    // Timeout or network blip; ignore
  } finally {
    isPollingTelegram = false;
  }
}

// Start polling Telegram updates every 3.5 seconds
setInterval(pollTelegramUpdates, 3500);

// Catalog data
const CATALOG = {
  roblox: {
    name: 'Roblox Robux Send',
    type: 'roblox',
    banner: '/media/roblox-banner.webp',
    thumb: '/media/roblox-thumb.webp',
    get packages() {
      return packages.length ? packages : [
        { id: '6aedea450bc5af89ab0ba8b1', robux: 50, price: 0.60, name: '50 Robux', ok: 1, icon: '/media/rolea-logo.webp' },
        { id: '6aee1ad13f2228cb3063790e', robux: 100, price: 1.00, name: '100 Robux', ok: 1, icon: '/media/rolea-logo.webp' }
      ];
    }
  }
};

// Check username or player ID endpoint
app.post('/api/check-id', async (req, res) => {
  const { game, player_id, server_id } = req.body || {};
  const query = String(player_id || '').trim().replace(/^@/, '');

  if (!query) {
    return res.status(400).json({ ok: false, error: 'Please enter a valid username or ID.' });
  }

  if (game === 'roblox') {
    // Attempt real Roblox API if reachable
    try {
      const response = await fetch('https://users.roblox.com/v1/usernames/users', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ usernames: [query], excludeBannedUsers: true }),
        signal: AbortSignal.timeout(3000)
      });
      const data = await response.json();

      if (data && Array.isArray(data.data) && data.data.length > 0) {
        const u = data.data[0];
        let avatar = '';
        try {
          const avRes = await fetch(`https://thumbnails.roblox.com/v1/users/avatar-headshot?userIds=${u.id}&size=150x150&format=Png&isCircular=false`, {
            signal: AbortSignal.timeout(2500)
          });
          const avData = await avRes.json();
          if (avData?.data?.[0]?.imageUrl) {
            avatar = avData.data[0].imageUrl;
          }
        } catch (_) {}

        return res.json({
          ok: true,
          username: u.name,
          display_name: u.displayName || u.name,
          roblox_id: String(u.id),
          avatar: avatar || 'https://tr.rbxcdn.com/30DAY-AvatarHeadshot-150x150-Png/150/150/AvatarHeadshot/Png/noFilter'
        });
      }
    } catch (_) {}

    // Clean, instant simulated player data for testing
    const fakeId = Math.abs(query.split('').reduce((acc, c) => ((acc << 5) - acc) + c.charCodeAt(0), 123456789)) % 900000000 + 100000000;
    return res.json({
      ok: true,
      username: query,
      display_name: query.charAt(0).toUpperCase() + query.slice(1),
      roblox_id: String(fakeId),
      avatar: 'https://tr.rbxcdn.com/30DAY-AvatarHeadshot-150x150-Png/150/150/AvatarHeadshot/Png/noFilter'
    });
  }

  if (game === 'mlbb') {
    if (server_id && !/^\d{3,6}$/.test(server_id)) {
      return res.status(400).json({ ok: false, error: 'Zone ID must be 4 or 5 digits.' });
    }
    return res.json({
      ok: true,
      username: query,
      display_name: 'Mythic Player (' + query + ')',
      server_id: server_id || '2034',
      avatar: '/media/mlbb-thumb.svg'
    });
  }

  if (game === 'tiktok') {
    return res.json({
      ok: true,
      username: query,
      display_name: '@' + query,
      avatar: '/media/tiktok-thumb.svg'
    });
  }

  return res.json({
    ok: true,
    username: query,
    display_name: query
  });
});

// Roblox avatar proxy
app.get('/api/roblox-avatar/:id', async (req, res) => {
  const id = req.params.id;
  try {
    const avRes = await fetch(`https://thumbnails.roblox.com/v1/users/avatar-headshot?userIds=${id}&size=150x150&format=Png&isCircular=false`, {
      signal: AbortSignal.timeout(3000)
    });
    const avData = await avRes.json();
    if (avData?.data?.[0]?.imageUrl) {
      return res.json({ avatar: avData.data[0].imageUrl });
    }
  } catch (_) {}
  res.json({ avatar: 'https://tr.rbxcdn.com/30DAY-AvatarHeadshot-150x150-Png/150/150/AvatarHeadshot/Png/noFilter' });
});

// KHQRPay Gateway Helper Functions
async function createKhqrPayOrder(amount, orderId) {
  const baseUrl = (settings.khqrpay_base_url || 'https://khqrpay.site').replace(/\/+$/, '');
  const apiKey = settings.khqrpay_api_key || 'sk_52b3f4ed679f5de854a6dfae6a500a368a6e11e77670c8e7';

  try {
    const res = await fetch(`${baseUrl}/api/v1/aba/create`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${apiKey}`,
        'X-Api-Key': apiKey,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        amount: Number(amount),
        order_id: String(orderId)
      }),
      signal: AbortSignal.timeout(6000)
    });
    const data = await res.json();
    if (data && (data.ok || data.id)) {
      return data;
    }
    console.warn('[KHQRPay] Create returned non-ok:', data);
  } catch (err) {
    console.error('[KHQRPay] Error creating payment:', err.message);
  }
  return null;
}

async function checkKhqrPayStatus(paymentId) {
  const baseUrl = (settings.khqrpay_base_url || 'https://khqrpay.site').replace(/\/+$/, '');
  const apiKey = settings.khqrpay_api_key || 'sk_52b3f4ed679f5de854a6dfae6a500a368a6e11e77670c8e7';

  try {
    const res = await fetch(`${baseUrl}/api/v1/payment?id=${encodeURIComponent(paymentId)}`, {
      headers: {
        'Authorization': `Bearer ${apiKey}`,
        'X-Api-Key': apiKey
      },
      signal: AbortSignal.timeout(5000)
    });
    const data = await res.json();
    if (data && (data.ok || data.payment)) {
      return data.payment || data;
    }
  } catch (err) {
    console.error('[KHQRPay] Error checking payment status:', err.message);
  }
  return null;
}

// ==========================================
// CUSTOMER AUTHENTICATION & PROFILE APIS
// ==========================================

app.post('/api/auth/register', (req, res) => {
  const { username, email, password } = req.body || {};
  if (!username || typeof username !== 'string' || username.trim().length < 3) {
    return res.status(400).json({ ok: false, error: 'Username must be at least 3 characters' });
  }
  if (!password || typeof password !== 'string' || password.length < 6) {
    return res.status(400).json({ ok: false, error: 'Password must be at least 6 characters' });
  }

  const cleanUsername = username.trim();
  const cleanEmail = (email || '').trim().toLowerCase();

  const exists = users.find(u => u.username.toLowerCase() === cleanUsername.toLowerCase() || (cleanEmail && u.email && u.email.toLowerCase() === cleanEmail));
  if (exists) {
    return res.status(400).json({ ok: false, error: 'Username or email already registered' });
  }

  const newUser = {
    id: 'usr_' + Date.now().toString(36) + Math.random().toString(36).slice(2, 6),
    username: cleanUsername,
    email: cleanEmail,
    password_hash: hashPassword(password),
    balance: 0.00,
    avatar: '/media/rolea-logo.webp',
    created_at: new Date().toISOString()
  };

  users.push(newUser);
  saveUsers();

  const token = crypto.randomBytes(32).toString('hex');
  sessions.set(token, { userId: newUser.id, expiresAt: Date.now() + 30 * 24 * 3600 * 1000 });

  res.json({
    ok: true,
    token,
    user: {
      id: newUser.id,
      username: newUser.username,
      email: newUser.email,
      balance: newUser.balance,
      avatar: newUser.avatar
    }
  });
});

app.post('/api/auth/login', (req, res) => {
  const { username, password } = req.body || {};
  if (!username || !password) {
    return res.status(400).json({ ok: false, error: 'Please enter username and password' });
  }

  const lookup = username.trim().toLowerCase();
  const user = users.find(u => u.username.toLowerCase() === lookup || (u.email && u.email.toLowerCase() === lookup));
  if (!user) {
    return res.status(400).json({ ok: false, error: 'Invalid username or password' });
  }

  const hash = hashPassword(password);
  if (user.password_hash !== hash) {
    return res.status(400).json({ ok: false, error: 'Invalid username or password' });
  }

  const token = crypto.randomBytes(32).toString('hex');
  sessions.set(token, { userId: user.id, expiresAt: Date.now() + 30 * 24 * 3600 * 1000 });

  res.json({
    ok: true,
    token,
    user: {
      id: user.id,
      username: user.username,
      email: user.email,
      balance: user.balance,
      avatar: user.avatar
    }
  });
});

app.get('/api/auth/me', (req, res) => {
  const user = getUserFromReq(req);
  if (!user) {
    return res.json({ ok: false, user: null });
  }
  res.json({
    ok: true,
    user: {
      id: user.id,
      username: user.username,
      email: user.email,
      balance: user.balance,
      avatar: user.avatar
    }
  });
});

app.post('/api/auth/logout', (req, res) => {
  let token = null;
  const authHeader = req.headers.authorization;
  if (authHeader && authHeader.startsWith('Bearer ')) token = authHeader.slice(7).trim();
  else if (req.headers['x-auth-token']) token = String(req.headers['x-auth-token']).trim();
  if (token) sessions.delete(token);
  res.json({ ok: true });
});

app.get('/api/auth/my-orders', (req, res) => {
  const user = getUserFromReq(req);
  if (!user) return res.status(401).json({ ok: false, error: 'Not authenticated' });
  const myOrders = orders.filter(o => o.user_id === user.id || o.roblox_username === user.username);
  res.json({ ok: true, orders: myOrders });
});

// ==========================================
// CUSTOMER WALLET & DEPOSIT APIS
// ==========================================

app.post('/api/wallet/topup', async (req, res) => {
  const user = getUserFromReq(req);
  if (!user) return res.status(401).json({ ok: false, error: 'Please log in to top up your wallet' });

  const amount = Number(req.body?.amount);
  if (isNaN(amount) || amount < 0.50) {
    return res.status(400).json({ ok: false, error: 'Minimum deposit is $0.50 USD' });
  }

  const now = new Date();
  const order_id = 'WLT' + Date.now().toString(36).toUpperCase() + Math.random().toString(36).substring(2, 5).toUpperCase();
  const token = Math.random().toString(36).substring(2) + Math.random().toString(36).substring(2);

  // Call KHQRPay gateway
  const khqrRes = await createKhqrPayOrder(amount, order_id);
  let qr_url = '';
  let khqrpay_id = null;
  let payment_url = '';
  let aba_deeplink = '';
  let expires_at = new Date(now.getTime() + 10 * 60 * 1000).toISOString();

  if (khqrRes && khqrRes.id) {
    khqrpay_id = khqrRes.id;
    qr_url = khqrRes.qr_image || '';
    payment_url = khqrRes.checkout_url || `https://khqrpay.site/pay/${khqrRes.id}`;
    aba_deeplink = khqrRes.aba_deeplink || '';
    if (khqrRes.expires_at) expires_at = new Date(khqrRes.expires_at).toISOString();
  }

  if (!qr_url) {
    const khqrPayload = `00020101021229370016bakong@rolea010108${order_id}520459995303840540${amount.toFixed(2).length < 10 ? '0' + amount.toFixed(2).length : amount.toFixed(2).length}${amount.toFixed(2)}5802KH5911ROLEA TOPUP6010PHNOM PENH62240108${order_id}0708ROLEATOPUP6304`;
    qr_url = await QRCode.toDataURL(khqrPayload, {
      errorCorrectionLevel: 'M',
      margin: 2,
      width: 400,
      color: { dark: '#10234b', light: '#ffffff' }
    });
    payment_url = `https://khqrpay.site/pay/${order_id}`;
  }

  const topupOrder = {
    order_id,
    khqrpay_id,
    token,
    user_id: user.id,
    buyer_account: user.username,
    roblox_username: user.username,
    type: 'wallet_topup',
    product_name: 'Rolea Wallet Top-up',
    product_type: 'wallet',
    package: `$${amount.toFixed(2)} USD Wallet Balance`,
    amount: amount,
    status: 'pending',
    step: 'wait',
    paid: false,
    delivered: false,
    created_at: now.toISOString(),
    expires_at: expires_at,
    payment_url: payment_url,
    aba_deeplink: aba_deeplink,
    qr_url: qr_url,
    label: 'Scan KHQR to deposit into your wallet'
  };

  orders.unshift(topupOrder);
  saveOrders();

  res.json({
    ok: true,
    order_id,
    amount,
    qr_url,
    payment_url,
    aba_deeplink,
    expires_at
  });
});

app.get('/api/wallet/transactions', (req, res) => {
  const user = getUserFromReq(req);
  if (!user) return res.status(401).json({ ok: false, error: 'Not authenticated' });
  const txs = walletTransactions.filter(t => t.user_id === user.id);
  res.json({ ok: true, balance: user.balance, transactions: txs });
});

// ==========================================
// PROMO CODE & VOUCHER APIS
// ==========================================

app.post('/api/promo/apply', (req, res) => {
  const { code, amount } = req.body || {};
  if (!code || typeof code !== 'string') {
    return res.status(400).json({ ok: false, error: 'Please enter a promo code' });
  }
  const orderAmount = Number(amount || 0);
  const cp = coupons.find(c => c.code.toUpperCase() === code.trim().toUpperCase() && c.enabled);
  if (!cp) {
    return res.status(404).json({ ok: false, error: 'Invalid or inactive promo code' });
  }
  if (cp.max_uses && cp.used_count >= cp.max_uses) {
    return res.status(400).json({ ok: false, error: 'Promo code usage limit has been reached' });
  }
  if (orderAmount < (cp.min_spend || 0)) {
    return res.status(400).json({ ok: false, error: `Minimum order of $${Number(cp.min_spend).toFixed(2)} required for this coupon` });
  }

  let discount = cp.type === 'percentage' ? (orderAmount * (cp.value / 100)) : cp.value;
  discount = Math.min(discount, Math.max(0, orderAmount - 0.05));
  discount = Number(discount.toFixed(2));
  const new_amount = Number((orderAmount - discount).toFixed(2));

  res.json({
    ok: true,
    code: cp.code,
    type: cp.type,
    value: cp.value,
    discount: discount,
    new_amount: new_amount,
    description: cp.description || `${cp.value}${cp.type === 'percentage' ? '%' : '$'} discount`
  });
});

// ==========================================
// CUSTOMER REVIEWS & LIVE PROOF APIS
// ==========================================

app.get('/api/reviews', (req, res) => {
  const approvedReviews = reviews.filter(r => r.approved !== false);
  const total = approvedReviews.length;
  const avg = total > 0 ? (approvedReviews.reduce((acc, r) => acc + Number(r.rating || 5), 0) / total) : 5.0;
  res.json({
    ok: true,
    reviews: approvedReviews,
    stats: {
      total: total,
      average_rating: Number(avg.toFixed(1))
    }
  });
});

app.post('/api/reviews/submit', (req, res) => {
  const { order_id, game, username, rating, comment } = req.body || {};
  if (!comment || typeof comment !== 'string' || comment.trim().length < 2) {
    return res.status(400).json({ ok: false, error: 'Please enter a review comment' });
  }

  const numRating = Math.max(1, Math.min(5, parseInt(rating) || 5));
  const cleanUsername = (username || 'Verified Customer').trim();
  const g = games[game] || {};

  const newReview = {
    id: 'rev_' + Date.now().toString(36),
    order_id: (order_id || '').trim(),
    game: game || 'general',
    game_name: g.name || 'Store Top-up',
    username: cleanUsername.length > 3 ? cleanUsername.slice(0, 3) + '***' : cleanUsername,
    rating: numRating,
    comment: comment.trim(),
    created_at: new Date().toISOString(),
    approved: true
  };

  reviews.unshift(newReview);
  if (reviews.length > 500) reviews = reviews.slice(0, 500);
  saveReviews();

  res.json({ ok: true, message: 'Thank you! Your review has been published.', review: newReview });
});

app.get('/api/live-proof', (req, res) => {
  // Return recent paid/completed deliveries
  let liveList = orders
    .filter(o => o.paid && o.type !== 'wallet_topup')
    .slice(0, 15)
    .map(o => {
      const rawName = o.roblox_username || o.username || o.display_name || 'Customer';
      const masked = rawName.length > 3 ? rawName.slice(0, 3) + '***' : rawName + '***';
      return {
        order_id: o.order_id,
        username: masked,
        game: o.product_name || games[o.game]?.name || 'Game Topup',
        package: o.package,
        amount: o.amount,
        time: o.created_at
      };
    });

  if (liveList.length < 5) {
    const defaultSeeds = [
      { order_id: 'PR8912A0', username: 'Vann***', game: 'Roblox Robux Send', package: '800 Robux', amount: 10.00, time: new Date(Date.now() - 3 * 60000).toISOString() },
      { order_id: 'PR7831B2', username: 'Soph***', game: 'TikTok SMM Services', package: '1000 Followers', amount: 6.00, time: new Date(Date.now() - 7 * 60000).toISOString() },
      { order_id: 'PR6543C9', username: 'Kosa***', game: 'Roblox Robux Send', package: '400 Robux', amount: 5.00, time: new Date(Date.now() - 14 * 60000).toISOString() },
      { order_id: 'PR9012D4', username: 'Chan***', game: 'Mobile Legends Diamonds', package: '257 Diamonds', amount: 3.75, time: new Date(Date.now() - 22 * 60000).toISOString() }
    ];
    liveList = [...liveList, ...defaultSeeds];
  }

  res.json({ ok: true, live_proof: liveList });
});

// Create Order endpoint
app.post('/api/create-order', async (req, res) => {
  try {
    const { game, package_id, player_id, server_id, username, checkout_ref, receipt_token, promo_code, payment_method } = req.body || {};
    const gameKey = game || 'roblox';
    const gameData = games[gameKey] || { name: 'Roblox Robux Send', type: 'roblox' };
    const gamePackages = packages.filter(p => (p.game || 'roblox') === gameKey);
    const pkg = packages.find(p => p.id === package_id) || gamePackages[0] || packages[0];

    const now = new Date();
    const order_id = checkout_ref || ('PR' + Date.now().toString(36).toUpperCase() + Math.random().toString(36).substring(2, 6).toUpperCase());
    const token = receipt_token || Math.random().toString(36).substring(2) + Math.random().toString(36).substring(2);
    let amount = Number(pkg.price);
    const original_amount = amount;
    let discount = 0;
    let appliedPromo = null;

    // Apply promo code if provided
    if (promo_code && typeof promo_code === 'string') {
      const codeUpper = promo_code.trim().toUpperCase();
      const cp = coupons.find(c => c.code.toUpperCase() === codeUpper && c.enabled);
      if (cp && (!cp.max_uses || cp.used_count < cp.max_uses) && amount >= (cp.min_spend || 0)) {
        discount = cp.type === 'percentage' ? (amount * (cp.value / 100)) : cp.value;
        discount = Math.min(discount, Math.max(0, amount - 0.05));
        discount = Number(discount.toFixed(2));
        amount = Number((amount - discount).toFixed(2));
        appliedPromo = cp.code;
        cp.used_count = (cp.used_count || 0) + 1;
        saveCoupons();
      }
    }

    const currentUser = getUserFromReq(req);

    // Instant Wallet Checkout Option
    if (payment_method === 'wallet') {
      if (!currentUser) {
        return res.status(401).json({ ok: false, error: 'Please log in to pay with your Rolea Wallet balance' });
      }
      if (currentUser.balance < amount) {
        return res.status(400).json({ ok: false, error: `Insufficient wallet balance ($${currentUser.balance.toFixed(2)} USD). Please top up first.` });
      }

      currentUser.balance = Number((currentUser.balance - amount).toFixed(2));
      saveUsers();

      walletTransactions.unshift({
        id: 'wtx_' + Date.now().toString(36),
        user_id: currentUser.id,
        type: 'spend',
        amount: -amount,
        order_id: order_id,
        product: `${gameData.name} - ${pkg.name}`,
        date: now.toISOString()
      });
      saveWalletTx();

      const newOrder = {
        order_id,
        token,
        user_id: currentUser.id,
        buyer_account: currentUser.username,
        game: gameKey,
        product_name: gameData.name,
        product_type: gameData.type,
        package: pkg.name,
        package_id: pkg.id,
        robux_amount: pkg.robux || 0,
        original_amount: original_amount,
        discount: discount,
        promo_code: appliedPromo,
        amount: amount,
        payment_method: 'Rolea Wallet',
        player_id: player_id || '',
        roblox_username: username || player_id || '',
        display_name: username || player_id || currentUser.username,
        roblox_id: String(Math.abs(player_id?.split('').reduce((acc, c) => acc + c.charCodeAt(0), 12345678) || 12345678)),
        profile_url: gameKey === 'roblox' ? `https://www.roblox.com/users/1/profile` : '',
        target_url: gameData.type === 'smm' ? player_id : '',
        status: settings.auto_deliver ? 'completed' : 'paid',
        step: settings.auto_deliver ? 'delivered' : 'sending',
        paid: true,
        delivered: !!settings.auto_deliver,
        created_at: now.toISOString(),
        label: settings.auto_deliver ? 'Payment confirmed via Wallet & items delivered' : 'Payment confirmed via Wallet. Processing delivery…'
      };

      orders.unshift(newOrder);
      if (orders.length > 500) orders = orders.slice(0, 500);
      saveOrders();
      sendTelegramPaidAlert(newOrder);

      return res.json({
        ok: true,
        paid_with_wallet: true,
        order_id: newOrder.order_id,
        receipt_token: newOrder.token,
        amount: newOrder.amount,
        original_amount: newOrder.original_amount,
        discount: newOrder.discount,
        promo_code: newOrder.promo_code,
        status: newOrder.status,
        step: newOrder.step,
        remaining_balance: currentUser.balance,
        label: newOrder.label
      });
    }

    // Call live KHQRPay gateway for ABA KHQR
    const khqrRes = await createKhqrPayOrder(amount, order_id);
    let qr_url = '';
    let khqrpay_id = null;
    let payment_url = '';
    let aba_deeplink = '';
    let expires_at = new Date(now.getTime() + 5 * 60 * 1000).toISOString();

    if (khqrRes && khqrRes.id) {
      khqrpay_id = khqrRes.id;
      qr_url = khqrRes.qr_image || '';
      payment_url = khqrRes.checkout_url || `https://khqrpay.site/pay/${khqrRes.id}`;
      aba_deeplink = khqrRes.aba_deeplink || '';
      if (khqrRes.expires_at) {
        expires_at = new Date(khqrRes.expires_at).toISOString();
      }
    }

    // Fallback if KHQRPay gateway is unreachable or offline
    if (!qr_url) {
      const khqrPayload = `00020101021229370016bakong@rolea010108${order_id}520459995303840540${amount.toFixed(2).length < 10 ? '0' + amount.toFixed(2).length : amount.toFixed(2).length}${amount.toFixed(2)}5802KH5911ROLEA TOPUP6010PHNOM PENH62240108${order_id}0708ROLEATOPUP6304`;
      qr_url = await QRCode.toDataURL(khqrPayload, {
        errorCorrectionLevel: 'M',
        margin: 2,
        width: 400,
        color: {
          dark: '#10234b',
          light: '#ffffff'
        }
      });
      payment_url = `https://khqrpay.site/pay/${order_id}`;
    }

    const newOrder = {
      order_id,
      khqrpay_id,
      token,
      user_id: currentUser ? currentUser.id : null,
      buyer_account: currentUser ? currentUser.username : (username || player_id || ''),
      game: gameKey,
      product_name: gameData.name,
      product_type: gameData.type,
      package: pkg.name,
      package_id: pkg.id,
      robux_amount: pkg.robux || 0,
      original_amount: original_amount,
      discount: discount,
      promo_code: appliedPromo,
      amount: amount,
      payment_method: 'ABA KHQR',
      player_id: player_id || '',
      roblox_username: username || player_id || '',
      display_name: username || player_id || 'Player',
      roblox_id: String(Math.abs(player_id?.split('').reduce((acc, c) => acc + c.charCodeAt(0), 12345678) || 12345678)),
      profile_url: gameKey === 'roblox' ? `https://www.roblox.com/users/1/profile` : '',
      target_url: gameData.type === 'smm' ? player_id : '',
      status: 'pending', // pending, scanned, paid, completed, failed, expired
      step: 'wait',      // wait, scanned, sending, delivered, hold, failed
      paid: false,
      delivered: false,
      created_at: now.toISOString(),
      expires_at: expires_at,
      payment_url: payment_url,
      aba_deeplink: aba_deeplink,
      qr_url: qr_url,
      label: 'Waiting for KHQR payment…'
    };

    orders.unshift(newOrder);
    if (orders.length > 500) orders = orders.slice(0, 500);
    saveOrders();

    return res.json({
      ok: true,
      order_id: newOrder.order_id,
      khqrpay_id: newOrder.khqrpay_id,
      receipt_token: newOrder.token,
      amount: newOrder.amount,
      original_amount: newOrder.original_amount,
      discount: newOrder.discount,
      promo_code: newOrder.promo_code,
      qr_url: newOrder.qr_url,
      payment_url: newOrder.payment_url,
      aba_deeplink: newOrder.aba_deeplink,
      expires_at: newOrder.expires_at,
      status: newOrder.status,
      step: newOrder.step,
      robux_amount: newOrder.robux_amount,
      server_now: new Date().toISOString(),
      label: newOrder.label
    });
  } catch (err) {
    console.error(err);
    res.status(500).json({ ok: false, error: err.message || 'Could not create order' });
  }
});

// Order status polling endpoint
app.get('/api/order-status/:id', async (req, res) => {
  const orderId = req.params.id;
  const order = orders.find(o => o.order_id === orderId);

  if (!order) {
    return res.status(404).json({ ok: false, error: 'Order not found' });
  }

  // If order has a KHQRPay ID and has not been marked paid yet, check live status with KHQRPay
  if (order.khqrpay_id && !order.paid && order.status !== 'completed' && order.status !== 'expired') {
    const live = await checkKhqrPayStatus(order.khqrpay_id);
    if (live) {
      const st = String(live.status || '').toLowerCase();
      if (st === 'paid' || st === 'success' || st === 'completed') {
        order.paid = true;
        if (order.type === 'wallet_topup') {
          order.status = 'completed';
          order.step = 'delivered';
          order.delivered = true;
          if (!order.wallet_credited) {
            order.wallet_credited = true;
            const u = users.find(usr => usr.id === order.user_id);
            if (u) {
              u.balance = Number((u.balance + Number(order.amount)).toFixed(2));
              saveUsers();
              walletTransactions.unshift({
                id: 'wtx_' + Date.now().toString(36),
                user_id: u.id,
                type: 'deposit',
                amount: Number(order.amount),
                order_id: order.order_id,
                product: 'Wallet Top-up',
                date: new Date().toISOString()
              });
              saveWalletTx();
            }
          }
          order.label = `Wallet successfully topped up (+$${Number(order.amount).toFixed(2)} USD)`;
        } else {
          order.status = 'paid';
          order.step = settings.auto_deliver ? 'delivered' : 'sending';
          if (settings.auto_deliver) {
            order.delivered = true;
            order.status = 'completed';
            order.label = 'Payment confirmed & items delivered';
          } else {
            order.label = 'Payment confirmed. Processing delivery…';
          }
          sendTelegramPaidAlert(order);
        }
        saveOrders();
      } else if (st === 'scanned' && order.status === 'pending') {
        order.status = 'scanned';
        order.step = 'scanned';
        order.label = 'QR Scanned in ABA Mobile';
        saveOrders();
      } else if (st === 'expired') {
        order.status = 'expired';
        order.step = 'expired';
        order.label = 'Payment expired';
        saveOrders();
      } else if (st === 'failed') {
        order.status = 'failed';
        order.step = 'failed';
        order.label = 'Payment failed';
        saveOrders();
      }
    }
  }

  // Check expiration if still pending
  if (order.status === 'pending' && new Date(order.expires_at) < new Date()) {
    order.status = 'expired';
    order.step = 'expired';
    order.label = 'Payment expired';
    saveOrders();
  }

  res.json({
    ok: true,
    order_id: order.order_id,
    khqrpay_id: order.khqrpay_id,
    amount: order.amount,
    status: order.status,
    step: order.step,
    paid: order.paid,
    delivered: order.delivered,
    robux_amount: order.robux_amount,
    roblox_username: order.roblox_username,
    display_name: order.display_name,
    roblox_id: order.roblox_id,
    package: order.package,
    product_name: order.product_name,
    product_type: order.product_type,
    qr_url: order.qr_url,
    payment_url: order.payment_url,
    aba_deeplink: order.aba_deeplink,
    expires_at: order.expires_at,
    server_now: new Date().toISOString(),
    label: order.label
  });
});

// Single order lookup (from Check Order tracking form)
app.post('/api/check-order', (req, res) => {
  const { order_id, username, receipt_token } = req.body || {};
  const order = orders.find(o => o.order_id === order_id);

  if (!order) {
    return res.status(404).json({ ok: false, error: 'Order not found. Please verify your Order ID.' });
  }

  // Token or username authorization
  const tokenMatch = receipt_token && order.token === receipt_token;
  const userMatch = username && order.roblox_username.toLowerCase() === username.trim().toLowerCase();

  if (!tokenMatch && !userMatch) {
    return res.status(403).json({
      ok: false,
      error: 'Receipt token does not match. For privacy, use the token saved on this device or contact support.'
    });
  }

  res.json({
    ok: true,
    order: order
  });
});

// Customer orders lookup (auto-loaded in My Orders via PutiOrders)
app.post('/api/customer-orders', (req, res) => {
  const { orders: refs } = req.body || {};
  if (!Array.isArray(refs)) {
    return res.json({ ok: true, orders: [] });
  }

  const tokenMap = new Map();
  refs.forEach(r => {
    if (r && r.order_id && r.token) {
      tokenMap.set(r.order_id, r.token);
    }
  });

  const matched = orders.filter(o => {
    const t = tokenMap.get(o.order_id);
    return t && t === o.token;
  });

  res.json({
    ok: true,
    orders: matched
  });
});

// Interactive Simulator endpoint for testing scan, payment, delivery
app.post('/api/simulate-pay', (req, res) => {
  const { order_id, action } = req.body || {};
  const order = orders.find(o => o.order_id === order_id);

  if (!order) {
    return res.status(404).json({ ok: false, error: 'Order not found' });
  }

  if (action === 'scan') {
    order.status = 'scanned';
    order.step = 'scanned';
    order.label = 'QR Scanned in ABA Mobile';
  } else if (action === 'pay') {
    order.status = 'paid';
    order.paid = true;
    order.step = 'sending';
    order.label = 'Payment Confirmed! Queuing delivery…';

    // Auto-advance to delivered after 3.5 seconds
    setTimeout(() => {
      const live = orders.find(o => o.order_id === order_id);
      if (live && live.paid) {
        live.status = 'completed';
        live.delivered = true;
        live.step = 'delivered';
        live.label = 'Robux transfer confirmed!';
        saveOrders();
      }
    }, 3500);
  } else if (action === 'deliver') {
    order.status = 'completed';
    order.paid = true;
    order.delivered = true;
    order.step = 'delivered';
    order.label = 'Robux sent successfully!';
  } else if (action === 'hold') {
    order.step = 'hold';
    order.label = 'Order on hold (awaiting account)';
  } else if (action === 'fail') {
    order.status = 'failed';
    order.step = 'failed';
    order.label = 'Payment failed';
  }

  saveOrders();
  res.json({ ok: true, order });
});

// ================= ADMIN APIS ================= //
app.post('/api/admin/login', (req, res) => {
  const { username, password } = req.body || {};
  if (username === 'admin' && (password === 'admin123' || password === 'admin')) {
    return res.json({ ok: true, token: 'rolea_token_' + Date.now() });
  }
  return res.status(401).json({ ok: false, error: 'Invalid username or password.' });
});

app.get('/api/admin/stats', (req, res) => {
  const revenue = orders.filter(o => o.paid).reduce((sum, o) => sum + (Number(o.amount) || 0), 0);
  const robuxDelivered = orders.filter(o => o.delivered).reduce((sum, o) => sum + (Number(o.robux_amount) || 0), 0);
  const pendingOrders = orders.filter(o => !o.paid && o.status !== 'failed' && o.status !== 'expired').length;

  res.json({
    ok: true,
    stats: {
      revenue,
      total_orders: orders.length,
      robux_delivered: robuxDelivered,
      pending_orders: pendingOrders
    }
  });
});

app.get('/api/admin/orders', (req, res) => {
  res.json({ ok: true, orders });
});

app.post('/api/admin/order-action', (req, res) => {
  const { order_id, action } = req.body || {};
  const orderIndex = orders.findIndex(o => o.order_id === order_id);

  if (orderIndex === -1) {
    return res.status(404).json({ ok: false, error: 'Order not found' });
  }

  const order = orders[orderIndex];

  if (action === 'delete') {
    orders.splice(orderIndex, 1);
    saveOrders();
    return res.json({ ok: true, message: 'Order deleted' });
  }

  if (action === 'mark_paid') {
    order.paid = true;
    order.status = 'paid';
    order.step = 'sending';
    order.label = 'Payment verified by Admin';
    saveOrders();
    if (order.type === 'wallet_topup' && !order.wallet_credited) {
      order.wallet_credited = true;
      const u = users.find(usr => usr.id === order.user_id);
      if (u) {
        u.balance = Number((u.balance + Number(order.amount)).toFixed(2));
        saveUsers();
        walletTransactions.unshift({
          id: 'wtx_' + Date.now().toString(36),
          user_id: u.id,
          type: 'deposit',
          amount: Number(order.amount),
          order_id: order.order_id,
          product: 'Wallet Top-up (Admin Action)',
          date: new Date().toISOString()
        });
        saveWalletTx();
      }
    }

    sendTelegramPaidAlert(order);

    if (settings.auto_deliver) {
      setTimeout(() => {
        const live = orders.find(o => o.order_id === order_id);
        if (live && live.paid) {
          live.status = 'completed';
          live.delivered = true;
          live.step = 'delivered';
          live.label = 'Delivery confirmed!';
          saveOrders();
        }
      }, 3500);
    }
  } else if (action === 'deliver') {
    order.paid = true;
    order.delivered = true;
    order.status = 'completed';
    order.step = 'delivered';
    order.label = 'Order fulfilled successfully!';
    if (order.type === 'wallet_topup' && !order.wallet_credited) {
      order.wallet_credited = true;
      const u = users.find(usr => usr.id === order.user_id);
      if (u) {
        u.balance = Number((u.balance + Number(order.amount)).toFixed(2));
        saveUsers();
        walletTransactions.unshift({
          id: 'wtx_' + Date.now().toString(36),
          user_id: u.id,
          type: 'deposit',
          amount: Number(order.amount),
          order_id: order.order_id,
          product: 'Wallet Top-up (Admin Action)',
          date: new Date().toISOString()
        });
        saveWalletTx();
      }
    }
    saveOrders();
    sendTelegramPaidAlert(order);
  } else if (action === 'hold') {
    order.step = 'hold';
    order.label = 'Order on hold (manual review)';
  } else if (action === 'failed') {
    order.status = 'failed';
    order.step = 'failed';
    order.label = 'Order marked failed by Admin';
  }

  saveOrders();
  res.json({ ok: true, order });
});

// Games APIs
app.get('/api/games', (req, res) => {
  res.json({ ok: true, games });
});

app.get('/api/game/:id', (req, res) => {
  const g = games[req.params.id];
  if (!g) return res.status(404).json({ ok: false, error: 'Game not found' });
  const pkgs = packages.filter(p => (p.game || 'roblox') === req.params.id && p.ok !== 0);
  res.json({ ok: true, game: g, packages: pkgs });
});

app.get('/api/admin/games', (req, res) => {
  res.json({ ok: true, games });
});

app.post('/api/admin/games/edit', (req, res) => {
  const { id, name, category, kicker, unit, logo, banner, badge, enabled } = req.body || {};
  if (!id || !games[id]) return res.status(404).json({ ok: false, error: 'Game not found' });
  const g = games[id];
  if (name) g.name = name;
  if (category) g.category = category;
  if (kicker) g.kicker = kicker;
  if (unit) g.unit = unit;
  if (logo) g.logo = logo;
  if (banner) g.banner = banner;
  if (badge !== undefined) g.badge = badge;
  if (enabled !== undefined) g.enabled = !!enabled;
  saveGames();
  res.json({ ok: true, game: g });
});

app.post('/api/admin/games/add', (req, res) => {
  let { id, name, category, kicker, unit, logo, banner, badge, enabled } = req.body || {};
  if (!name || !name.trim()) {
    return res.status(400).json({ ok: false, error: 'Game name is required' });
  }
  name = name.trim();
  
  if (!id || !id.trim()) {
    id = name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
  } else {
    id = id.trim().toLowerCase().replace(/[^a-z0-9_-]+/g, '');
  }

  if (!id) id = 'game_' + Date.now();

  if (games[id]) {
    id = id + '_' + Math.floor(Math.random() * 1000);
  }

  category = (category && category.trim()) || 'Topup & Game Services';
  kicker = (kicker && kicker.trim()) || (name.toUpperCase() + ' • TOPUP');
  unit = (unit && unit.trim()) || 'Units';
  logo = (logo && logo.trim()) || '/media/rolea-logo.webp';
  banner = (banner && banner.trim()) || '/media/banner1.webp';
  badge = badge || 'NEW';
  enabled = enabled !== undefined ? !!enabled : true;

  const newGame = {
    id,
    name,
    category,
    kicker,
    unit,
    type: id,
    enabled,
    logo,
    banner,
    badge
  };

  games[id] = newGame;
  saveGames();

  // Create 2 starter packages for the new game so it has items right away
  const starter1 = {
    id: `pkg_${id}_1`,
    game: id,
    name: `100 ${unit}`,
    robux: 100,
    price: 1.00,
    badge: 'STARTER',
    icon: logo,
    ok: 1
  };
  const starter2 = {
    id: `pkg_${id}_2`,
    game: id,
    name: `500 ${unit}`,
    robux: 500,
    price: 4.50,
    badge: 'POPULAR',
    icon: logo,
    ok: 1
  };
  packages.push(starter1, starter2);
  savePackages();

  res.json({ ok: true, game: newGame, id });
});

app.post('/api/admin/games/delete', (req, res) => {
  const { id } = req.body || {};
  if (!id || !games[id]) {
    return res.status(404).json({ ok: false, error: 'Game not found' });
  }

  const gameKeys = Object.keys(games);
  if (gameKeys.length <= 1) {
    return res.status(400).json({ ok: false, error: 'Cannot delete the only remaining game.' });
  }

  const deletedName = games[id].name;
  delete games[id];
  saveGames();

  // Remove packages associated with this game
  packages = packages.filter(p => (p.game || 'roblox') !== id);
  savePackages();

  res.json({ ok: true, message: `Game ${deletedName} deleted`, remainingGames: Object.keys(games) });
});

app.post('/api/admin/games/toggle', (req, res) => {
  const { id } = req.body || {};
  if (!id || !games[id]) return res.status(404).json({ ok: false, error: 'Game not found' });
  games[id].enabled = !games[id].enabled;
  saveGames();
  res.json({ ok: true, game: games[id] });
});

app.post('/api/admin/games/upload-logo', (req, res) => {
  const { id, image_base64, image_url } = req.body || {};

  if (image_url) {
    const url = image_url.trim();
    if (id && games[id]) {
      games[id].logo = url;
      saveGames();
    }
    return res.json({ ok: true, logo: url });
  }

  if (image_base64) {
    try {
      const match = image_base64.match(/^data:image\/([a-zA-Z0-9+]+);base64,(.+)$/);
      let ext = 'webp';
      let data = image_base64;
      if (match) {
        ext = match[1] === 'jpeg' ? 'jpg' : (match[1] === 'png' ? 'png' : 'webp');
        data = match[2];
      }
      const buffer = Buffer.from(data, 'base64');
      const safeId = (id || 'game').replace(/[^a-zA-Z0-9_-]/g, '');
      const filename = `logo_${safeId}_${Date.now()}.${ext}`;
      fs.writeFileSync(path.join(publicDir, 'media', filename), buffer);

      const finalLogoUrl = `/media/${filename}`;
      if (id && games[id]) {
        games[id].logo = finalLogoUrl;
        saveGames();
      }
      return res.json({ ok: true, logo: finalLogoUrl });
    } catch (err) {
      console.error(err);
      return res.status(500).json({ ok: false, error: 'Failed to upload game logo' });
    }
  }

  res.status(400).json({ ok: false, error: 'No image provided' });
});

app.get('/api/admin/packages', (req, res) => {
  const { game } = req.query;
  if (game) {
    const filtered = packages.filter(p => (p.game || 'roblox') === game);
    return res.json({ ok: true, packages: filtered });
  }
  res.json({ ok: true, packages });
});

app.post('/api/admin/packages/add', (req, res) => {
  const { game, name, robux, price, badge, icon } = req.body || {};
  if (!name || robux === undefined || price === undefined) {
    return res.status(400).json({ ok: false, error: 'Missing package fields' });
  }
  const gameKey = game || 'roblox';
  const defaultIcon = games[gameKey]?.logo || '/media/rolea-logo.webp';
  const newPkg = {
    id: 'pkg_' + Date.now().toString(36),
    game: gameKey,
    name: name,
    robux: Number(robux),
    price: Number(price),
    badge: badge ? String(badge).trim().toUpperCase() : '',
    ok: 1,
    icon: icon || defaultIcon
  };
  packages.push(newPkg);
  savePackages();
  res.json({ ok: true, package: newPkg });
});

app.post('/api/admin/packages/edit', (req, res) => {
  const { id, game, name, robux, price, badge, ok, icon } = req.body || {};
  const pkg = packages.find(p => p.id === id);
  if (!pkg) return res.status(404).json({ ok: false, error: 'Package not found' });
  if (name) pkg.name = name;
  if (robux !== undefined) pkg.robux = Number(robux);
  if (price !== undefined) pkg.price = Number(price);
  if (badge !== undefined) pkg.badge = String(badge).trim().toUpperCase();
  if (ok !== undefined) pkg.ok = ok ? 1 : 0;
  if (icon) pkg.icon = icon;
  if (game) pkg.game = game;
  savePackages();
  res.json({ ok: true, package: pkg });
});

app.post('/api/admin/packages/toggle', (req, res) => {
  const { id } = req.body || {};
  const pkg = packages.find(p => p.id === id);
  if (!pkg) return res.status(404).json({ ok: false, error: 'Package not found' });
  pkg.ok = pkg.ok === 1 ? 0 : 1;
  savePackages();
  res.json({ ok: true, package: pkg });
});

app.post('/api/admin/packages/delete', (req, res) => {
  const { id } = req.body || {};
  packages = packages.filter(p => p.id !== id);
  savePackages();
  res.json({ ok: true });
});

app.get('/api/admin/settings', (req, res) => {
  res.json({ ok: true, settings });
});

app.get('/api/settings', (req, res) => {
  res.json({
    ok: true,
    store_name: settings.store_name,
    telegram_handle: settings.telegram_handle,
    khqr_merchant_name: settings.khqr_merchant_name,
    home_banner: settings.home_banner || '/media/banner1.webp',
    roblox_banner: settings.roblox_banner || '/media/roblox-banner.webp'
  });
});

app.post('/api/admin/settings', (req, res) => {
  const { store_name, telegram_handle, khqr_merchant_name, khqr_account, auto_deliver, khqrpay_api_key, khqrpay_base_url, home_banner, roblox_banner, telegram_bot_token, telegram_chat_id } = req.body || {};
  if (store_name) settings.store_name = store_name;
  if (telegram_handle) settings.telegram_handle = telegram_handle;
  if (telegram_bot_token) settings.telegram_bot_token = telegram_bot_token.trim();
  if (telegram_chat_id) settings.telegram_chat_id = String(telegram_chat_id).trim();
  if (khqr_merchant_name) settings.khqr_merchant_name = khqr_merchant_name;
  if (khqr_account) settings.khqr_account = khqr_account;
  if (khqrpay_api_key) settings.khqrpay_api_key = khqrpay_api_key;
  if (khqrpay_base_url) settings.khqrpay_base_url = khqrpay_base_url;
  if (home_banner) settings.home_banner = home_banner;
  if (roblox_banner) settings.roblox_banner = roblox_banner;
  if (typeof auto_deliver === 'boolean') settings.auto_deliver = auto_deliver;
  saveSettings();
  res.json({ ok: true, settings });
});

app.post('/api/admin/telegram/test', async (req, res) => {
  const token = settings.telegram_bot_token || (process.env.TELEGRAM_BOT_TOKEN || '');
  const chatId = settings.telegram_chat_id || '-5315869838';
  try {
    const url = `https://api.telegram.org/bot${token}/sendMessage`;
    const resp = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        chat_id: chatId,
        text: `🔔 <b>[TEST NOTIFICATION]</b>\n✨ <b>Rolea Topup:</b> Telegram Order Alert bot is connected successfully.\n🕒 <b>Time:</b> ${new Date().toLocaleString('en-US', { timeZone: 'Asia/Phnom_Penh' })}`,
        parse_mode: 'HTML'
      })
    });
    const j = await resp.json();
    if (j && j.ok) {
      return res.json({ ok: true, message: 'Test message sent to Telegram!' });
    }
    return res.status(400).json({ ok: false, error: j.description || 'Telegram rejected message' });
  } catch (err) {
    return res.status(500).json({ ok: false, error: err.message });
  }
});

// Admin Banner Upload endpoint
app.post('/api/admin/upload-banner', (req, res) => {
  const { type, game_id, image_base64, image_url } = req.body || {};
  const targetGame = game_id || (type && type !== 'home' ? type : null);

  // If home banner
  if (!targetGame || type === 'home') {
    if (image_url && typeof image_url === 'string') {
      settings.home_banner = image_url.trim();
      saveSettings();
      return res.json({ ok: true, banner_url: settings.home_banner, type: 'home' });
    }

    if (image_base64 && typeof image_base64 === 'string') {
      try {
        const match = image_base64.match(/^data:image\/([a-zA-Z0-9+]+);base64,(.+)$/);
        let ext = 'webp';
        let data = image_base64;
        if (match) {
          ext = match[1] === 'jpeg' ? 'jpg' : (match[1] === 'png' ? 'png' : 'webp');
          data = match[2];
        }
        const buffer = Buffer.from(data, 'base64');
        const filename = `banner_home_${Date.now()}.${ext}`;
        const filePath = path.join(publicDir, 'media', filename);
        fs.writeFileSync(filePath, buffer);

        const savedUrl = `/media/${filename}`;
        settings.home_banner = savedUrl;
        saveSettings();
        return res.json({ ok: true, banner_url: savedUrl, type: 'home' });
      } catch (err) {
        console.error('Upload error:', err);
        return res.status(500).json({ ok: false, error: 'Failed to save banner image' });
      }
    }
    return res.status(400).json({ ok: false, error: 'No image data or URL provided' });
  }

  // If game-specific banner (e.g. roblox, tiktok, etc.)
  if (!games[targetGame]) {
    return res.status(404).json({ ok: false, error: `Game ${targetGame} not found` });
  }

  if (image_url && typeof image_url === 'string') {
    games[targetGame].banner = image_url.trim();
    saveGames();
    if (targetGame === 'roblox') {
      settings.roblox_banner = image_url.trim();
      saveSettings();
    }
    return res.json({ ok: true, banner_url: games[targetGame].banner, game_id: targetGame });
  }

  if (image_base64 && typeof image_base64 === 'string') {
    try {
      const match = image_base64.match(/^data:image\/([a-zA-Z0-9+]+);base64,(.+)$/);
      let ext = 'webp';
      let data = image_base64;
      if (match) {
        ext = match[1] === 'jpeg' ? 'jpg' : (match[1] === 'png' ? 'png' : 'webp');
        data = match[2];
      }
      const buffer = Buffer.from(data, 'base64');
      const filename = `banner_${targetGame}_${Date.now()}.${ext}`;
      const filePath = path.join(publicDir, 'media', filename);
      fs.writeFileSync(filePath, buffer);

      const savedUrl = `/media/${filename}`;
      games[targetGame].banner = savedUrl;
      saveGames();
      if (targetGame === 'roblox') {
        settings.roblox_banner = savedUrl;
        saveSettings();
      }
      return res.json({ ok: true, banner_url: savedUrl, game_id: targetGame });
    } catch (err) {
      console.error('Upload error:', err);
      return res.status(500).json({ ok: false, error: 'Failed to save banner image' });
    }
  }

  return res.status(400).json({ ok: false, error: 'No image data or URL provided' });
});

// ==========================================
// ADMIN PROMOS & VOUCHERS APIS
// ==========================================

app.get('/api/admin/promos', (req, res) => {
  res.json({ ok: true, promos: coupons });
});

app.post('/api/admin/promos/add', (req, res) => {
  const { code, type, value, min_spend, max_uses, description } = req.body || {};
  if (!code || typeof code !== 'string') {
    return res.status(400).json({ ok: false, error: 'Promo code is required' });
  }
  const cleanCode = code.trim().toUpperCase();
  if (coupons.some(c => c.code.toUpperCase() === cleanCode)) {
    return res.status(400).json({ ok: false, error: 'Promo code already exists' });
  }

  const numVal = parseFloat(value);
  if (isNaN(numVal) || numVal <= 0) {
    return res.status(400).json({ ok: false, error: 'Discount value must be greater than 0' });
  }

  const newPromo = {
    id: 'cpn_' + Date.now().toString(36),
    code: cleanCode,
    type: type === 'fixed' ? 'fixed' : 'percentage',
    value: numVal,
    min_spend: parseFloat(min_spend) || 0,
    max_uses: parseInt(max_uses) || 0,
    used_count: 0,
    enabled: true,
    description: description ? description.trim() : `${numVal}${type === 'fixed' ? '$' : '%'} Discount`
  };

  coupons.unshift(newPromo);
  saveCoupons();
  res.json({ ok: true, promo: newPromo });
});

app.post('/api/admin/promos/toggle', (req, res) => {
  const { id } = req.body || {};
  const cp = coupons.find(c => c.id === id || c.code === id);
  if (!cp) return res.status(404).json({ ok: false, error: 'Promo code not found' });
  cp.enabled = !cp.enabled;
  saveCoupons();
  res.json({ ok: true, promo: cp });
});

app.post('/api/admin/promos/delete', (req, res) => {
  const { id } = req.body || {};
  const idx = coupons.findIndex(c => c.id === id || c.code === id);
  if (idx === -1) return res.status(404).json({ ok: false, error: 'Promo code not found' });
  const deleted = coupons.splice(idx, 1)[0];
  saveCoupons();
  res.json({ ok: true, message: `Promo code ${deleted.code} deleted` });
});

// ==========================================
// ADMIN REVIEWS APIS
// ==========================================

app.get('/api/admin/reviews', (req, res) => {
  res.json({ ok: true, reviews });
});

app.post('/api/admin/reviews/toggle', (req, res) => {
  const { id } = req.body || {};
  const r = reviews.find(item => item.id === id);
  if (!r) return res.status(404).json({ ok: false, error: 'Review not found' });
  r.approved = !r.approved;
  saveReviews();
  res.json({ ok: true, review: r });
});

app.post('/api/admin/reviews/delete', (req, res) => {
  const { id } = req.body || {};
  const idx = reviews.findIndex(r => r.id === id);
  if (idx === -1) return res.status(404).json({ ok: false, error: 'Review not found' });
  const deleted = reviews.splice(idx, 1)[0];
  saveReviews();
  res.json({ ok: true, message: 'Review deleted' });
});

app.post('/api/admin/reviews/add', (req, res) => {
  const { game, username, rating, comment } = req.body || {};
  if (!comment || typeof comment !== 'string') {
    return res.status(400).json({ ok: false, error: 'Comment required' });
  }
  const g = games[game] || {};
  const newRev = {
    id: 'rev_' + Date.now().toString(36),
    order_id: 'ADMIN_' + Date.now().toString(36).toUpperCase(),
    game: game || 'roblox',
    game_name: g.name || 'Rolea Topup',
    username: (username || 'Verified Buyer').trim(),
    rating: Math.max(1, Math.min(5, parseInt(rating) || 5)),
    comment: comment.trim(),
    created_at: new Date().toISOString(),
    approved: true
  };
  reviews.unshift(newRev);
  saveReviews();
  res.json({ ok: true, review: newRev });
});

// ==========================================
// ADMIN USERS & WALLET ADJUSTMENT APIS
// ==========================================

app.get('/api/admin/users', (req, res) => {
  const safeUsers = users.map(u => ({
    id: u.id,
    username: u.username,
    email: u.email,
    balance: u.balance,
    created_at: u.created_at,
    total_orders: orders.filter(o => o.user_id === u.id).length
  }));
  res.json({ ok: true, users: safeUsers });
});

app.post('/api/admin/users/edit', (req, res) => {
  const { user_id, username, email, password } = req.body || {};
  const user = users.find(u => u.id === user_id || u.username === user_id);
  if (!user) return res.status(404).json({ ok: false, error: 'User not found' });

  if (username && typeof username === 'string' && username.trim().length >= 3) {
    const cleanUname = username.trim();
    const conflict = users.find(u => u.id !== user.id && u.username.toLowerCase() === cleanUname.toLowerCase());
    if (conflict) {
      return res.status(400).json({ ok: false, error: 'Username already taken by another account' });
    }
    user.username = cleanUname;
  }

  if (email !== undefined) {
    user.email = (email || '').trim().toLowerCase();
  }

  if (password && typeof password === 'string' && password.trim().length >= 6) {
    user.password_hash = hashPassword(password.trim());
  }

  saveUsers();
  res.json({
    ok: true,
    message: `Account ${user.username} updated successfully`,
    user: {
      id: user.id,
      username: user.username,
      email: user.email,
      balance: user.balance
    }
  });
});

app.post('/api/admin/users/delete', (req, res) => {
  const { user_id } = req.body || {};
  const idx = users.findIndex(u => u.id === user_id || u.username === user_id);
  if (idx === -1) return res.status(404).json({ ok: false, error: 'User not found' });
  const deleted = users.splice(idx, 1)[0];
  saveUsers();
  res.json({ ok: true, message: `Account ${deleted.username} deleted` });
});

app.post('/api/admin/users/adjust-balance', (req, res) => {
  const { user_id, action, amount, reason } = req.body || {};
  const user = users.find(u => u.id === user_id || u.username === user_id);
  if (!user) return res.status(404).json({ ok: false, error: 'User not found' });

  let num = parseFloat(amount);
  if (isNaN(num)) return res.status(400).json({ ok: false, error: 'Invalid amount' });

  num = Math.abs(num);
  if (action === 'deduct') {
    num = -num;
  }

  user.balance = Math.max(0, Number((user.balance + num).toFixed(2)));
  saveUsers();

  walletTransactions.unshift({
    id: 'wtx_' + Date.now().toString(36),
    user_id: user.id,
    type: num >= 0 ? 'admin_credit' : 'admin_debit',
    amount: num,
    order_id: 'ADMIN',
    product: reason || (num >= 0 ? 'Admin Deposit' : 'Admin Deduction'),
    date: new Date().toISOString()
  });
  saveWalletTx();

  res.json({ ok: true, message: `Balance updated for ${user.username}`, balance: user.balance });
});

// Web routes
const sendOptions = { root: publicDir, dotfiles: 'allow' };

app.get('/', (req, res) => {
  res.sendFile('index.html', sendOptions);
});

app.get('/game/:game', (req, res) => {
  res.sendFile('roblox.html', sendOptions);
});

app.get('/check-order', (req, res) => {
  res.sendFile('check_order.html', sendOptions);
});

app.get('/order/success/:order_id', (req, res) => {
  res.sendFile('receipt.html', sendOptions);
});

// Admin Panel Web Routes
app.get('/admin', (req, res) => {
  res.sendFile('admin.html', sendOptions);
});

app.get('/admin/login', (req, res) => {
  res.sendFile('admin_login.html', sendOptions);
});

app.listen(PORT, () => {
  console.log(`===============================================`);
  console.log(`ROLEA TOPUP Web Server running at:`);
  console.log(`- http://localhost:${PORT}`);
  console.log(`- http://localhost:${PORT}/game/roblox`);
  console.log(`- http://localhost:${PORT}/check-order`);
  console.log(`- http://localhost:${PORT}/admin (Credentials: admin / admin123)`);
  console.log(`===============================================`);
});
