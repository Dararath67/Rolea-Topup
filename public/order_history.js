/* Puti Reach V22 — browser-local order references. No API keys or payment data are stored.
 * Actual order records (including unpaid Pay Now orders) are saved in MongoDB.
 * Private 256-bit receipt tokens authorize fetching each buyer's order.
 */
(function () {
  'use strict';
  const KEY = 'puti_reach_my_orders_v22';
  const MAX = 50;
  const ORDER = /^PR[A-Za-z0-9]{8,62}$/;
  let fallback = [];
  function read() {
    try {
      const raw = JSON.parse(localStorage.getItem(KEY) || '[]');
      if (!Array.isArray(raw)) return fallback.slice();
      const seen = new Set();
      return raw.filter(r => {
        if (!r || typeof r.order_id !== 'string' || !ORDER.test(r.order_id) ||
            typeof r.token !== 'string' || r.token.length < 16 || r.token.length > 128 ||
            seen.has(r.order_id)) return false;
        seen.add(r.order_id);
        return true;
      }).slice(0, MAX);
    } catch (_) { return fallback.slice(); }
  }
  function write(rows) {
    fallback = rows.slice(0, MAX);
    try { localStorage.setItem(KEY, JSON.stringify(fallback)); } catch (_) {}
    window.dispatchEvent(new Event('puti:orders-changed'));
  }
  function add(order_id, token) {
    if (typeof order_id !== 'string' || !ORDER.test(order_id) ||
        typeof token !== 'string' || token.length < 16 || token.length > 128) return;
    write([{ order_id, token, saved_at: Date.now() }, ...read().filter(r => r.order_id !== order_id)]);
  }
  function remove(order_id) { write(read().filter(r => r.order_id !== order_id)); }
  function secureCheckout() {
    if (!window.crypto || typeof crypto.getRandomValues !== 'function') {
      throw new Error('A secure browser connection is required. Open this store via HTTPS.');
    }
    function hex(bytes) {
      const data = new Uint8Array(bytes);
      crypto.getRandomValues(data);
      return Array.from(data, b => b.toString(16).padStart(2, '0')).join('');
    }
    return {order_id: 'PR' + hex(12).toUpperCase(), token: hex(32)};
  }
  function get(order_id) {
    if (!order_id) return null;
    const clean = String(order_id).trim().toUpperCase().replace(/^#/, '');
    return read().find(r => r.order_id && r.order_id.trim().toUpperCase().replace(/^#/, '') === clean) || null;
  }
  window.PutiOrders = Object.freeze({ read, add, remove, get, secureCheckout });
}());
