import asyncio
import base64
import hashlib
import hmac
import io
import ipaddress
import json
import math
import os
import re
import secrets
import smtplib
import ssl
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import httpx
import qrcode
from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
PUBLIC_DIR = BASE_DIR / "public"
MEDIA_DIR = PUBLIC_DIR / "media"

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(MEDIA_DIR, exist_ok=True)

# Optional .env loader (for Apsara Hosting / cloud panel deployments)
_env_file = BASE_DIR / ".env"
if _env_file.exists():
    try:
        for _line in _env_file.read_text(encoding="utf-8").splitlines():
            _line = _line.strip()
            if not _line or _line.startswith("#") or "=" not in _line:
                continue
            _k, _v = _line.split("=", 1)
            _k = _k.strip()
            _v = _v.strip().strip('"').strip("'")
            if _k and _k not in os.environ:
                os.environ[_k] = _v
    except Exception:
        pass

# File paths
DB_PATH = DATA_DIR / "orders.json"
PACKAGES_PATH = DATA_DIR / "packages.json"
SETTINGS_PATH = DATA_DIR / "settings.json"
GAMES_PATH = DATA_DIR / "games.json"
USERS_PATH = DATA_DIR / "users.json"
COUPONS_PATH = DATA_DIR / "coupons.json"
REVIEWS_PATH = DATA_DIR / "reviews.json"
WALLET_TX_PATH = DATA_DIR / "wallet_transactions.json"
INVENTORY_PATH = DATA_DIR / "inventory.json"
BLACKLIST_PATH = DATA_DIR / "blacklist.json"
ADMIN_SECURITY_PATH = DATA_DIR / "admin_security.json"
SPIN_PATH = DATA_DIR / "spin.json"

# In-memory data store
orders: List[Dict[str, Any]] = []
packages: List[Dict[str, Any]] = []
games: Dict[str, Dict[str, Any]] = {
    "roblox": {
        "id": "roblox",
        "name": "Roblox Robux Send",
        "category": "Roblox Robux",
        "kicker": "ROBLOX · ROBUX SEND",
        "unit": "Robux",
        "type": "roblox",
        "enabled": True,
        "logo": "/media/rolea-logo.webp",
        "banner": "/media/roblox-banner.webp",
        "badge": "HOT"
    },
    "mlbb": {
        "id": "mlbb",
        "name": "Mobile Legends: Bang Bang",
        "category": "Mobile Game",
        "kicker": "MOONTON · DIAMONDS",
        "unit": "Diamonds",
        "type": "mlbb",
        "enabled": True,
        "logo": "/media/mlbb-thumb.svg",
        "banner": "/media/banner1.webp",
        "badge": "POPULAR"
    },
    "tiktok": {
        "id": "tiktok",
        "name": "TikTok SMM Services",
        "category": "Social Media",
        "kicker": "TIKTOK · FOLLOWERS & LIKES",
        "unit": "Followers",
        "type": "smm",
        "enabled": True,
        "logo": "/media/tiktok-thumb.svg",
        "banner": "/media/banner1.webp",
        "badge": "PROMO"
    },
    "freefire": {
        "id": "freefire",
        "name": "Free Fire Diamonds",
        "category": "Mobile Game",
        "kicker": "GARENA · DIAMONDS",
        "unit": "Diamonds",
        "type": "freefire",
        "enabled": True,
        "logo": "/media/freefire-thumb.svg",
        "banner": "/media/banner1.webp",
        "badge": "FAST"
    }
}
settings: Dict[str, Any] = {
    "store_name": "Rolea Topup",
    "telegram_handle": "putireach",
    "khqr_merchant_name": "Rolea",
    "khqr_account": "bakong@rolea",
    "khqrpay_api_key": os.environ.get("KHQRPAY_API_KEY", ""),
    "khqrpay_base_url": "https://khqrpay.site",
    "home_banner": "/media/banner1.webp",
    "roblox_banner": "/media/roblox-banner.webp",
    "auto_deliver": True,
    "telegram_bot_token": os.environ.get("TELEGRAM_BOT_TOKEN", ""),
    "telegram_chat_id": "8710759437",
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 587,
    "smtp_email": "",
    "smtp_password": "",
    "admin_recovery_email": ""
}
users: List[Dict[str, Any]] = []
coupons: List[Dict[str, Any]] = []
reviews: List[Dict[str, Any]] = []
wallet_transactions: List[Dict[str, Any]] = []

# token -> {"userId": ..., "expiresAt": timestamp_ms}
sessions: Dict[str, Dict[str, Any]] = {}

def load_json(path: Path, default: Any) -> Any:
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading {path}: {e}")
    return default

def save_json(path: Path, data: Any):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving {path}: {e}")

# Load initial data
orders = load_json(DB_PATH, orders)
packages = load_json(PACKAGES_PATH, packages)
settings = load_json(SETTINGS_PATH, settings)
for _env_k, _set_k in (
    ("TELEGRAM_BOT_TOKEN", "telegram_bot_token"),
    ("KHQRPAY_API_KEY", "khqrpay_api_key"),
    ("SMTP_EMAIL", "smtp_email"),
    ("SMTP_PASSWORD", "smtp_password"),
):
    if not settings.get(_set_k) and os.environ.get(_env_k):
        settings[_set_k] = os.environ[_env_k]
games = load_json(GAMES_PATH, games)
users = load_json(USERS_PATH, users)
coupons = load_json(COUPONS_PATH, coupons)
reviews = load_json(REVIEWS_PATH, reviews)
wallet_transactions = load_json(WALLET_TX_PATH, wallet_transactions)
inventory: Dict[str, Any] = load_json(INVENTORY_PATH, {
    "manual_stock_enabled": False,
    "manual_stock_robux": 0,
    "low_stock_threshold": 5000,
    "telegram_alert_enabled": True,
    "last_alert_sent_at": None,
    "bots": [],
    "history": []
})

def save_orders(): save_json(DB_PATH, orders)
def init_default_spin_data() -> Dict[str, Any]:
    return {
        "enabled": True,
        "title": "Lucky Robux Wheel",
        "subtitle": "Spin to win instant Robux up to 1,000 R$!",
        "spin_price_usd": 0.50,
        "cost_per_1k_robux_usd": 4.00,
        "big_prize_threshold_robux": 100,
        "max_big_wins_per_day": 1,
        "min_spins_between_big_wins": 25,
        "require_profit_reserve": True,
        "spins_since_last_big_win": 0,
        "total_spins": 0,
        "total_revenue_usd": 0.0,
        "total_robux_awarded": 0,
        "slices": [
            {"id": "sl_1", "label": "Thank You", "robux": 0, "weight": 40.0, "color": "#475569", "text_color": "#ffffff"},
            {"id": "sl_2", "label": "10 Robux", "robux": 10, "weight": 30.0, "color": "#2563eb", "text_color": "#ffffff"},
            {"id": "sl_3", "label": "25 Robux", "robux": 25, "weight": 18.0, "color": "#0284c7", "text_color": "#ffffff"},
            {"id": "sl_4", "label": "50 Robux", "robux": 50, "weight": 8.0, "color": "#059669", "text_color": "#ffffff"},
            {"id": "sl_5", "label": "100 Robux", "robux": 100, "weight": 2.8, "color": "#7c3aed", "text_color": "#ffffff"},
            {"id": "sl_6", "label": "200 Robux", "robux": 200, "weight": 0.9, "color": "#d97706", "text_color": "#ffffff"},
            {"id": "sl_7", "label": "500 Robux", "robux": 500, "weight": 0.25, "color": "#e11d48", "text_color": "#ffffff"},
            {"id": "sl_8", "label": "1,000 R$ JACKPOT", "robux": 1000, "weight": 0.05, "color": "#f59e0b", "text_color": "#0f172a"}
        ],
        "history": []
    }

spin_data: Dict[str, Any] = load_json(SPIN_PATH, None)
if not spin_data or not isinstance(spin_data.get("slices"), list) or len(spin_data["slices"]) == 0:
    spin_data = init_default_spin_data()
    save_json(SPIN_PATH, spin_data)

pending_spin_tickets: Dict[str, Dict[str, Any]] = {}

def save_spin_data():
    save_json(SPIN_PATH, spin_data)

def perform_spin_roll(sim_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Weighted server-side spin roll with Anti-Big-Prize Guard (មិនឲ្យងាយត្រូវអាធំៗ)."""
    state = sim_state if sim_state is not None else spin_data
    slices = state.get("slices", [])
    if not slices:
        return {"slice_index": 0, "slice": {"id": "sl_0", "label": "Thank You", "robux": 0, "weight": 100, "color": "#475569", "text_color": "#ffffff"}, "guard_triggered": False}

    sys_rng = secrets.SystemRandom()
    weights = [max(0.0, float(s.get("weight", 0))) for s in slices]
    total_w = sum(weights)
    if total_w <= 0:
        weights = [1.0] * len(slices)
        total_w = float(len(slices))

    r_val = sys_rng.uniform(0.0, total_w)
    upto = 0.0
    chosen_idx = 0
    for idx, w in enumerate(weights):
        upto += w
        if r_val <= upto:
            chosen_idx = idx
            break

    chosen_slice = slices[chosen_idx]
    big_thresh = int(state.get("big_prize_threshold_robux", 100))
    prize_robux = int(chosen_slice.get("robux", 0))
    guard_triggered = False

    if prize_robux >= big_thresh and big_thresh > 0:
        blocked_by_guard = False
        max_per_day = int(state.get("max_big_wins_per_day", 1))
        min_cooldown = int(state.get("min_spins_between_big_wins", 25))
        require_reserve = bool(state.get("require_profit_reserve", True))
        spins_since = int(state.get("spins_since_last_big_win", 0))

        # Check 1: Cooldown between big wins
        if spins_since < min_cooldown:
            blocked_by_guard = True

        # Check 2: Max big wins today
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if max_per_day <= 0:
            blocked_by_guard = True
        else:
            big_today = sum(
                1 for h in state.get("history", [])
                if int(h.get("robux", 0)) >= big_thresh and str(h.get("created_at", "")).startswith(today_str)
            )
            if big_today >= max_per_day:
                blocked_by_guard = True

        # Check 3: Profit reserve buffer (never let the store go into net loss)
        if require_reserve:
            cost_per_r = float(state.get("cost_per_1k_robux_usd", 4.0)) / 1000.0
            rev = float(state.get("total_revenue_usd", 0.0)) + float(state.get("spin_price_usd", 0.50))
            paid_cost = float(state.get("total_robux_awarded", 0)) * cost_per_r
            needed_cost = prize_robux * cost_per_r
            if (rev - paid_cost) < needed_cost:
                blocked_by_guard = True

        if blocked_by_guard:
            guard_triggered = True
            # Fall back to weighted non-big slices (small prizes / Thank You)
            small_indices = [i for i, s in enumerate(slices) if int(s.get("robux", 0)) < big_thresh]
            if small_indices:
                small_weights = [max(0.01, float(slices[i].get("weight", 0))) for i in small_indices]
                sw_total = sum(small_weights)
                sr = sys_rng.uniform(0.0, sw_total)
                supto = 0.0
                for si, sw in zip(small_indices, small_weights):
                    supto += sw
                    if sr <= supto:
                        chosen_idx = si
                        chosen_slice = slices[si]
                        break

    final_robux = int(chosen_slice.get("robux", 0))
    if final_robux >= big_thresh and big_thresh > 0:
        state["spins_since_last_big_win"] = 0
    else:
        state["spins_since_last_big_win"] = int(state.get("spins_since_last_big_win", 0)) + 1

    state["total_spins"] = int(state.get("total_spins", 0)) + 1
    state["total_revenue_usd"] = round(float(state.get("total_revenue_usd", 0.0)) + float(state.get("spin_price_usd", 0.50)), 4)
    state["total_robux_awarded"] = int(state.get("total_robux_awarded", 0)) + final_robux

    return {
        "slice_index": chosen_idx,
        "slice": chosen_slice,
        "guard_triggered": guard_triggered
    }

blacklist: Dict[str, Any] = load_json(BLACKLIST_PATH, {
    "blocked_users": [],
    "blocked_ips": [],
    "blocked_emails": [],
    "rules": {
        "block_duplicate_unpaid_orders": True,
        "max_unpaid_orders_per_ip": 5,
        "auto_flag_suspicious": True
    },
    "logs": []
})

def save_inventory(): save_json(INVENTORY_PATH, inventory)
def save_blacklist(): save_json(BLACKLIST_PATH, blacklist)
def save_packages(): save_json(PACKAGES_PATH, packages)
def save_settings(): save_json(SETTINGS_PATH, settings)
def save_games(): save_json(GAMES_PATH, games)
def save_users(): save_json(USERS_PATH, users)
def save_coupons(): save_json(COUPONS_PATH, coupons)
def save_reviews(): save_json(REVIEWS_PATH, reviews)
def save_wallet_tx(): save_json(WALLET_TX_PATH, wallet_transactions)

# Admin Security & Session Management
admin_failed_attempts: Dict[str, List[float]] = {}
admin_lockouts: Dict[str, float] = {}

def hash_admin_secret(secret_val: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", secret_val.encode("utf-8"), salt.encode("utf-8"), 120000).hex()

def hash_session_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

def init_default_admin_security() -> Dict[str, Any]:
    salt = secrets.token_hex(16)
    return {
        "username": "admin",
        "password_salt": salt,
        "password_hash": hash_admin_secret("admin123", salt),
        "is_default_password": True,
        "pin_enabled": False,
        "pin_salt": "",
        "pin_hash": "",
        "session_timeout_hours": 24,
        "telegram_login_alert": True,
        "sessions": {},
        "login_logs": []
    }

admin_security: Dict[str, Any] = load_json(ADMIN_SECURITY_PATH, None)
if not admin_security or not admin_security.get("password_hash"):
    admin_security = init_default_admin_security()
    save_json(ADMIN_SECURITY_PATH, admin_security)

def save_admin_security():
    save_json(ADMIN_SECURITY_PATH, admin_security)

def cleanup_expired_admin_sessions():
    now_ms = int(time.time() * 1000)
    sessions_map = admin_security.setdefault("sessions", {})
    expired = [k for k, v in sessions_map.items() if v.get("expires_at", 0) < now_ms]
    if expired:
        for k in expired:
            sessions_map.pop(k, None)
        save_admin_security()

def log_admin_security_event(event: str, ip: str, username: str, status_str: str, details: str = ""):
    logs = admin_security.setdefault("login_logs", [])
    logs.insert(0, {
        "time": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "ip": ip,
        "username": username,
        "status": status_str,
        "details": details
    })
    if len(logs) > 30:
        admin_security["login_logs"] = logs[:30]
    save_admin_security()

def extract_admin_token(request: Request) -> Optional[str]:
    auth_header = request.headers.get("authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:].strip()
    if "rolea_admin_token" in request.cookies:
        return request.cookies.get("rolea_admin_token", "").strip()
    return None

def verify_admin_session(request: Request) -> Optional[str]:
    raw_token = extract_admin_token(request)
    if not raw_token:
        return None
    token_hash = hash_session_token(raw_token)
    sessions_map = admin_security.get("sessions", {})
    sess = sessions_map.get(token_hash)
    if not sess:
        return None
    if sess.get("expires_at", 0) < int(time.time() * 1000):
        sessions_map.pop(token_hash, None)
        save_admin_security()
        return None
    return token_hash

async def send_admin_security_telegram(message_text: str):
    if not admin_security.get("telegram_login_alert", True):
        return
    token = settings.get("telegram_bot_token")
    chat_id = settings.get("telegram_chat_id")
    if token and chat_id:
        await send_telegram_direct_message(token, chat_id, message_text)

# Helper functions
def hash_password(password: str) -> str:
    salt = "ROLEA_SECURE_SALT_2026"
    return hashlib.sha256((password + salt).encode("utf-8")).hexdigest()

def get_user_from_req(request: Request) -> Optional[Dict[str, Any]]:
    token = None
    auth_header = request.headers.get("authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    elif request.headers.get("x-auth-token"):
        token = request.headers.get("x-auth-token", "").strip()
    elif "rolea_token" in request.cookies:
        token = request.cookies.get("rolea_token", "").strip()

    if not token or token not in sessions:
        return None

    sess = sessions[token]
    if sess.get("expiresAt", 0) < int(time.time() * 1000):
        del sessions[token]
        return None

    user_id = sess.get("userId")
    for u in users:
        if u.get("id") == user_id:
            return u
    return None

def generate_khqr_data_url(khqr_payload: str) -> str:
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=2,
    )
    qr.add_data(khqr_payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#10234b", back_color="#ffffff")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{b64}"

# External API helpers
async def create_khqrpay_order(amount: float, order_id: str) -> Optional[Dict[str, Any]]:
    base_url = (settings.get("khqrpay_base_url") or "https://khqrpay.site").rstrip("/")
    api_key = settings.get("khqrpay_api_key") or os.environ.get("KHQRPAY_API_KEY", "")
    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            res = await client.post(
                f"{base_url}/api/v1/aba/create",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "X-Api-Key": api_key,
                    "Content-Type": "application/json"
                },
                json={"amount": float(amount), "order_id": str(order_id)}
            )
            data = res.json()
            if data and (data.get("ok") or data.get("id")):
                return data
            print("[KHQRPay] Create returned non-ok:", data)
    except Exception as err:
        print("[KHQRPay] Error creating payment:", err)
    return None

async def check_khqrpay_status(payment_id: str) -> Optional[Dict[str, Any]]:
    base_url = (settings.get("khqrpay_base_url") or "https://khqrpay.site").rstrip("/")
    api_key = settings.get("khqrpay_api_key") or os.environ.get("KHQRPAY_API_KEY", "")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            res = await client.get(
                f"{base_url}/api/v1/payment",
                params={"id": payment_id},
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "X-Api-Key": api_key
                }
            )
            data = res.json()
            if data and (data.get("ok") or data.get("payment")):
                return data.get("payment") or data
    except Exception as err:
        print("[KHQRPay] Error checking payment status:", err)
    return None

# Telegram integration
async def send_telegram_paid_alert(order: Dict[str, Any]):
    if not order or order.get("telegram_alerted"):
        return
    # Only alert when user buys products (Robux, SMM), NOT wallet deposits
    if order.get("type") == "wallet_topup" or order.get("product_type") == "wallet" or str(order.get("order_id", "")).startswith("WLT"):
        return

    token = settings.get("telegram_bot_token") or os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = settings.get("telegram_chat_id") or "8710759437"
    if not token or not chat_id:
        return

    g = games.get(order.get("game", "roblox"), {})
    game_name = g.get("name") or order.get("game") or "Rolea Topup"
    customer = order.get("roblox_username") or order.get("username") or order.get("display_name") or "Customer"
    amount = f"{float(order.get('amount') or order.get('price') or 0):.2f}"
    pkg_name = order.get("package") or f"{order.get('robux_amount', '')} {g.get('unit', 'Units')}".strip()
    pay_method = order.get("payment_method") or "ABA KHQR"

    is_tiktok = (order.get("game") == "tiktok") or (order.get("product_type") == "smm") or str(order.get("player_id", "")).startswith("http")
    target_link = order.get("target_url") or order.get("player_id") or order.get("roblox_username") or ""

    if is_tiktok:
        account_line = f"🔗 <b>Video Link:</b> {target_link}"
    else:
        account_line = f"👤 <b>Account:</b> {customer}"

    try:
        dt = datetime.fromisoformat(order.get("created_at", datetime.now(timezone.utc).isoformat()).replace("Z", "+00:00"))
        time_str = dt.astimezone(timezone(timedelta(hours=7))).strftime("%m/%d/%Y, %I:%M:%S %p")
    except Exception:
        time_str = datetime.now().strftime("%m/%d/%Y, %I:%M:%S %p")

    message = (
        f"🔔 <b>[PAID ORDER NOTIFICATION]</b>\n"
        f"🏪 <b>Store:</b> {settings.get('store_name', 'Rolea Topup')}\n"
        f"🆔 <b>Order ID:</b> <code>{order.get('order_id')}</code>\n"
        f"🎮 <b>Game/Service:</b> {game_name}\n"
        f"{account_line}\n"
        f"📦 <b>Package:</b> {pkg_name}\n"
        f"💵 <b>Amount:</b> ${amount} USD\n"
        f"💳 <b>Payment Gateway:</b> {pay_method}\n"
        f"⚡ <b>Status:</b> PAID - AWAITING ADMIN DELIVERY\n"
        f"🕒 <b>Time:</b> {time_str}"
    )

    inline_keyboard = []
    if is_tiktok and target_link.startswith("http"):
        inline_keyboard.append([{"text": "🎬 Open TikTok Video", "url": target_link}])
    inline_keyboard.append([
        {"text": "✅ Complete Order", "callback_data": f"complete:{order.get('order_id')}"},
        {"text": "❌ Reject & Refund", "callback_data": f"reject:{order.get('order_id')}"}
    ])

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "reply_markup": {
            "inline_keyboard": inline_keyboard
        }
    }

    for attempt in range(1, 4):
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(url, json=payload)
                data = res.json()
                if data and data.get("ok"):
                    order["telegram_alerted"] = True
                    save_orders()
                    print(f"Telegram paid alert sent successfully for order {order.get('order_id')}")
                    return
                else:
                    print(f"Telegram alert attempt {attempt} error:", data)
        except Exception as err:
            print(f"Telegram alert attempt {attempt} failed: {err}")
        await asyncio.sleep(2.0)



def build_password_reset_email_html(store_name: str, account_name: str, otp_code: str, client_ip: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background-color:#0f172a;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#0f172a;padding:32px 16px;">
    <tr>
      <td align="center">
        <table width="100%" cellpadding="0" cellspacing="0" style="max-width:540px;background-color:#1e293b;border:1px solid #334155;border-radius:16px;overflow:hidden;">
          <tr>
            <td style="padding:28px 28px 18px;border-bottom:1px solid #334155;">
              <div style="font-size:24px;font-weight:900;letter-spacing:1.2px;color:#ffffff;">{store_name.upper()}</div>
              <div style="font-size:12px;font-weight:700;color:#38bdf8;margin-top:4px;letter-spacing:0.6px;text-transform:uppercase;">Account Password Recovery</div>
            </td>
          </tr>
          <tr>
            <td style="padding:28px;color:#e2e8f0;font-size:15px;line-height:1.6;">
              <h1 style="margin:0 0 18px;font-size:22px;font-weight:800;color:#ffffff;">Password Reset Code: {otp_code}</h1>
              <div style="background-color:#0f172a;border:1px solid #334155;border-radius:12px;padding:18px;text-align:center;margin:0 0 20px;">
                <div style="font-size:11px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;">Code Requested</div>
                <div style="font-family:'Courier New',Courier,monospace;font-size:32px;font-weight:900;letter-spacing:8px;color:#ffffff;">{otp_code}</div>
              </div>
              <p style="margin:0 0 12px;">Hello, <b style="color:#ffffff;">{account_name}</b></p>
              <p style="margin:0 0 12px;">A password reset code was requested for your {store_name} account <b style="color:#ffffff;">{account_name}</b>.</p>
              <p style="margin:0 0 12px;color:#cbd5e1;">This request was received from IP <b style="color:#ffffff;">{client_ip}</b>. This code is valid for 10 minutes.</p>
              <p style="margin:18px 0 0;font-size:13px;color:#94a3b8;border-top:1px solid #334155;padding-top:16px;">
                <b style="color:#f8fafc;">IMPORTANT:</b> Don't share your password reset code with anyone — including on a call, screen share, or in a text message.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

def _send_smtp_sync(host: str, port: int, sender: str, password: str, to_email: str, subject: str, html_body: str, text_body: str) -> tuple[bool, str]:
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{settings.get('store_name', 'Rolea Topup')} <{sender}>"
        msg["To"] = to_email
        msg.attach(MIMEText(text_body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        clean_pw = password.replace(" ", "")
        context = ssl.create_default_context()
        if int(port) == 465:
            with smtplib.SMTP_SSL(host, int(port), context=context, timeout=12) as server:
                server.login(sender, clean_pw)
                server.sendmail(sender, [to_email], msg.as_string())
        else:
            with smtplib.SMTP(host, int(port), timeout=12) as server:
                server.ehlo()
                server.starttls(context=context)
                server.ehlo()
                server.login(sender, clean_pw)
                server.sendmail(sender, [to_email], msg.as_string())
        return True, "Sent"
    except Exception as e:
        return False, str(e)

async def send_smtp_email(to_email: str, subject: str, html_body: str, text_body: str) -> tuple[bool, str]:
    host = str(settings.get("smtp_host") or "smtp.gmail.com").strip()
    port = int(settings.get("smtp_port") or 587)
    sender = str(settings.get("smtp_email") or "").strip()
    password = str(settings.get("smtp_password") or "").strip()
    if not sender or not password:
        return False, "SMTP email & App Password not configured"
    return await asyncio.to_thread(_send_smtp_sync, host, port, sender, password, to_email, subject, html_body, text_body)

async def answer_callback_query(token: str, query_id: str, text: str):
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                f"https://api.telegram.org/bot{token}/answerCallbackQuery",
                json={"callback_query_id": query_id, "text": text, "show_alert": False}
            )
    except Exception:
        pass

async def edit_telegram_message(token: str, chat_id: Any, message_id: Any, text: str):
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                f"https://api.telegram.org/bot{token}/editMessageText",
                json={
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "text": text,
                    "parse_mode": "HTML"
                }
            )
    except Exception:
        pass


async def send_telegram_direct_message(token: str, chat_id: Union[int, str], text: str, reply_markup: Optional[Dict] = None):
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        async with httpx.AsyncClient(timeout=8.0) as client:
            await client.post(url, json=payload)
    except Exception as e:
        print(f"Customer telegram msg error: {e}")

async def notify_customer_order_completed(order: Dict[str, Any]):
    token = settings.get("telegram_bot_token") or os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token or not order:
        return
    chat_id = order.get("customer_telegram_chat_id")
    if not chat_id and order.get("user_id"):
        u = next((usr for usr in users if usr.get("id") == order.get("user_id")), None)
        if u and u.get("telegram_chat_id"):
            chat_id = u.get("telegram_chat_id")
    if not chat_id:
        return

    g = games.get(order.get("game", "roblox"), {})
    game_name = g.get("name") or order.get("game") or "Rolea Topup"
    customer = order.get("roblox_username") or order.get("username") or order.get("display_name") or "Customer"
    pkg = order.get("package") or f"{order.get('robux_amount', '')} {g.get('unit', 'Units')}".strip()
    amount = f"{float(order.get('amount') or order.get('price') or 0):.2f}"

    text = (
        f"<b>ORDER DELIVERED SUCCESSFULLY</b>\n\n"
        f"Hello <b>{customer}</b>, your order has been completed and delivered!\n\n"
        f"<b>Order ID:</b> <code>#{order.get('order_id')}</code>\n"
        f"<b>Product:</b> {pkg} ({game_name})\n"
        f"<b>Amount:</b> ${amount} USD\n"
        f"<b>Status:</b> Completed & Delivered\n\n"
        f"Thank you for shopping at {settings.get('store_name', 'Rolea Topup')}!"
    )
    await send_telegram_direct_message(token, chat_id, text)

async def notify_customer_order_refunded(order: Dict[str, Any]):
    token = settings.get("telegram_bot_token") or os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token or not order:
        return
    chat_id = order.get("customer_telegram_chat_id")
    if not chat_id and order.get("user_id"):
        u = next((usr for usr in users if usr.get("id") == order.get("user_id")), None)
        if u and u.get("telegram_chat_id"):
            chat_id = u.get("telegram_chat_id")
    if not chat_id:
        return

    amount = f"{float(order.get('amount') or order.get('price') or 0):.2f}"
    text = (
        f"<b>ORDER STATUS UPDATE: REFUNDED</b>\n\n"
        f"Your order <code>#{order.get('order_id')}</code> has been refunded.\n\n"
        f"<b>Amount:</b> ${amount} USD\n"
        f"<b>Status:</b> Refunded\n\n"
        f"If paid via Rolea Wallet, your balance has been restored. Contact support if you need further help."
    )
    await send_telegram_direct_message(token, chat_id, text)

async def handle_telegram_callback_query(query: Dict[str, Any], token: str):
    query_id = query.get("id")
    data = query.get("data", "")
    from_id = str(query.get("from", {}).get("id"))
    target_chat_id = str(settings.get("telegram_chat_id") or "8710759437")

    if from_id != target_chat_id:
        await answer_callback_query(token, query_id, "Unauthorized: Admin action only.")
        return

    parts = data.split(":")
    if len(parts) < 2:
        await answer_callback_query(token, query_id, "Invalid request data.")
        return

    action, order_id = parts[0], parts[1]
    order = next((o for o in orders if o.get("order_id") == order_id), None)
    if not order:
        await answer_callback_query(token, query_id, "Order not found.")
        return

    now_ict = datetime.now(timezone(timedelta(hours=7))).strftime("%m/%d/%Y, %I:%M:%S %p")
    g = games.get(order.get("game", "roblox"), {})
    game_name = g.get("name") or order.get("game") or "Rolea Topup"
    customer = order.get("roblox_username") or order.get("username") or order.get("display_name") or "Customer"
    amount = f"{float(order.get('amount') or order.get('price') or 0):.2f}"
    pkg_name = order.get("package") or f"{order.get('robux_amount', '')} {g.get('unit', 'Units')}".strip()
    from_user = query.get("from", {})
    admin_name = f"@{from_user['username']}" if from_user.get("username") else (from_user.get("first_name") or "Admin")

    if action == "complete":
        order["paid"] = True
        order["delivered"] = True
        order["status"] = "completed"
        order["step"] = "delivered"
        order["label"] = "Order fulfilled and confirmed by Admin via Telegram"
        save_orders()
        asyncio.create_task(notify_customer_order_completed(order))

        await answer_callback_query(token, query_id, f"✅ Order #{order_id} marked as Completed!")

        updated_text = (
            f"✅ <b>[ORDER COMPLETED BY ADMIN]</b>\n"
            f"🏪 <b>Store:</b> {settings.get('store_name', 'Rolea Topup')}\n"
            f"🆔 <b>Order ID:</b> <code>{order.get('order_id')}</code>\n"
            f"🎮 <b>Game:</b> {game_name}\n"
            f"👤 <b>Account:</b> {customer}\n"
            f"📦 <b>Package:</b> {pkg_name}\n"
            f"💵 <b>Amount:</b> ${amount} USD\n"
            f"🎉 <b>Status:</b> COMPLETED & DELIVERED\n"
            f"👮 <b>Action By:</b> {admin_name}\n"
            f"🕒 <b>Action Time:</b> {now_ict}"
        )
        if query.get("message"):
            msg = query["message"]
            await edit_telegram_message(token, msg["chat"]["id"], msg["message_id"], updated_text)

    elif action == "reject":
        order["status"] = "refunded"
        order["step"] = "refunded"
        order["delivered"] = False
        order["label"] = "Order rejected and refunded to customer by Admin"
        if order.get("payment_method") == "Rolea Wallet" and order.get("user_id"):
            u = next((usr for usr in users if usr.get("id") == order.get("user_id")), None)
            if u:
                u["balance"] = round(float(u.get("balance", 0.0)) + float(order["amount"]), 2)
                save_users()
                wallet_transactions.insert(0, {
                    "id": "wtx_" + secrets.token_hex(4),
                    "user_id": u["id"],
                    "type": "deposit",
                    "amount": float(order["amount"]),
                    "order_id": order["order_id"],
                    "product": f"Refund for Order #{order['order_id']}",
                    "date": datetime.now(timezone.utc).isoformat()
                })
                save_wallet_tx()
        save_orders()
        asyncio.create_task(notify_customer_order_refunded(order))

        await answer_callback_query(token, query_id, f"⚠️ Order #{order_id} Rejected & Refunded!")

        updated_text = (
            f"❌ <b>[ORDER REJECTED & REFUNDED]</b>\n"
            f"🏪 <b>Store:</b> {settings.get('store_name', 'Rolea Topup')}\n"
            f"🆔 <b>Order ID:</b> <code>{order.get('order_id')}</code>\n"
            f"🎮 <b>Game:</b> {game_name}\n"
            f"👤 <b>Account:</b> {customer}\n"
            f"📦 <b>Package:</b> {pkg_name}\n"
            f"💵 <b>Amount:</b> ${amount} USD\n"
            f"🚫 <b>Status:</b> REJECTED & REFUNDED\n"
            f"👮 <b>Action By:</b> {admin_name}\n"
            f"🕒 <b>Action Time:</b> {now_ict}"
        )
        if query.get("message"):
            msg = query["message"]
            await edit_telegram_message(token, msg["chat"]["id"], msg["message_id"], updated_text)

telegram_offset = 0
async def telegram_polling_loop():
    global telegram_offset
    while True:
        try:
            token = settings.get("telegram_bot_token") or os.environ.get("TELEGRAM_BOT_TOKEN", "")
            if token:
                url = f"https://api.telegram.org/bot{token}/getUpdates?offset={telegram_offset}&timeout=5"
                async with httpx.AsyncClient(timeout=8.0) as client:
                    resp = await client.get(url)
                    j = resp.json()
                    if j and j.get("ok") and isinstance(j.get("result"), list):
                        for update in j["result"]:
                            telegram_offset = update["update_id"] + 1
                            if "callback_query" in update:
                                await handle_telegram_callback_query(update["callback_query"], token)
                            elif "message" in update:
                                msg = update["message"]
                                chat_id = str(msg.get("chat", {}).get("id"))
                                text = (msg.get("text") or "").strip()
                                if text.startswith("/start"):
                                    parts = text.split(maxsplit=1)
                                    param = parts[1].strip() if len(parts) > 1 else ""
                                    if param:
                                        target_order = next((o for o in orders if o.get("order_id") == param or o.get("order_id") == f"ORD-{param}"), None)
                                        if target_order:
                                            target_order["customer_telegram_chat_id"] = chat_id
                                            save_orders()
                                            if target_order.get("user_id"):
                                                u = next((usr for usr in users if usr.get("id") == target_order.get("user_id")), None)
                                                if u:
                                                    u["telegram_chat_id"] = chat_id
                                                    save_users()
                                            st = target_order.get("status", "pending").upper()
                                            rep = (
                                                f"Welcome to <b>{settings.get('store_name', 'Rolea Topup')}</b>!\n\n"
                                                f"You are now subscribed to live delivery alerts for Order <code>#{target_order.get('order_id')}</code>.\n\n"
                                                f"<b>Package:</b> {target_order.get('package')}\n"
                                                f"<b>Amount:</b> ${float(target_order.get('amount') or 0):.2f} USD\n"
                                                f"<b>Status:</b> {st}\n\n"
                                                f"We will message you right here as soon as your items are delivered."
                                            )
                                            await send_telegram_direct_message(token, chat_id, rep)
                                        else:
                                            rep = (
                                                f"Welcome to <b>{settings.get('store_name', 'Rolea Topup')}</b>!\n\n"
                                                f"Order <code>#{param}</code> was not found. Please verify your order ID or use <code>/track &lt;ORDER_ID&gt;</code>."
                                            )
                                            await send_telegram_direct_message(token, chat_id, rep)
                                    else:
                                        rep = (
                                            f"Welcome to <b>{settings.get('store_name', 'Rolea Topup')} Bot</b>!\n\n"
                                            f"Track orders and get instant delivery notifications.\n\n"
                                            f"• Send <code>/track &lt;ORDER_ID&gt;</code> to link your order and check real-time status.\n\n"
                                            f"Website: http://localhost:3000"
                                        )
                                        await send_telegram_direct_message(token, chat_id, rep)
                                elif text.startswith("/track"):
                                    parts = text.split(maxsplit=1)
                                    param = parts[1].strip() if len(parts) > 1 else ""
                                    if param:
                                        target_order = next((o for o in orders if o.get("order_id") == param or o.get("order_id") == f"ORD-{param}"), None)
                                        if target_order:
                                            target_order["customer_telegram_chat_id"] = chat_id
                                            save_orders()
                                            st = target_order.get("status", "pending").upper()
                                            deliv = "Delivered" if target_order.get("delivered") else "In Progress"
                                            rep = (
                                                f"<b>Order #{target_order.get('order_id')}</b>\n\n"
                                                f"<b>Product:</b> {target_order.get('package')}\n"
                                                f"<b>Amount:</b> ${float(target_order.get('amount') or 0):.2f} USD\n"
                                                f"<b>Status:</b> {st} ({deliv})\n"
                                                f"<b>Date:</b> {target_order.get('created_at') or 'Recent'}\n\n"
                                                f"Notifications are active for this chat."
                                            )
                                            await send_telegram_direct_message(token, chat_id, rep)
                                        else:
                                            await send_telegram_direct_message(token, chat_id, f"Order <code>#{param}</code> not found.")
                                    else:
                                        await send_telegram_direct_message(token, chat_id, "Please provide an Order ID: <code>/track ORD-123456</code>")
        except Exception:
            pass
        await asyncio.sleep(3.5)

# Security Concurrency & Anti-DDoS Guards
_tx_lock = asyncio.Lock()
_rate_buckets: Dict[str, List[float]] = {}
_credited_khqr_ids: set = set()

MAX_JSON_BODY_BYTES = 2 * 1024 * 1024   # 2 MB limit on public/API payloads
MAX_UPLOAD_BODY_BYTES = 10 * 1024 * 1024  # 10 MB limit for admin image uploads

def _sanitize_plain(val: Any, max_len: int = 200) -> str:
    s = str(val or "").strip()
    s = re.sub(r"<[^>]*>", "", s)
    s = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", s)
    return s[:max_len]

def _get_rate_tier(path: str) -> tuple[str, int, int]:
    if path in (
        "/api/auth/forgot-password", "/api/auth/verify-reset-code", "/api/auth/reset-password",
        "/api/admin/forgot-password", "/api/admin/verify-reset-code", "/api/admin/reset-password"
    ):
        return ("otp", 8, 60)
    if path in ("/api/auth/login", "/api/auth/register", "/api/auth/google", "/api/admin/login"):
        return ("auth", 15, 60)
    if path in ("/api/create-order", "/api/wallet/topup", "/api/spin/create-ticket"):
        return ("pay_create", 15, 60)
    if path in ("/api/check-id", "/api/promo/apply", "/api/check-order", "/api/reviews/submit"):
        return ("lookup", 30, 60)
    if path.startswith("/api/"):
        return ("api_general", 120, 60)
    return ("static", 300, 60)

def _check_rate_limit(ip: str, path: str) -> tuple[bool, int]:
    tier, max_req, window_sec = _get_rate_tier(path)
    now_ts = time.time()
    key = f"{tier}:{ip}"
    if len(_rate_buckets) > 10000:
        stale_keys = [k for k, v in _rate_buckets.items() if not v or (now_ts - v[-1]) > 120]
        for k in stale_keys[:5000]:
            _rate_buckets.pop(k, None)
        if len(_rate_buckets) > 10000:
            _rate_buckets.clear()

    hist = [t for t in _rate_buckets.get(key, []) if now_ts - t < window_sec]
    if len(hist) >= max_req:
        retry_after = max(1, int(window_sec - (now_ts - hist[0])))
        _rate_buckets[key] = hist
        return False, retry_after
    hist.append(now_ts)
    _rate_buckets[key] = hist
    return True, 0

def verify_khqr_bank_payment(live: Optional[Dict[str, Any]], expected_amount: float) -> tuple[bool, str]:
    """Strict server-side bank/KHQR verification (status + paid amount + currency + non-negative guard)."""
    if not isinstance(live, dict):
        return False, "invalid_payload"
    st = str(live.get("status", "")).lower().strip()
    if st not in ("paid", "success", "completed"):
        return False, st or "pending"

    raw_amt = live.get("amount")
    if raw_amt is not None:
        try:
            paid_amt = float(raw_amt)
        except (ValueError, TypeError):
            return False, "invalid_amount"
        if not math.isfinite(paid_amt) or paid_amt < round(float(expected_amount) - 0.01, 2):
            return False, "amount_mismatch"

    curr = str(live.get("currency") or "USD").upper().strip()
    if curr not in ("USD", ""):
        return False, "currency_mismatch"

    return True, "paid"

# Initialize FastAPI App
app = FastAPI(title="Rolea Topup API", version="2.0.0")

HOME_WIFI_NETWORK = ipaddress.ip_network("192.168.100.0/24", strict=False)
_blocked_ip_log_cooldown: Dict[str, float] = {}

def _get_extra_admin_networks() -> List[Any]:
    raw = os.environ.get("ADMIN_ALLOWED_IPS", "").strip()
    nets = []
    for part in raw.split(","):
        part = part.strip()
        if not part or part == "*":
            continue
        try:
            nets.append(ipaddress.ip_network(part, strict=False))
        except ValueError:
            pass
    return nets

def _is_single_ip_allowed(ip_str: str) -> bool:
    if not ip_str:
        return False
    try:
        ip_obj = ipaddress.ip_address(ip_str)
        if getattr(ip_obj, "ipv4_mapped", None):
            ip_obj = ip_obj.ipv4_mapped
        if ip_obj.is_loopback:
            return True
        if isinstance(ip_obj, ipaddress.IPv4Address) and ip_obj in HOME_WIFI_NETWORK:
            return True
        for net in _get_extra_admin_networks():
            if ip_obj in net:
                return True
    except ValueError:
        return False
    return False

def _is_trusted_proxy_peer(ip_str: str) -> bool:
    if not ip_str:
        return False
    try:
        ip_obj = ipaddress.ip_address(ip_str)
        if getattr(ip_obj, "ipv4_mapped", None):
            ip_obj = ip_obj.ipv4_mapped
        return ip_obj.is_loopback or ip_obj.is_private
    except ValueError:
        return False

def get_admin_effective_ip(request: Request) -> str:
    cf_ip = request.headers.get("cf-connecting-ip", "").strip()
    xff = request.headers.get("x-forwarded-for", "").strip()
    x_real = request.headers.get("x-real-ip", "").strip()
    if cf_ip:
        return cf_ip
    if xff:
        return xff.split(",")[0].strip()
    if x_real:
        return x_real
    return request.client.host if request.client else ""

def is_admin_ip_allowed(request: Request) -> tuple[bool, str]:
    effective_ip = get_admin_effective_ip(request)
    allowed_env = os.environ.get("ADMIN_ALLOWED_IPS", "").strip()
    if allowed_env == "*" or settings.get("admin_ip_restriction") is False:
        return True, effective_ip or "remote"
    # On managed Python hosts (e.g., Apsara Hosting / Pterodactyl setting SERVER_PORT),
    # allow remote Admin login protected by PBKDF2 + 2FA + lockout unless ADMIN_ALLOWED_IPS restricts it.
    if os.environ.get("SERVER_PORT") and not allowed_env:
        return True, effective_ip or "cloud"

    peer_ip = request.client.host if request.client else ""
    if not (_is_single_ip_allowed(peer_ip) or _is_trusted_proxy_peer(peer_ip)):
        return False, peer_ip or "unknown"
    if not _is_single_ip_allowed(effective_ip):
        return False, effective_ip or "unknown"
    return True, effective_ip

@app.middleware("http")
async def security_and_no_cache_middleware(request: Request, call_next):
    path = request.url.path
    raw_qs = request.url.query or ""

    # 1. Path traversal / null-byte guard
    if ".." in path or "\x00" in path or "%00" in path.lower() or ".." in raw_qs:
        return JSONResponse(status_code=400, content={"ok": False, "error": "Invalid request path"})

    # 2. Request payload size guard (Anti-Payload Flood)
    cl_hdr = request.headers.get("content-length")
    if cl_hdr:
        try:
            cl_val = int(cl_hdr)
            is_upload = path in ("/api/admin/upload-banner", "/api/admin/games/upload-logo")
            max_bytes = MAX_UPLOAD_BODY_BYTES if is_upload else MAX_JSON_BODY_BYTES
            if cl_val > max_bytes or cl_val < 0:
                return JSONResponse(status_code=413, content={"ok": False, "error": "Payload too large"})
        except ValueError:
            return JSONResponse(status_code=400, content={"ok": False, "error": "Invalid Content-Length"})

    # 3. Anti-DDoS sliding-window rate limiter per client IP
    eff_ip = get_admin_effective_ip(request) or "unknown"
    ok_rate, retry_after = _check_rate_limit(eff_ip, path)
    if not ok_rate:
        return JSONResponse(
            status_code=429,
            headers={"Retry-After": str(retry_after)},
            content={"ok": False, "error": f"Too many requests. Please wait {retry_after}s and try again."}
        )

    is_admin_route = (
        path == "/admin"
        or path.startswith("/admin/")
        or path.startswith("/api/admin")
        or path in ("/admin.html", "/admin_login.html")
    )

    if is_admin_route:
        allowed, blocked_ip = is_admin_ip_allowed(request)
        if not allowed:
            now_ts = time.time()
            if now_ts - _blocked_ip_log_cooldown.get(blocked_ip, 0) > 10:
                _blocked_ip_log_cooldown[blocked_ip] = now_ts
                log_admin_security_event(
                    "Blocked Unauthorized IP",
                    blocked_ip,
                    "-",
                    "locked",
                    f"Attempted access to {path} outside Home WiFi (192.168.100.x)"
                )
            if path.startswith("/api/"):
                return JSONResponse(
                    status_code=403,
                    content={"ok": False, "error": "Access Denied: Admin Console is restricted to Home WiFi (192.168.100.x) & Localhost only."}
                )
            return HTMLResponse(
                status_code=403,
                content=(
                    "<!doctype html><html><head><meta charset='utf-8'><title>403 Forbidden</title>"
                    "<style>body{font-family:system-ui,sans-serif;background:#f8fafc;color:#0f172a;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}"
                    ".box{background:#fff;border:1px solid #fecaca;border-radius:16px;padding:32px;max-width:420px;text-align:center;box-shadow:0 10px 30px rgba(0,0,0,0.06)}"
                    "h1{color:#dc2626;font-size:20px;margin:0 0 8px}p{color:#475569;font-size:14px;line-height:1.5;margin:0 0 18px}"
                    "a{display:inline-block;padding:10px 18px;background:#2563eb;color:#fff;text-decoration:none;border-radius:10px;font-weight:700;font-size:13px}</style></head>"
                    "<body><div class='box'><h1>403 Forbidden</h1>"
                    "<p>Admin Console access is restricted strictly to <b>Home WiFi (192.168.100.x) &amp; Localhost</b> only.</p>"
                    "<a href='/'>Back to Storefront</a></div></body></html>"
                )
            )

    # Enforce strict server-side session verification for Admin APIs and Admin Console
    if path.startswith("/api/admin") and path not in ("/api/admin/login", "/api/admin/forgot-password", "/api/admin/verify-reset-code", "/api/admin/reset-password"):
        if not verify_admin_session(request):
            return JSONResponse(
                status_code=401,
                content={"ok": False, "error": "Unauthorized. Admin session required."}
            )
    elif path in ("/admin", "/admin.html"):
        if not verify_admin_session(request):
            return RedirectResponse(url="/admin/login", status_code=302)

    response = await call_next(request)
    if path.endswith((".js", ".css", ".html")) or path in ("/", "/spin", "/admin", "/admin/login", "/signin", "/game/roblox", "/my-account", "/check-order") or response.headers.get("content-type", "").startswith("text/html"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(telegram_polling_loop())
    asyncio.create_task(robux_balance_auto_sync_loop())

# ==========================================
# PUBLIC STORE APIS
# ==========================================

@app.get("/api/settings")
async def get_public_settings():
    return {
        "ok": True,
        "store_name": settings.get("store_name"),
        "telegram_handle": settings.get("telegram_handle"),
        "khqr_merchant_name": settings.get("khqr_merchant_name"),
        "home_banner": settings.get("home_banner", "/media/banner1.webp"),
        "roblox_banner": settings.get("roblox_banner", "/media/roblox-banner.webp"),
        "google_client_id": settings.get("google_client_id", "220196407393-n5m72vbjquni5g4uuo9bfpdrmmn41c24.apps.googleusercontent.com")
    }

@app.get("/api/games")
async def get_games():
    return {"ok": True, "games": games}

@app.get("/api/packages")
async def get_public_packages(game: Optional[str] = None):
    if game:
        return {"ok": True, "packages": [p for p in packages if p.get("game", "roblox") == game and p.get("ok") != 0]}
    return {"ok": True, "packages": [p for p in packages if p.get("ok") != 0]}

@app.get("/api/game/{game_id}")
async def get_game_detail(game_id: str):
    g = games.get(game_id)
    if not g:
        return JSONResponse(status_code=404, content={"ok": False, "error": "Game not found"})
    pkgs = [p for p in packages if p.get("game", "roblox") == game_id and p.get("ok") != 0]
    return {"ok": True, "game": g, "packages": pkgs}

@app.post("/api/check-id")
async def check_player_id(request: Request):
    body = await request.json() if (await request.body()) else {}
    game = body.get("game")
    player_id = body.get("player_id", "")
    server_id = body.get("server_id")
    query = str(player_id or "").strip().lstrip("@")

    if not query:
        return JSONResponse(status_code=400, content={"ok": False, "error": "Please enter a valid username or ID."})

    if game == "roblox":
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                res = await client.post(
                    "https://users.roblox.com/v1/usernames/users",
                    json={"usernames": [query], "excludeBannedUsers": True}
                )
                data = res.json()
                if data and isinstance(data.get("data"), list) and len(data["data"]) > 0:
                    u = data["data"][0]
                    avatar = ""
                    try:
                        av_res = await client.get(
                            f"https://thumbnails.roblox.com/v1/users/avatar-headshot?userIds={u['id']}&size=150x150&format=Png&isCircular=false"
                        )
                        av_data = av_res.json()
                        if av_data and av_data.get("data") and len(av_data["data"]) > 0:
                            avatar = av_data["data"][0].get("imageUrl", "")
                    except Exception:
                        pass
                    return {
                        "ok": True,
                        "username": u["name"],
                        "display_name": u.get("displayName") or u["name"],
                        "roblox_id": str(u["id"]),
                        "avatar": avatar or "https://tr.rbxcdn.com/30DAY-AvatarHeadshot-150x150-Png/150/150/AvatarHeadshot/Png/noFilter"
                    }
        except Exception:
            pass

        fake_id = (abs(sum((ord(c) << (i % 5)) for i, c in enumerate(query))) % 900000000) + 100000000
        return {
            "ok": True,
            "username": query,
            "display_name": query.capitalize(),
            "roblox_id": str(fake_id),
            "avatar": "https://tr.rbxcdn.com/30DAY-AvatarHeadshot-150x150-Png/150/150/AvatarHeadshot/Png/noFilter"
        }

    if game == "mlbb":
        if server_id and not re.match(r"^\d{3,6}$", str(server_id)):
            return JSONResponse(status_code=400, content={"ok": False, "error": "Zone ID must be 4 or 5 digits."})
        return {
            "ok": True,
            "username": query,
            "display_name": f"Mythic Player ({query})",
            "server_id": server_id or "2034",
            "avatar": "/media/mlbb-thumb.svg"
        }

    if game == "tiktok":
        return {
            "ok": True,
            "username": query,
            "display_name": f"@{query}",
            "avatar": "/media/tiktok-thumb.svg"
        }

    return {"ok": True, "username": query, "display_name": query}

@app.get("/api/roblox-avatar/{user_id}")
async def get_roblox_avatar(user_id: str):
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            av_res = await client.get(
                f"https://thumbnails.roblox.com/v1/users/avatar-headshot?userIds={user_id}&size=150x150&format=Png&isCircular=false"
            )
            av_data = av_res.json()
            if av_data and av_data.get("data") and len(av_data["data"]) > 0:
                img_url = av_data["data"][0].get("imageUrl")
                if img_url:
                    return {"avatar": img_url}
    except Exception:
        pass
    return {"avatar": "https://tr.rbxcdn.com/30DAY-AvatarHeadshot-150x150-Png/150/150/AvatarHeadshot/Png/noFilter"}

# ==========================================
# ==========================================
# LUCKY SPIN ROBUX APIS (PUBLIC & ADMIN)
# ==========================================

def _finalize_spin_win_order(username: str, roblox_id: Optional[str], avatar: str, display_name: str, pay_method: str, spin_id: str, slice_obj: Dict[str, Any], user_obj: Optional[Dict[str, Any]], guard_triggered: bool) -> Optional[str]:
    robux_won = int(slice_obj.get("robux", 0))
    now_iso = datetime.now(timezone.utc).isoformat()
    order_id = None

    if robux_won > 0:
        order_id = spin_id
        auto_del = bool(settings.get("auto_deliver", False))
        new_order = {
            "order_id": order_id,
            "token": secrets.token_hex(16),
            "user_id": user_obj["id"] if user_obj else None,
            "buyer_account": user_obj["username"] if user_obj else username,
            "game": "roblox",
            "product_name": "Lucky Spin Robux",
            "product_type": "roblox",
            "package": f"Spin Win: {robux_won} Robux",
            "package_id": "spin_reward",
            "robux_amount": robux_won,
            "original_amount": float(spin_data.get("spin_price_usd", 0.50)),
            "discount": 0.0,
            "promo_code": None,
            "amount": float(spin_data.get("spin_price_usd", 0.50)),
            "payment_method": pay_method,
            "player_id": username,
            "roblox_username": username,
            "display_name": display_name or username,
            "roblox_id": roblox_id,
            "avatar": avatar or "/media/robux-coin.svg",
            "profile_url": f"https://www.roblox.com/users/{roblox_id}/profile" if roblox_id else "",
            "status": "completed" if auto_del else "paid",
            "step": "delivered" if auto_del else "sending",
            "paid": True,
            "delivered": auto_del,
            "created_at": now_iso,
            "label": f"Lucky Spin Winner ({robux_won} R$)"
        }
        orders.insert(0, new_order)
        if len(orders) > 500:
            orders[:] = orders[:500]
        save_orders()
        asyncio.create_task(send_telegram_paid_alert(new_order))

    hist_entry = {
        "spin_id": spin_id,
        "username": username,
        "label": slice_obj.get("label", "Thank You"),
        "robux": robux_won,
        "price_usd": float(spin_data.get("spin_price_usd", 0.50)),
        "payment_method": pay_method,
        "guard_triggered": guard_triggered,
        "order_id": order_id,
        "created_at": now_iso
    }
    spin_data.setdefault("history", []).insert(0, hist_entry)
    if len(spin_data["history"]) > 300:
        spin_data["history"] = spin_data["history"][:300]
    save_spin_data()
    return order_id

@app.get("/api/spin/config")
async def get_public_spin_config():
    public_slices = [
        {
            "id": s.get("id"),
            "label": s.get("label"),
            "robux": int(s.get("robux", 0)),
            "color": s.get("color", "#2563eb"),
            "text_color": s.get("text_color", "#ffffff")
        }
        for s in spin_data.get("slices", [])
    ]
    recent_winners = []
    for h in spin_data.get("history", []):
        if int(h.get("robux", 0)) > 0:
            u = str(h.get("username") or "Player")
            masked = (u[:3] + "***") if len(u) > 3 else (u + "***")
            recent_winners.append({
                "username": masked,
                "robux": int(h.get("robux", 0)),
                "label": h.get("label"),
                "created_at": h.get("created_at")
            })
            if len(recent_winners) >= 12:
                break
    return {
        "ok": True,
        "enabled": bool(spin_data.get("enabled", True)),
        "title": spin_data.get("title", "Lucky Robux Wheel"),
        "subtitle": spin_data.get("subtitle", "Spin to win instant Robux up to 1,000 R$!"),
        "spin_price_usd": float(spin_data.get("spin_price_usd", 0.50)),
        "slices": public_slices,
        "recent_winners": recent_winners
    }

@app.post("/api/spin/create-ticket")
async def create_spin_ticket(request: Request):
    if not spin_data.get("enabled", True):
        return JSONResponse(status_code=400, content={"ok": False, "error": "Lucky Spin Robux is temporarily disabled by Admin."})

    body = await request.json() if (await request.body()) else {}
    username = str(body.get("username") or "").strip().lstrip("@")
    pay_method = str(body.get("payment_method") or "wallet").lower().strip()
    roblox_id = str(body.get("roblox_id") or "").strip() or None
    display_name = str(body.get("display_name") or username).strip()
    avatar = str(body.get("avatar") or "/media/robux-coin.svg").strip()

    if not username or len(username) < 2:
        return JSONResponse(status_code=400, content={"ok": False, "error": "Please enter your Roblox username first."})

    if pay_method not in ("wallet", "khqr"):
        return JSONResponse(status_code=400, content={"ok": False, "error": "Invalid payment method"})

    client_ip = get_admin_effective_ip(request)
    blocked, b_reason = is_blacklisted(player_id=username, username=username, ip=client_ip)
    if blocked:
        return JSONResponse(status_code=403, content={"ok": False, "error": f"Account blocked: {b_reason}"})

    price = round(float(spin_data.get("spin_price_usd", 0.50)), 2)
    if not math.isfinite(price) or price < 0.05:
        return JSONResponse(status_code=400, content={"ok": False, "error": "Invalid spin ticket configuration."})

    spin_id = "SPIN" + secrets.token_hex(4).upper()
    current_user = get_user_from_req(request)

    if pay_method == "wallet":
        if not current_user:
            return JSONResponse(status_code=401, content={"ok": False, "error": "Please sign in to spin using your Rolea Wallet balance."})
        async with _tx_lock:
            if float(current_user.get("balance", 0.0)) < price:
                return JSONResponse(status_code=400, content={"ok": False, "error": f"Insufficient Rolea Wallet balance (${float(current_user.get('balance', 0.0)):.2f}). Please top up first or use KHQR."})

            current_user["balance"] = round(float(current_user.get("balance", 0.0)) - price, 2)
            save_users()
            wallet_transactions.insert(0, {
                "id": "wtx_" + secrets.token_hex(4),
                "user_id": current_user["id"],
                "type": "spend",
                "amount": -price,
                "order_id": spin_id,
                "product": "Lucky Robux Spin Ticket",
                "date": datetime.now(timezone.utc).isoformat()
            })
            save_wallet_tx()

            roll = perform_spin_roll()
            sl = roll["slice"]
            order_id = _finalize_spin_win_order(username, roblox_id, avatar, display_name, "Rolea Wallet", spin_id, sl, current_user, roll["guard_triggered"])
            return {
                "ok": True,
                "paid": True,
                "spin_id": spin_id,
                "slice_index": roll["slice_index"],
                "slice": {
                    "id": sl.get("id"),
                    "label": sl.get("label"),
                    "robux": int(sl.get("robux", 0)),
                    "color": sl.get("color")
                },
                "order_id": order_id,
                "remaining_balance": current_user["balance"]
            }

    # KHQR payment ticket
    khqr_res = await create_khqrpay_order(price, spin_id)
    now = datetime.now(timezone.utc)
    expires_at = (now + timedelta(minutes=5)).isoformat()
    khqrpay_id = None
    qr_url = ""
    payment_url = ""
    aba_deeplink = ""

    if khqr_res and khqr_res.get("id"):
        khqrpay_id = khqr_res["id"]
        qr_url = khqr_res.get("qr_image", "")
        payment_url = khqr_res.get("checkout_url") or f"https://khqrpay.site/pay/{khqrpay_id}"
        aba_deeplink = khqr_res.get("aba_deeplink", "")
        if khqr_res.get("expires_at"):
            expires_at = khqr_res["expires_at"]
    if not qr_url:
        amt_str = f"{price:.2f}"
        amt_len = f"{len(amt_str):02d}"
        khqr_payload = f"00020101021229370016bakong@rolea010108{spin_id}520459995303840540{amt_len}{amt_str}5802KH5911ROLEA TOPUP6010PHNOM PENH62240108{spin_id}0708ROLEATOPUP6304"
        qr_url = generate_khqr_data_url(khqr_payload)
        payment_url = f"https://khqrpay.site/pay/{spin_id}"

    pending_spin_tickets[spin_id] = {
        "spin_id": spin_id,
        "khqrpay_id": khqrpay_id,
        "username": username,
        "roblox_id": roblox_id,
        "display_name": display_name,
        "avatar": avatar,
        "user_id": current_user["id"] if current_user else None,
        "amount": price,
        "qr_url": qr_url,
        "payment_url": payment_url,
        "aba_deeplink": aba_deeplink,
        "expires_at": expires_at,
        "paid": False,
        "spun": False,
        "result": None
    }
    return {
        "ok": True,
        "paid": False,
        "spin_id": spin_id,
        "amount": price,
        "qr_url": qr_url,
        "payment_url": payment_url,
        "aba_deeplink": aba_deeplink,
        "expires_at": expires_at
    }

@app.get("/api/spin/ticket/{spin_id}")
async def check_spin_ticket(spin_id: str):
    tkt = pending_spin_tickets.get(spin_id)
    if not tkt:
        return JSONResponse(status_code=404, content={"ok": False, "error": "Spin ticket not found"})

    if not tkt["paid"] and tkt.get("khqrpay_id"):
        live = await check_khqrpay_status(tkt["khqrpay_id"])
        if live:
            verified_paid, v_st = verify_khqr_bank_payment(live, float(tkt.get("amount", 0.50)))
            if verified_paid:
                async with _tx_lock:
                    kid = str(tkt["khqrpay_id"])
                    if not tkt["paid"] and kid not in _credited_khqr_ids:
                        _credited_khqr_ids.add(kid)
                        tkt["paid"] = True
            elif v_st in ["expired", "failed"]:
                return {"ok": True, "paid": False, "status": v_st}

    if tkt["paid"] and not tkt["spun"]:
        async with _tx_lock:
            if tkt["paid"] and not tkt["spun"]:
                tkt["spun"] = True
                roll = perform_spin_roll()
                sl = roll["slice"]
                u_obj = next((u for u in users if u.get("id") == tkt.get("user_id")), None) if tkt.get("user_id") else None
                order_id = _finalize_spin_win_order(
                    tkt["username"], tkt.get("roblox_id"), tkt.get("avatar", "/media/robux-coin.svg"),
                    tkt.get("display_name", tkt["username"]), "ABA KHQR", spin_id, sl, u_obj, roll["guard_triggered"]
                )
                tkt["result"] = {
                    "slice_index": roll["slice_index"],
                    "slice": {
                        "id": sl.get("id"),
                        "label": sl.get("label"),
                        "robux": int(sl.get("robux", 0)),
                        "color": sl.get("color")
                    },
                    "order_id": order_id
                }

    return {
        "ok": True,
        "paid": tkt["paid"],
        "spun": tkt["spun"],
        "result": tkt["result"]
    }

@app.get("/api/admin/spin")
async def admin_get_spin():
    cost_per_r = float(spin_data.get("cost_per_1k_robux_usd", 4.0)) / 1000.0
    total_rev = float(spin_data.get("total_revenue_usd", 0.0))
    total_robux = int(spin_data.get("total_robux_awarded", 0))
    est_cost = round(total_robux * cost_per_r, 4)
    est_profit = round(total_rev - est_cost, 2)

    slices = spin_data.get("slices", [])
    total_w = sum(max(0.0, float(s.get("weight", 0))) for s in slices) or 1.0
    expected_robux_per_spin = sum((max(0.0, float(s.get("weight", 0))) / total_w) * int(s.get("robux", 0)) for s in slices)
    expected_cost_per_spin = round(expected_robux_per_spin * cost_per_r, 4)
    spin_price = float(spin_data.get("spin_price_usd", 0.50))
    expected_margin_pct = round(((spin_price - expected_cost_per_spin) / spin_price) * 100, 1) if spin_price > 0 else 0.0

    return {
        "ok": True,
        "spin": spin_data,
        "metrics": {
            "total_spins": int(spin_data.get("total_spins", 0)),
            "total_revenue_usd": round(total_rev, 2),
            "total_robux_awarded": total_robux,
            "est_net_profit_usd": est_profit,
            "expected_cost_per_spin": expected_cost_per_spin,
            "expected_margin_pct": expected_margin_pct,
            "spins_since_last_big_win": int(spin_data.get("spins_since_last_big_win", 0))
        }
    }

@app.post("/api/admin/spin/save")
async def admin_save_spin(request: Request):
    body = await request.json() if (await request.body()) else {}
    if "enabled" in body:
        spin_data["enabled"] = bool(body["enabled"])
    if "title" in body and body["title"]:
        spin_data["title"] = str(body["title"]).strip()
    if "subtitle" in body and body["subtitle"] is not None:
        spin_data["subtitle"] = str(body["subtitle"]).strip()
    if "spin_price_usd" in body:
        spin_data["spin_price_usd"] = max(0.05, round(float(body["spin_price_usd"]), 2))
    if "cost_per_1k_robux_usd" in body:
        spin_data["cost_per_1k_robux_usd"] = max(0.5, round(float(body["cost_per_1k_robux_usd"]), 2))
    if "big_prize_threshold_robux" in body:
        spin_data["big_prize_threshold_robux"] = max(0, int(body["big_prize_threshold_robux"]))
    if "max_big_wins_per_day" in body:
        spin_data["max_big_wins_per_day"] = max(0, int(body["max_big_wins_per_day"]))
    if "min_spins_between_big_wins" in body:
        spin_data["min_spins_between_big_wins"] = max(0, int(body["min_spins_between_big_wins"]))
    if "require_profit_reserve" in body:
        spin_data["require_profit_reserve"] = bool(body["require_profit_reserve"])

    if "slices" in body and isinstance(body["slices"], list) and len(body["slices"]) >= 2:
        cleaned = []
        for idx, s in enumerate(body["slices"]):
            lbl = str(s.get("label") or f"Slice {idx+1}").strip()
            robux = max(0, int(s.get("robux", 0)))
            weight = max(0.0, float(s.get("weight", 0)))
            color = str(s.get("color") or "#2563eb").strip()
            text_color = str(s.get("text_color") or ("#0f172a" if color.lower() in ("#f59e0b", "#facc15", "#fef08a", "#ffffff") else "#ffffff")).strip()
            cleaned.append({
                "id": str(s.get("id") or f"sl_{idx+1}"),
                "label": lbl,
                "robux": robux,
                "weight": weight,
                "color": color,
                "text_color": text_color
            })
        if sum(x["weight"] for x in cleaned) <= 0:
            return JSONResponse(status_code=400, content={"ok": False, "error": "Total win weight must be greater than 0."})
        spin_data["slices"] = cleaned

    save_spin_data()
    return {"ok": True, "spin": spin_data, "message": "Lucky Spin configuration saved!"}

@app.post("/api/admin/spin/test-roll")
async def admin_test_spin_roll():
    """Runs a 1,000-spin Monte Carlo simulation without affecting real stats."""
    sim_state = json.loads(json.dumps(spin_data))
    sim_state["history"] = []
    sim_state["total_spins"] = 0
    sim_state["total_revenue_usd"] = 0.0
    sim_state["total_robux_awarded"] = 0
    sim_state["spins_since_last_big_win"] = int(spin_data.get("spins_since_last_big_win", 0))

    counts: Dict[str, int] = {}
    guard_blocks = 0
    for _ in range(1000):
        res = perform_spin_roll(sim_state=sim_state)
        lbl = res["slice"]["label"]
        counts[lbl] = counts.get(lbl, 0) + 1
        if res["guard_triggered"]:
            guard_blocks += 1

    cost_per_r = float(sim_state.get("cost_per_1k_robux_usd", 4.0)) / 1000.0
    sim_rev = round(float(sim_state["total_revenue_usd"]), 2)
    sim_cost = round(int(sim_state["total_robux_awarded"]) * cost_per_r, 2)
    sim_profit = round(sim_rev - sim_cost, 2)
    return {
        "ok": True,
        "simulated_spins": 1000,
        "revenue_usd": sim_rev,
        "robux_awarded": sim_state["total_robux_awarded"],
        "estimated_cost_usd": sim_cost,
        "estimated_profit_usd": sim_profit,
        "guard_blocks": guard_blocks,
        "breakdown": counts
    }

@app.post("/api/admin/spin/reset-stats")
async def admin_reset_spin_stats():
    spin_data["total_spins"] = 0
    spin_data["total_revenue_usd"] = 0.0
    spin_data["total_robux_awarded"] = 0
    spin_data["spins_since_last_big_win"] = 0
    spin_data["history"] = []
    save_spin_data()
    return {"ok": True, "message": "Spin statistics and history cleared."}

# CUSTOMER AUTHENTICATION & PROFILE
# ==========================================

@app.post("/api/auth/register")
async def register(request: Request):
    body = await request.json() if (await request.body()) else {}
    username = body.get("username", "")
    email = body.get("email", "")
    password = body.get("password", "")

    if not username or len(username.strip()) < 3:
        return JSONResponse(status_code=400, content={"ok": False, "error": "Username must be at least 3 characters"})
    if not password or len(password) < 6:
        return JSONResponse(status_code=400, content={"ok": False, "error": "Password must be at least 6 characters"})

    clean_username = username.strip()
    clean_email = email.strip().lower()

    for u in users:
        if u.get("username", "").lower() == clean_username.lower():
            return JSONResponse(status_code=400, content={"ok": False, "error": "Username already registered"})
        if clean_email and u.get("email", "").lower() == clean_email:
            return JSONResponse(status_code=400, content={"ok": False, "error": "Email already registered"})

    new_user = {
        "id": "usr_" + secrets.token_hex(4) + hex(int(time.time()))[2:],
        "username": clean_username,
        "email": clean_email,
        "password_hash": hash_password(password),
        "balance": 0.00,
        "avatar": "/media/rolea-logo.webp",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    users.append(new_user)
    save_users()

    token = secrets.token_hex(32)
    sessions[token] = {
        "userId": new_user["id"],
        "expiresAt": int((time.time() + 30 * 24 * 3600) * 1000)
    }

    return {
        "ok": True,
        "token": token,
        "user": {
            "id": new_user["id"],
            "username": new_user["username"],
            "email": new_user["email"],
            "balance": new_user["balance"],
            "avatar": new_user["avatar"]
        }
    }

@app.post("/api/auth/login")
async def login(request: Request):
    body = await request.json() if (await request.body()) else {}
    username = body.get("username", "").strip()
    password = body.get("password", "")

    if not username or not password:
        return JSONResponse(status_code=400, content={"ok": False, "error": "Please enter username and password"})

    lookup = username.lower()
    user = next((u for u in users if u.get("username", "").lower() == lookup or (u.get("email") and u.get("email", "").lower() == lookup)), None)
    if not user:
        return JSONResponse(status_code=400, content={"ok": False, "error": "Invalid username or password"})

    if user.get("password_hash") != hash_password(password):
        return JSONResponse(status_code=400, content={"ok": False, "error": "Invalid username or password"})

    token = secrets.token_hex(32)
    sessions[token] = {
        "userId": user["id"],
        "expiresAt": int((time.time() + 30 * 24 * 3600) * 1000)
    }

    return {
        "ok": True,
        "token": token,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "email": user["email"],
            "balance": user["balance"],
            "avatar": user["avatar"]
        }
    }

# Password Reset OTP Store (in-memory, salted SHA-256)
customer_reset_otps: Dict[str, Dict[str, Any]] = {}
customer_reset_rate: Dict[str, List[float]] = {}

@app.post("/api/auth/forgot-password")
async def customer_forgot_password(request: Request):
    client_ip = request.client.host if request.client else "unknown"
    now_ts = time.time()
    recent = [t for t in customer_reset_rate.get(client_ip, []) if now_ts - t < 900]
    if len(recent) >= 8:
        return JSONResponse(status_code=429, content={"ok": False, "error": "Too many reset requests. Please try again in 15 minutes."})
    recent.append(now_ts)
    customer_reset_rate[client_ip] = recent

    body = await request.json() if (await request.body()) else {}
    identifier = str(body.get("identifier") or "").strip().lower()
    if not identifier:
        return JSONResponse(status_code=400, content={"ok": False, "error": "Please enter your email or username."})

    user = next((u for u in users if u.get("username", "").lower() == identifier or (u.get("email") and u.get("email", "").lower() == identifier)), None)
    if not user:
        return JSONResponse(status_code=404, content={"ok": False, "error": "No customer account found with this email or username. Please register first (or use /admin/login for Admin)."})

    smtp_ready = bool(settings.get("smtp_email") and settings.get("smtp_password"))
    user_email = str(user.get("email") or "").strip()
    tg_token = settings.get("telegram_bot_token")
    user_chat = user.get("telegram_chat_id")

    otp_code = f"{secrets.randbelow(900000) + 100000}"
    otp_salt = secrets.token_hex(8)
    customer_reset_otps[user["id"]] = {
        "salt": otp_salt,
        "hash": hashlib.sha256((otp_code + otp_salt).encode("utf-8")).hexdigest(),
        "expires_at": now_ts + 600,
        "attempts": 0,
        "verified": False,
        "reset_token": ""
    }

    sent_email = False
    mail_err = ""
    if user_email and smtp_ready:
        store_name = settings.get("store_name", "Rolea Topup")
        subj = f"{store_name} Password Reset Code: {otp_code}"
        html_body = build_password_reset_email_html(store_name, user.get("username", user_email), otp_code, client_ip)
        txt_body = f"{store_name} Password Reset Code: {otp_code}\nHello {user.get('username')}, a password reset code was requested from IP {client_ip}. Valid for 10 minutes."
        ok_mail, mail_err = await send_smtp_email(user_email, subj, html_body, txt_body)
        if ok_mail:
            sent_email = True
        else:
            print("[SMTP Customer Reset Error]:", mail_err)

    sent_tg = False
    if tg_token and user_chat:
        msg = (
            f"<b>Password Reset Code · {settings.get('store_name', 'Rolea Topup')}</b>\n\n"
            f"Your 6-digit password reset code is: <code>{otp_code}</code>\n"
            f"Account: <code>{user.get('username')}</code>\n"
            f"Valid for 10 minutes. Never share this code with anyone."
        )
        asyncio.create_task(send_telegram_direct_message(tg_token, user_chat, msg))
        sent_tg = True

    if sent_email:
        return {"ok": True, "channel": "email", "message": f"A 6-digit Password Reset Code has been sent to {user_email}!"}
    if sent_tg:
        return {"ok": True, "channel": "telegram", "message": "A 6-digit Password Reset Code has been sent to your linked Telegram!"}

    customer_reset_otps.pop(user["id"], None)
    if mail_err:
        return JSONResponse(status_code=500, content={"ok": False, "error": f"Failed to send email: {mail_err}"})
    return JSONResponse(status_code=400, content={"ok": False, "error": "This account has no email or Telegram linked to receive a reset code."})

@app.post("/api/auth/verify-reset-code")
async def customer_verify_reset_code(request: Request):
    body = await request.json() if (await request.body()) else {}
    identifier = str(body.get("identifier") or "").strip().lower()
    code = str(body.get("code") or "").strip()

    if not identifier or not code:
        return JSONResponse(status_code=400, content={"ok": False, "error": "Please enter the 6-digit verification code."})

    user = next((u for u in users if u.get("username", "").lower() == identifier or (u.get("email") and u.get("email", "").lower() == identifier)), None)
    if not user or user["id"] not in customer_reset_otps:
        return JSONResponse(status_code=400, content={"ok": False, "error": "No active reset code found. Please request a new code."})

    rec = customer_reset_otps[user["id"]]
    if time.time() > rec["expires_at"]:
        customer_reset_otps.pop(user["id"], None)
        return JSONResponse(status_code=400, content={"ok": False, "error": "Verification code expired. Please request a new one."})

    rec["attempts"] += 1
    if rec["attempts"] > 5:
        customer_reset_otps.pop(user["id"], None)
        return JSONResponse(status_code=429, content={"ok": False, "error": "Too many wrong attempts. Please request a new code."})

    cand_hash = hashlib.sha256((code + rec["salt"]).encode("utf-8")).hexdigest()
    if not hmac.compare_digest(cand_hash, rec["hash"]):
        return JSONResponse(status_code=400, content={"ok": False, "error": "Incorrect 6-digit verification code."})

    reset_token = secrets.token_urlsafe(24)
    rec["verified"] = True
    rec["reset_token"] = reset_token
    return {"ok": True, "reset_token": reset_token, "message": "Code verified! Now enter your new password."}

@app.post("/api/auth/reset-password")
async def customer_reset_password(request: Request):
    body = await request.json() if (await request.body()) else {}
    identifier = str(body.get("identifier") or "").strip().lower()
    reset_token = str(body.get("reset_token") or "").strip()
    new_pw = str(body.get("new_password") or "")
    confirm_pw = str(body.get("confirm_password") or "")

    if not identifier or not reset_token:
        return JSONResponse(status_code=400, content={"ok": False, "error": "Please verify your 6-digit OTP code first."})
    if len(new_pw) < 6:
        return JSONResponse(status_code=400, content={"ok": False, "error": "New password must be at least 6 characters."})
    if new_pw != confirm_pw:
        return JSONResponse(status_code=400, content={"ok": False, "error": "Passwords do not match."})

    user = next((u for u in users if u.get("username", "").lower() == identifier or (u.get("email") and u.get("email", "").lower() == identifier)), None)
    if not user or user["id"] not in customer_reset_otps:
        return JSONResponse(status_code=400, content={"ok": False, "error": "Reset session expired. Please start again."})

    rec = customer_reset_otps[user["id"]]
    if time.time() > rec["expires_at"]:
        customer_reset_otps.pop(user["id"], None)
        return JSONResponse(status_code=400, content={"ok": False, "error": "Reset session expired. Please request a new code."})

    if not rec.get("verified") or not hmac.compare_digest(rec.get("reset_token", ""), reset_token):
        return JSONResponse(status_code=403, content={"ok": False, "error": "OTP verification required before changing password."})

    user["password_hash"] = hash_password(new_pw)
    save_users()
    customer_reset_otps.pop(user["id"], None)

    # Invalidate existing sessions for this user
    stale_tokens = [tok for tok, s in sessions.items() if s.get("userId") == user["id"]]
    for tok in stale_tokens:
        sessions.pop(tok, None)

    return {"ok": True, "message": "Password reset successfully! You can now sign in with your new password."}

@app.post("/api/auth/google")
async def auth_google(request: Request):
    body = await request.json() if (await request.body()) else {}
    credential = str(body.get("credential") or "").strip()
    access_token = str(body.get("access_token") or "").strip()
    expected_cid = str(settings.get("google_client_id") or "220196407393-n5m72vbjquni5g4uuo9bfpdrmmn41c24.apps.googleusercontent.com").strip()

    email = ""
    name = ""
    avatar = ""
    google_id = ""

    # Strictly verify token server-side with Google OAuth servers (never trust raw client email!)
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            if credential:
                r = await client.get("https://oauth2.googleapis.com/tokeninfo", params={"id_token": credential})
                if r.status_code == 200:
                    claims = r.json()
                    aud = str(claims.get("aud") or "").strip()
                    verified = str(claims.get("email_verified") or "").lower() in ("true", "1")
                    if verified and (not expected_cid or aud == expected_cid):
                        email = str(claims.get("email") or "").strip().lower()
                        name = _sanitize_plain(claims.get("name") or claims.get("given_name") or "", 60)
                        avatar = str(claims.get("picture") or "").strip()
                        google_id = str(claims.get("sub") or "").strip()
            elif access_token:
                ti = await client.get("https://oauth2.googleapis.com/tokeninfo", params={"access_token": access_token})
                ui = await client.get("https://www.googleapis.com/oauth2/v3/userinfo", headers={"Authorization": f"Bearer {access_token}"})
                if ti.status_code == 200 and ui.status_code == 200:
                    ti_data = ti.json()
                    ui_data = ui.json()
                    aud = str(ti_data.get("aud") or ti_data.get("azp") or "").strip()
                    verified = bool(ui_data.get("email_verified", True))
                    if verified and (not expected_cid or aud == expected_cid):
                        email = str(ui_data.get("email") or "").strip().lower()
                        name = _sanitize_plain(ui_data.get("name") or ui_data.get("given_name") or "", 60)
                        avatar = str(ui_data.get("picture") or "").strip()
                        google_id = str(ui_data.get("sub") or "").strip()
    except Exception:
        return JSONResponse(status_code=502, content={"ok": False, "error": "Unable to verify Google Sign-In token"})

    if not email or not google_id:
        return JSONResponse(status_code=401, content={"ok": False, "error": "Invalid or unverified Google authentication token"})

    user = next((u for u in users if (u.get("email") and u.get("email", "").lower() == email) or (u.get("google_id") and u.get("google_id") == google_id)), None)

    if not user:
        base_uname = (name.replace(" ", "").lower() if name else email.split("@")[0])[:12]
        base_uname = re.sub(r'[^a-zA-Z0-9_]', '', base_uname) or "user"
        username = base_uname
        counter = 1
        while any(u.get("username", "").lower() == username.lower() for u in users):
            username = f"{base_uname}{counter}"
            counter += 1

        user = {
            "id": "usr_" + secrets.token_hex(4) + hex(int(time.time()))[2:],
            "username": username,
            "email": email,
            "google_id": google_id,
            "auth_provider": "google",
            "avatar": avatar or "/media/rolea-logo.webp",
            "password_hash": "",
            "balance": 0.0,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        users.append(user)
        save_users()
    else:
        if google_id and not user.get("google_id"):
            user["google_id"] = google_id
        if avatar and (not user.get("avatar") or user.get("avatar") == "/media/rolea-logo.webp"):
            user["avatar"] = avatar
        if not user.get("email"):
            user["email"] = email
        save_users()

    token = secrets.token_hex(32)
    sessions[token] = {
        "userId": user["id"],
        "expiresAt": int((time.time() + 30 * 24 * 3600) * 1000)
    }

    return {
        "ok": True,
        "token": token,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "email": user.get("email"),
            "avatar": user.get("avatar"),
            "balance": user.get("balance", 0.0)
        }
    }

@app.get("/api/auth/me")
async def get_current_user(request: Request):
    user = get_user_from_req(request)
    if not user:
        return {"ok": False, "user": None}
    return {
        "ok": True,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "email": user["email"],
            "balance": user["balance"],
            "avatar": user["avatar"]
        }
    }

@app.post("/api/auth/logout")
async def logout(request: Request):
    auth_header = request.headers.get("authorization")
    token = None
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    elif request.headers.get("x-auth-token"):
        token = request.headers.get("x-auth-token", "").strip()
    if token and token in sessions:
        del sessions[token]
    return {"ok": True}

@app.post("/api/auth/profile/update")
async def update_customer_profile(request: Request):
    user = get_user_from_req(request)
    if not user:
        return JSONResponse(status_code=401, content={"ok": False, "error": "Not authenticated"})
    body = await request.json() if (await request.body()) else {}
    email = body.get("email")
    telegram = body.get("telegram")
    current_password = body.get("current_password")
    new_password = body.get("new_password")

    if email:
        user["email"] = email.strip()
    if telegram is not None:
        user["telegram"] = telegram.strip().lstrip("@")

    if new_password:
        if len(new_password) < 4:
            return JSONResponse(status_code=400, content={"ok": False, "error": "New password must be at least 4 characters long"})
        if current_password:
            curr_hash = hash_password(current_password)
            if curr_hash != user.get("password_hash") and current_password != user.get("password_plain"):
                return JSONResponse(status_code=400, content={"ok": False, "error": "Current password is incorrect"})
        user["password_hash"] = hash_password(new_password)
        user["password_plain"] = new_password

    save_users()
    return {
        "ok": True,
        "message": "Profile updated successfully",
        "user": {
            "id": user["id"],
            "username": user["username"],
            "email": user.get("email"),
            "telegram": user.get("telegram", ""),
            "balance": user.get("balance", 0.0),
            "created_at": user.get("created_at")
        }
    }

@app.get("/api/auth/my-orders")
async def get_my_orders(request: Request):
    user = get_user_from_req(request)
    if not user:
        return JSONResponse(status_code=401, content={"ok": False, "error": "Not authenticated"})
    # Only return actual purchased products (Robux, SMM); wallet top-ups belong in Wallet Transactions
    my_orders = [
        o for o in orders 
        if (o.get("user_id") == user["id"] or o.get("roblox_username") == user["username"])
        and o.get("type") != "wallet_topup"
        and o.get("product_type") != "wallet"
        and not str(o.get("order_id", "")).startswith("WLT")
    ]
    return {"ok": True, "orders": my_orders}

# ==========================================
# WALLET & BALANCE
# ==========================================

@app.post("/api/wallet/topup")
async def wallet_topup(request: Request):
    user = get_user_from_req(request)
    if not user:
        return JSONResponse(status_code=401, content={"ok": False, "error": "Please log in to top up your wallet"})

    body = await request.json() if (await request.body()) else {}
    try:
        amount = float(body.get("amount", 0))
    except (ValueError, TypeError):
        amount = 0.0

    if not math.isfinite(amount) or amount < 0.50 or amount > 2000.00:
        return JSONResponse(status_code=400, content={"ok": False, "error": "Deposit amount must be between $0.50 and $2,000.00 USD"})
    amount = round(amount, 2)

    now = datetime.now(timezone.utc)
    order_id = "WLT" + hex(int(time.time()))[2:].upper() + secrets.token_hex(2).upper()
    token = secrets.token_hex(16)

    khqr_res = await create_khqrpay_order(amount, order_id)
    qr_url = ""
    khqrpay_id = None
    payment_url = ""
    aba_deeplink = ""
    expires_at = (now + timedelta(minutes=10)).isoformat()

    if khqr_res and khqr_res.get("id"):
        khqrpay_id = khqr_res["id"]
        qr_url = khqr_res.get("qr_image", "")
        payment_url = khqr_res.get("checkout_url") or f"https://khqrpay.site/pay/{khqrpay_id}"
        aba_deeplink = khqr_res.get("aba_deeplink", "")
        if khqr_res.get("expires_at"):
            expires_at = khqr_res["expires_at"]

    if not qr_url:
        amt_str = f"{amount:.2f}"
        amt_len = f"{len(amt_str):02d}"
        khqr_payload = f"00020101021229370016bakong@rolea010108{order_id}520459995303840540{amt_len}{amt_str}5802KH5911ROLEA TOPUP6010PHNOM PENH62240108{order_id}0708ROLEATOPUP6304"
        qr_url = generate_khqr_data_url(khqr_payload)
        payment_url = f"https://khqrpay.site/pay/{order_id}"

    topup_order = {
        "order_id": order_id,
        "khqrpay_id": khqrpay_id,
        "token": token,
        "user_id": user["id"],
        "buyer_account": user["username"],
        "roblox_username": user["username"],
        "type": "wallet_topup",
        "product_name": "Rolea Wallet Top-up",
        "product_type": "wallet",
        "package": f"${amount:.2f} USD Wallet Balance",
        "amount": amount,
        "status": "pending",
        "step": "wait",
        "paid": False,
        "delivered": False,
        "created_at": now.isoformat(),
        "expires_at": expires_at,
        "payment_url": payment_url,
        "aba_deeplink": aba_deeplink,
        "qr_url": qr_url,
        "label": "Scan KHQR to deposit into your wallet"
    }

    orders.insert(0, topup_order)
    save_orders()

    return {
        "ok": True,
        "order_id": order_id,
        "amount": amount,
        "qr_url": qr_url,
        "payment_url": payment_url,
        "aba_deeplink": aba_deeplink,
        "expires_at": expires_at
    }

@app.get("/api/wallet/transactions")
async def get_wallet_transactions(request: Request):
    user = get_user_from_req(request)
    if not user:
        return JSONResponse(status_code=401, content={"ok": False, "error": "Not authenticated"})
    txs = [t for t in wallet_transactions if t.get("user_id") == user["id"]]
    return {"ok": True, "balance": user.get("balance", 0.0), "transactions": txs}

# ==========================================
# PROMOS & COUPONS
# ==========================================

@app.post("/api/promo/apply")
async def apply_promo(request: Request):
    body = await request.json() if (await request.body()) else {}
    code = body.get("code")
    if not code or not isinstance(code, str):
        return JSONResponse(status_code=400, content={"ok": False, "error": "Please enter a promo code"})

    try:
        order_amount = float(body.get("amount", 0))
    except (ValueError, TypeError):
        order_amount = 0.0

    cp = next((c for c in coupons if c.get("code", "").upper() == code.strip().upper() and c.get("enabled")), None)
    if not cp:
        return JSONResponse(status_code=404, content={"ok": False, "error": "Invalid or inactive promo code"})

    if cp.get("max_uses") and cp.get("used_count", 0) >= cp["max_uses"]:
        return JSONResponse(status_code=400, content={"ok": False, "error": "Promo code usage limit has been reached"})

    if order_amount < float(cp.get("min_spend", 0)):
        return JSONResponse(status_code=400, content={"ok": False, "error": f"Minimum order of ${float(cp.get('min_spend', 0)):.2f} required for this coupon"})

    if cp.get("type") == "percentage":
        discount = order_amount * (float(cp.get("value", 0)) / 100)
    else:
        discount = float(cp.get("value", 0))

    discount = min(discount, max(0.0, order_amount - 0.05))
    discount = round(discount, 2)
    new_amount = round(order_amount - discount, 2)

    return {
        "ok": True,
        "code": cp["code"],
        "type": cp.get("type"),
        "value": cp.get("value"),
        "discount": discount,
        "new_amount": new_amount,
        "description": cp.get("description") or f"{cp.get('value')}{'%' if cp.get('type') == 'percentage' else '$'} discount"
    }

# ==========================================
# REVIEWS & LIVE PROOF
# ==========================================

@app.get("/api/reviews")
async def get_reviews():
    approved = [r for r in reviews if r.get("approved") is not False]
    total = len(approved)
    avg = sum(float(r.get("rating", 5)) for r in approved) / total if total > 0 else 5.0
    return {
        "ok": True,
        "reviews": approved,
        "stats": {
            "total": total,
            "average_rating": round(avg, 1)
        }
    }

@app.post("/api/reviews/submit")
async def submit_review(request: Request):
    body = await request.json() if (await request.body()) else {}
    comment = body.get("comment", "")
    if not comment or len(comment.strip()) < 2:
        return JSONResponse(status_code=400, content={"ok": False, "error": "Please enter a review comment"})

    try:
        rating = max(1, min(5, int(body.get("rating", 5))))
    except Exception:
        rating = 5

    username = body.get("username", "Verified Customer").strip()
    masked = username[:3] + "***" if len(username) > 3 else username
    game_key = body.get("game", "general")
    g = games.get(game_key, {})

    new_rev = {
        "id": "rev_" + secrets.token_hex(4),
        "order_id": _sanitize_plain(body.get("order_id") or "", 48),
        "game": game_key,
        "game_name": _sanitize_plain(g.get("name") or "Store Top-up", 80),
        "username": _sanitize_plain(masked, 40),
        "rating": max(1, min(5, int(rating))),
        "comment": _sanitize_plain(comment, 400),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "approved": True
    }
    reviews.insert(0, new_rev)
    if len(reviews) > 500:
        reviews[:] = reviews[:500]
    save_reviews()

    return {"ok": True, "message": "Thank you! Your review has been published.", "review": new_rev}

@app.get("/api/live-proof")
async def get_live_proof():
    live_list = []
    for o in orders:
        if o.get("paid") and o.get("type") != "wallet_topup":
            raw_name = o.get("roblox_username") or o.get("username") or o.get("display_name") or "Customer"
            masked = raw_name[:3] + "***" if len(raw_name) > 3 else raw_name + "***"
            g_name = o.get("product_name") or games.get(o.get("game", ""), {}).get("name") or "Game Topup"
            live_list.append({
                "order_id": o.get("order_id"),
                "username": masked,
                "game": g_name,
                "package": o.get("package"),
                "amount": o.get("amount"),
                "time": o.get("created_at")
            })
            if len(live_list) >= 15:
                break

    # Only return real paid orders (no fake seed entries)

    return {"ok": True, "live_proof": live_list}

# ==========================================
# CREATE & CHECK ORDERS
# ==========================================

@app.post("/api/create-order")
async def create_order(request: Request):
    try:
        body = await request.json() if (await request.body()) else {}
        if not isinstance(body, dict):
            return JSONResponse(status_code=400, content={"ok": False, "error": "Invalid JSON payload"})
        client_ip = get_admin_effective_ip(request)
        blocked, b_reason = is_blacklisted(player_id=body.get("player_id", ""), username=body.get("username", ""), email=body.get("email", ""), ip=client_ip)
        if blocked:
            return JSONResponse(status_code=403, content={"ok": False, "error": f"គណនី ឬ IP របស់អ្នកត្រូវបានបិទ (Blacklisted) ដោយសារការសង្ស័យបន្លំ: {b_reason}"})

        game_key = _sanitize_plain(body.get("game") or "roblox", 40)
        game_data = games.get(game_key)
        if not game_data or game_data.get("enabled") is False:
            return JSONResponse(status_code=400, content={"ok": False, "error": "Selected product is unavailable."})

        pkg_id = body.get("package_id")
        if pkg_id:
            pkg = next((p for p in packages if p.get("id") == pkg_id and p.get("game", "roblox") == game_key), None)
        else:
            game_packages = [p for p in packages if p.get("game", "roblox") == game_key and p.get("ok", 1)]
            pkg = game_packages[0] if game_packages else None
        if not pkg or not pkg.get("ok", 1):
            return JSONResponse(status_code=400, content={"ok": False, "error": "Invalid or unavailable package."})
        if pkg.get("in_stock") is False:
            return JSONResponse(status_code=400, content={"ok": False, "error": f"កញ្ចប់ '{pkg.get('name')}' គឺអស់ពីស្តុកបណ្តោះអាសន្ន (Out of Stock)។ សូមជ្រើសរើសកញ្ចប់ផ្សេង។"})

        now = datetime.now(timezone.utc)
        raw_ref = str(body.get("checkout_ref") or "").strip()
        if re.fullmatch(r"[A-Za-z0-9_-]{8,40}", raw_ref) and not any(o.get("order_id") == raw_ref for o in orders):
            order_id = raw_ref
        else:
            order_id = "PR" + hex(int(time.time()))[2:].upper() + secrets.token_hex(3).upper()
        # Always generate random receipt token server-side
        token = secrets.token_hex(16)

        amount = round(float(pkg.get("price", 0)), 2)
        if not math.isfinite(amount) or amount < 0.01:
            return JSONResponse(status_code=400, content={"ok": False, "error": "Invalid package pricing."})
        original_amount = amount
        discount = 0.0
        applied_promo = None
        current_user = get_user_from_req(request)

        async with _tx_lock:
            promo_code = body.get("promo_code")
            if promo_code and isinstance(promo_code, str):
                code_upper = promo_code.strip().upper()
                cp = next((c for c in coupons if c.get("code", "").upper() == code_upper and c.get("enabled")), None)
                if cp and (not cp.get("max_uses") or cp.get("used_count", 0) < cp["max_uses"]) and amount >= float(cp.get("min_spend", 0)):
                    val = float(cp.get("value", 0))
                    if math.isfinite(val) and val > 0:
                        if cp.get("type") == "percentage":
                            discount = amount * (min(100.0, val) / 100.0)
                        else:
                            discount = val
                        discount = min(discount, max(0.0, amount - 0.05))
                        discount = round(discount, 2)
                        amount = round(max(0.05, amount - discount), 2)
                        applied_promo = cp["code"]
                        cp["used_count"] = cp.get("used_count", 0) + 1
                        save_coupons()

            # 1-Click Wallet Checkout (atomic inside _tx_lock)
            if body.get("payment_method") == "wallet":
                if not current_user:
                    return JSONResponse(status_code=401, content={"ok": False, "error": "Please log in to pay with your Rolea Wallet balance"})
                if float(current_user.get("balance", 0.0)) < amount:
                    return JSONResponse(status_code=400, content={"ok": False, "error": f"Insufficient wallet balance (${float(current_user.get('balance', 0)):.2f} USD). Please top up first."})

                current_user["balance"] = round(float(current_user.get("balance", 0.0)) - amount, 2)
                save_users()

                wallet_transactions.insert(0, {
                    "id": "wtx_" + secrets.token_hex(4),
                    "user_id": current_user["id"],
                    "type": "spend",
                    "amount": -amount,
                    "order_id": order_id,
                    "product": f"{game_data.get('name')} - {pkg.get('name')}",
                    "date": now.isoformat()
                })
                save_wallet_tx()

                auto_del = bool(settings.get("auto_deliver", False))
                is_smm = (game_data.get("type") == "smm") or (game_key == "tiktok")
                t_input = _sanitize_plain(body.get("player_id") or "", 180)
                tt_link = t_input if (t_input.startswith("http://") or t_input.startswith("https://")) else (f"https://www.tiktok.com/@{t_input.replace('@', '')}" if t_input else "")
                new_order = {
                    "order_id": order_id,
                    "token": token,
                    "user_id": current_user["id"],
                    "buyer_account": current_user["username"],
                    "game": game_key,
                    "product_name": game_data.get("name"),
                    "product_type": game_data.get("type"),
                    "package": pkg.get("name"),
                    "package_id": pkg.get("id"),
                    "robux_amount": pkg.get("robux", 0),
                    "original_amount": original_amount,
                    "discount": discount,
                    "promo_code": applied_promo,
                    "amount": amount,
                    "payment_method": "Rolea Wallet",
                    "player_id": t_input,
                    "roblox_username": _sanitize_plain(body.get("username") or t_input, 60),
                    "display_name": _sanitize_plain((body.get("username") or t_input or current_user["username"]) if not is_smm else "TikTok Customer", 60),
                    "roblox_id": None if is_smm else str(abs(sum(ord(c) for c in (t_input or "12345678")))),
                    "profile_url": tt_link if is_smm else (f"https://www.roblox.com/users/1/profile" if game_key == "roblox" else ""),
                    "avatar": "/media/tiktok-thumb.svg" if is_smm else "/media/robux-coin.svg",
                    "target_url": t_input if is_smm else "",
                    "status": "completed" if auto_del else "paid",
                    "step": "delivered" if auto_del else "sending",
                    "paid": True,
                    "delivered": auto_del,
                    "created_at": now.isoformat(),
                    "label": "Payment confirmed via Wallet & items delivered" if auto_del else "Payment confirmed via Wallet. Processing delivery…"
                }

                orders.insert(0, new_order)
                if len(orders) > 500: orders[:] = orders[:500]
                save_orders()
                asyncio.create_task(send_telegram_paid_alert(new_order))
                if auto_del:
                    asyncio.create_task(notify_customer_order_completed(new_order))

                return {
                    "ok": True,
                    "paid_with_wallet": True,
                    "order_id": new_order["order_id"],
                    "receipt_token": new_order["token"],
                    "amount": new_order["amount"],
                    "original_amount": new_order["original_amount"],
                    "discount": new_order["discount"],
                    "promo_code": new_order["promo_code"],
                    "status": new_order["status"],
                    "step": new_order["step"],
                    "remaining_balance": current_user["balance"],
                    "label": new_order["label"]
                }

        # KHQR Checkout
        khqr_res = await create_khqrpay_order(amount, order_id)
        qr_url = ""
        khqrpay_id = None
        payment_url = ""
        aba_deeplink = ""
        expires_at = (now + timedelta(minutes=5)).isoformat()

        if khqr_res and khqr_res.get("id"):
            khqrpay_id = khqr_res["id"]
            qr_url = khqr_res.get("qr_image", "")
            payment_url = khqr_res.get("checkout_url") or f"https://khqrpay.site/pay/{khqrpay_id}"
            aba_deeplink = khqr_res.get("aba_deeplink", "")
            if khqr_res.get("expires_at"):
                expires_at = khqr_res["expires_at"]

        if not qr_url:
            amt_str = f"{amount:.2f}"
            amt_len = f"{len(amt_str):02d}"
            khqr_payload = f"00020101021229370016bakong@rolea010108{order_id}520459995303840540{amt_len}{amt_str}5802KH5911ROLEA TOPUP6010PHNOM PENH62240108{order_id}0708ROLEATOPUP6304"
            qr_url = generate_khqr_data_url(khqr_payload)
            payment_url = f"https://khqrpay.site/pay/{order_id}"

        is_smm = (game_data.get("type") == "smm") or (game_key == "tiktok")
        t_input = str(body.get("player_id") or "").strip()
        tt_link = t_input if (t_input.startswith("http://") or t_input.startswith("https://")) else (f"https://www.tiktok.com/@{t_input.replace('@', '')}" if t_input else "")
        new_order = {
            "order_id": order_id,
            "khqrpay_id": khqrpay_id,
            "token": token,
            "user_id": current_user["id"] if current_user else None,
            "buyer_account": current_user["username"] if current_user else (body.get("username") or body.get("player_id") or ""),
            "game": game_key,
            "product_name": game_data.get("name"),
            "product_type": game_data.get("type"),
            "package": pkg.get("name"),
            "package_id": pkg.get("id"),
            "robux_amount": pkg.get("robux", 0),
            "original_amount": original_amount,
            "discount": discount,
            "promo_code": applied_promo,
            "amount": amount,
            "payment_method": "ABA KHQR",
            "player_id": body.get("player_id", ""),
            "roblox_username": body.get("username") or body.get("player_id") or "",
            "display_name": (body.get("username") or body.get("player_id") or "Player") if not is_smm else "TikTok Customer",
            "roblox_id": None if is_smm else str(abs(sum(ord(c) for c in (body.get("player_id") or "12345678")))),
            "profile_url": tt_link if is_smm else (f"https://www.roblox.com/users/1/profile" if game_key == "roblox" else ""),
            "avatar": "/media/tiktok-thumb.svg" if is_smm else "/media/robux-coin.svg",
            "target_url": t_input if is_smm else "",
            "status": "pending",
            "step": "wait",
            "paid": False,
            "delivered": False,
            "created_at": now.isoformat(),
            "expires_at": expires_at,
            "payment_url": payment_url,
            "aba_deeplink": aba_deeplink,
            "qr_url": qr_url,
            "label": "Waiting for KHQR payment…"
        }

        orders.insert(0, new_order)
        if len(orders) > 500: orders[:] = orders[:500]
        save_orders()

        return {
            "ok": True,
            "order_id": new_order["order_id"],
            "khqrpay_id": new_order["khqrpay_id"],
            "receipt_token": new_order["token"],
            "amount": new_order["amount"],
            "original_amount": new_order["original_amount"],
            "discount": new_order["discount"],
            "promo_code": new_order["promo_code"],
            "qr_url": new_order["qr_url"],
            "payment_url": new_order["payment_url"],
            "aba_deeplink": new_order["aba_deeplink"],
            "expires_at": new_order["expires_at"],
            "status": new_order["status"],
            "step": new_order["step"],
            "robux_amount": new_order["robux_amount"],
            "server_now": datetime.now(timezone.utc).isoformat(),
            "label": new_order["label"]
        }
    except Exception as err:
        print("Create order error:", err)
        return JSONResponse(status_code=500, content={"ok": False, "error": "Unable to process order right now. Please try again."})

@app.get("/api/order-status/{order_id}")
async def get_order_status(order_id: str):
    order = next((o for o in orders if o.get("order_id") == order_id), None)
    if not order:
        return JSONResponse(status_code=404, content={"ok": False, "error": "Order not found"})

    if order.get("khqrpay_id") and not order.get("paid") and order.get("status") not in ["completed", "expired"]:
        live = await check_khqrpay_status(order["khqrpay_id"])
        if live:
            verified_paid, v_st = verify_khqr_bank_payment(live, float(order.get("amount", 0)))
            if verified_paid:
                async with _tx_lock:
                    kid = str(order["khqrpay_id"])
                    if not order.get("paid") and kid not in _credited_khqr_ids:
                        _credited_khqr_ids.add(kid)
                        order["paid"] = True
                        if order.get("type") == "wallet_topup":
                            order["status"] = "completed"
                            order["step"] = "delivered"
                            order["delivered"] = True
                            if not order.get("wallet_credited"):
                                order["wallet_credited"] = True
                                u = next((usr for usr in users if usr.get("id") == order.get("user_id")), None)
                                if u:
                                    u["balance"] = round(float(u.get("balance", 0.0)) + float(order["amount"]), 2)
                                    save_users()
                                    wallet_transactions.insert(0, {
                                        "id": "wtx_" + secrets.token_hex(4),
                                        "user_id": u["id"],
                                        "type": "deposit",
                                        "amount": float(order["amount"]),
                                        "order_id": order["order_id"],
                                        "product": "Wallet Top-up",
                                        "date": datetime.now(timezone.utc).isoformat()
                                    })
                                    save_wallet_tx()
                            order["label"] = f"Wallet successfully topped up (+${float(order['amount']):.2f} USD)"
                        else:
                            order["status"] = "paid"
                            auto_del = bool(settings.get("auto_deliver", False))
                            order["step"] = "delivered" if auto_del else "sending"
                            if auto_del:
                                order["delivered"] = True
                                order["status"] = "completed"
                                order["label"] = "Payment confirmed & items delivered"
                            else:
                                order["delivered"] = False
                                order["status"] = "paid"
                                order["label"] = "Payment confirmed. Waiting for Admin to deliver Robux…"
                            asyncio.create_task(send_telegram_paid_alert(order))
                        save_orders()
            elif v_st == "scanned" and order.get("status") == "pending":
                order["status"] = "scanned"
                order["step"] = "scanned"
                order["label"] = "QR Scanned in ABA Mobile"
                save_orders()
            elif v_st == "expired":
                order["status"] = "expired"
                order["step"] = "expired"
                order["label"] = "Payment expired"
                save_orders()
            elif v_st in ("failed", "amount_mismatch", "currency_mismatch"):
                order["status"] = "failed"
                order["step"] = "failed"
                order["label"] = "Payment verification failed"
                save_orders()

    # Expiry check
    if order.get("status") == "pending" and order.get("expires_at"):
        try:
            exp = datetime.fromisoformat(order["expires_at"].replace("Z", "+00:00"))
            if exp < datetime.now(timezone.utc):
                order["status"] = "expired"
                order["step"] = "expired"
                order["label"] = "Payment expired"
                save_orders()
        except Exception:
            pass

    return {
        "ok": True,
        "order_id": order.get("order_id"),
        "khqrpay_id": order.get("khqrpay_id"),
        "amount": order.get("amount"),
        "status": order.get("status"),
        "step": order.get("step"),
        "paid": order.get("paid"),
        "delivered": order.get("delivered"),
        "robux_amount": order.get("robux_amount"),
        "roblox_username": order.get("roblox_username"),
        "display_name": order.get("display_name"),
        "roblox_id": order.get("roblox_id"),
        "package": order.get("package"),
        "product_name": order.get("product_name"),
        "product_type": order.get("product_type"),
        "qr_url": order.get("qr_url"),
        "payment_url": order.get("payment_url"),
        "aba_deeplink": order.get("aba_deeplink"),
        "expires_at": order.get("expires_at"),
        "server_now": datetime.now(timezone.utc).isoformat(),
        "label": order.get("label")
    }

@app.post("/api/check-order")
async def check_single_order(request: Request):
    body = await request.json() if (await request.body()) else {}
    order_id = body.get("order_id")
    username = body.get("username")
    receipt_token = body.get("receipt_token")

    order = next((o for o in orders if o.get("order_id") == order_id), None)
    if not order:
        return JSONResponse(status_code=404, content={"ok": False, "error": "Order not found. Please verify your Order ID."})

    token_match = receipt_token and order.get("token") == receipt_token
    user_match = username and order.get("roblox_username", "").lower() == username.strip().lower()

    if not token_match and not user_match:
        return JSONResponse(status_code=403, content={
            "ok": False,
            "error": "Receipt token does not match. For privacy, use the token saved on this device or contact support."
        })

    if token_match:
        return {"ok": True, "order": order}
    safe_order = {k: v for k, v in order.items() if k not in ("token", "khqrpay_id", "qr_url", "payment_url", "aba_deeplink")}
    return {"ok": True, "order": safe_order}

@app.post("/api/customer-orders")
async def get_customer_orders(request: Request):
    body = await request.json() if (await request.body()) else {}
    refs = body.get("orders")
    if not isinstance(refs, list):
        return {"ok": True, "orders": []}

    token_map = {r["order_id"]: r["token"] for r in refs if isinstance(r, dict) and r.get("order_id") and r.get("token")}
    matched = [o for o in orders if token_map.get(o.get("order_id")) == o.get("token")]
    return {"ok": True, "orders": matched}

@app.post("/api/simulate-pay")
async def simulate_pay(request: Request):
    if not verify_admin_session(request):
        return JSONResponse(status_code=403, content={"ok": False, "error": "Forbidden: Admin authentication required"})
    body = await request.json() if (await request.body()) else {}
    order_id = body.get("order_id")
    action = body.get("action")
    order = next((o for o in orders if o.get("order_id") == order_id), None)
    if not order:
        return JSONResponse(status_code=404, content={"ok": False, "error": "Order not found"})

    if action == "scan":
        order["status"] = "scanned"
        order["step"] = "scanned"
        order["label"] = "QR Scanned in ABA Mobile"
    elif action == "pay":
        order["status"] = "paid"
        order["paid"] = True
        order["step"] = "sending"
        order["label"] = "Payment Confirmed! Queuing delivery…"

        async def auto_deliver_after_delay(target_id):
            await asyncio.sleep(3.5)
            live = next((o for o in orders if o.get("order_id") == target_id), None)
            if live and live.get("paid"):
                live["status"] = "completed"
                live["delivered"] = True
                live["step"] = "delivered"
                live["label"] = "Delivery confirmed!"
                save_orders()
                try:
                    deduct_inventory_on_deliver(live)
                except Exception as eInv:
                    print("Inventory deduction error:", eInv)
        asyncio.create_task(auto_deliver_after_delay(order_id))

    elif action == "deliver":
        order["status"] = "completed"
        order["paid"] = True
        order["delivered"] = True
        order["step"] = "delivered"
        order["label"] = "Sent successfully!"
        try:
            deduct_inventory_on_deliver(order)
        except Exception as eInv:
            print("Inventory deduction error:", eInv)
    elif action == "hold":
        order["step"] = "hold"
        order["label"] = "Order on hold (awaiting account)"
    elif action == "fail":
        order["status"] = "failed"
        order["step"] = "failed"
        order["label"] = "Payment failed"

    save_orders()
    return {"ok": True, "order": order}

# ==========================================
# ADMIN DASHBOARD APIS
# ==========================================

@app.post("/api/admin/login")
async def admin_login(request: Request):
    client_ip = get_admin_effective_ip(request) or "unknown"
    now_ts = time.time()

    # Check IP lockout (Brute-force protection)
    lock_until = admin_lockouts.get(client_ip, 0)
    if lock_until > now_ts:
        wait_sec = int(lock_until - now_ts)
        return JSONResponse(
            status_code=429,
            content={"ok": False, "error": f"Too many failed login attempts. Try again in {wait_sec}s."}
        )

    body = await request.json() if (await request.body()) else {}
    username = str(body.get("username") or "").strip()
    password = str(body.get("password") or "")
    pin = str(body.get("pin") or "").strip()

    stored_user = admin_security.get("username", "admin")
    stored_salt = admin_security.get("password_salt", "")
    stored_hash = admin_security.get("password_hash", "")
    candidate_hash = hash_admin_secret(password, stored_salt)

    if not hmac.compare_digest(username, stored_user) or not hmac.compare_digest(candidate_hash, stored_hash):
        attempts = [t for t in admin_failed_attempts.get(client_ip, []) if now_ts - t < 900]
        attempts.append(now_ts)
        admin_failed_attempts[client_ip] = attempts
        remaining = max(0, 5 - len(attempts))
        if len(attempts) >= 5:
            admin_lockouts[client_ip] = now_ts + 300
            admin_failed_attempts[client_ip] = []
            log_admin_security_event("IP Locked Out", client_ip, username or "unknown", "locked", "5 consecutive failed attempts (5 min ban)")
            asyncio.create_task(send_admin_security_telegram(
                f"<b>[SECURITY ALERT] Admin Brute-Force Blocked</b>\nIP Address: <code>{client_ip}</code>\nAttempted User: <code>{username}</code>\nStatus: Locked out for 5 minutes."
            ))
            return JSONResponse(status_code=429, content={"ok": False, "error": "Account temporarily locked for 5 minutes due to 5 failed attempts."})
        log_admin_security_event("Failed Login", client_ip, username or "unknown", "failed", f"Invalid credentials ({remaining} attempts left)")
        return JSONResponse(status_code=401, content={"ok": False, "error": f"Invalid username or password. ({remaining} attempts remaining)"})

    # Optional 2FA Security PIN check
    if admin_security.get("pin_enabled"):
        if not pin:
            return {"ok": False, "require_pin": True, "message": "Enter your 2FA Security PIN"}
        pin_salt = admin_security.get("pin_salt", "")
        pin_hash = admin_security.get("pin_hash", "")
        if not hmac.compare_digest(hash_admin_secret(pin, pin_salt), pin_hash):
            attempts = [t for t in admin_failed_attempts.get(client_ip, []) if now_ts - t < 900]
            attempts.append(now_ts)
            admin_failed_attempts[client_ip] = attempts
            log_admin_security_event("Failed 2FA PIN", client_ip, username, "failed", "Incorrect Security PIN")
            return JSONResponse(status_code=401, content={"ok": False, "error": "Incorrect 2FA Security PIN."})

    # Success: reset failed attempts & create cryptographic session
    admin_failed_attempts.pop(client_ip, None)
    admin_lockouts.pop(client_ip, None)
    cleanup_expired_admin_sessions()

    raw_token = secrets.token_urlsafe(32)
    token_hash = hash_session_token(raw_token)
    timeout_hours = int(admin_security.get("session_timeout_hours", 24))
    expires_ms = int((now_ts + timeout_hours * 3600) * 1000)

    admin_security.setdefault("sessions", {})[token_hash] = {
        "token_id": token_hash[:10],
        "ip": client_ip,
        "user_agent": str(request.headers.get("user-agent", "Unknown"))[:90],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": expires_ms
    }
    log_admin_security_event("Login Success", client_ip, username, "success", "Authenticated session issued")
    save_admin_security()

    asyncio.create_task(send_admin_security_telegram(
        f"<b>[ADMIN LOGIN] New Admin Session Started</b>\nUsername: <code>{username}</code>\nIP Address: <code>{client_ip}</code>"
    ))

    resp = JSONResponse(content={
        "ok": True,
        "token": raw_token,
        "is_default_password": bool(admin_security.get("is_default_password", False))
    })
    resp.set_cookie(
        key="rolea_admin_token",
        value=raw_token,
        httponly=True,
        samesite="lax",
        path="/",
        max_age=timeout_hours * 3600
    )
    return resp

@app.post("/api/admin/logout")
async def admin_logout(request: Request):
    token_hash = verify_admin_session(request)
    if token_hash and token_hash in admin_security.get("sessions", {}):
        admin_security["sessions"].pop(token_hash, None)
        save_admin_security()
    resp = JSONResponse(content={"ok": True})
    resp.delete_cookie("rolea_admin_token", path="/")
    return resp

admin_reset_otp_state: Dict[str, Any] = {}

@app.post("/api/admin/forgot-password")
async def admin_forgot_password(request: Request):
    client_ip = request.client.host if request.client else "unknown"
    now_ts = time.time()
    if admin_lockouts.get(client_ip, 0) > now_ts:
        wait_sec = int(admin_lockouts[client_ip] - now_ts)
        return JSONResponse(status_code=429, content={"ok": False, "error": f"Temporarily locked. Try again in {wait_sec}s."})

    if admin_reset_otp_state.get("last_sent", 0) + 20 > now_ts:
        wait_s = int(admin_reset_otp_state["last_sent"] + 20 - now_ts)
        return JSONResponse(status_code=429, content={"ok": False, "error": f"Please wait {wait_s}s before requesting another code."})

    body = await request.json() if (await request.body()) else {}
    req_email = str(body.get("email") or "").strip().lower()

    configured_admin_email = str(settings.get("admin_recovery_email") or settings.get("smtp_email") or "").strip().lower()
    smtp_ready = bool(settings.get("smtp_email") and settings.get("smtp_password"))
    tg_token = settings.get("telegram_bot_token")
    tg_chat = settings.get("telegram_chat_id")

    if req_email:
        if not smtp_ready:
            return JSONResponse(status_code=400, content={"ok": False, "error": "Gmail SMTP is not configured yet! Add Sender Email & Gmail App Password in Admin Store Settings first."})
        if configured_admin_email and req_email != configured_admin_email:
            return JSONResponse(status_code=400, content={"ok": False, "error": "This email does not match the configured Admin Recovery Email."})

    if not smtp_ready and (not tg_token or not tg_chat):
        return JSONResponse(status_code=400, content={"ok": False, "error": "Neither SMTP Email nor Telegram Bot is configured."})

    otp_code = f"{secrets.randbelow(900000) + 100000}"
    otp_salt = secrets.token_hex(12)
    admin_reset_otp_state.clear()
    admin_reset_otp_state.update({
        "salt": otp_salt,
        "hash": hash_admin_secret(otp_code, otp_salt),
        "expires_at": now_ts + 600,
        "attempts": 0,
        "last_sent": now_ts
    })

    sent_channels = []
    target_email = req_email or configured_admin_email
    if smtp_ready and target_email:
        store_name = settings.get("store_name", "Rolea Topup")
        subj = f"{store_name} Admin Password Reset Code: {otp_code}"
        html_body = build_password_reset_email_html(store_name, admin_security.get("username", "admin"), otp_code, client_ip)
        txt_body = f"{store_name} Password Reset Code: {otp_code}\nHello admin, a password reset code was requested from IP {client_ip}."
        ok_mail, mail_err = await send_smtp_email(target_email, subj, html_body, txt_body)
        if ok_mail:
            sent_channels.append(f"Email ({target_email})")
        else:
            if req_email:
                admin_reset_otp_state.clear()
                return JSONResponse(status_code=500, content={"ok": False, "error": f"Failed to send email: {mail_err}"})

    if tg_token and tg_chat:
        msg = (
            f"<b>[ADMIN PASSWORD RESET] {settings.get('store_name', 'Rolea Topup')}</b>\n\n"
            f"Password Reset Code: <code>{otp_code}</code>\n"
            f"Requested from IP: <code>{client_ip}</code>\n"
            f"Valid for 10 minutes."
        )
        asyncio.create_task(send_telegram_direct_message(tg_token, tg_chat, msg))
        sent_channels.append("Telegram")

    log_admin_security_event("Reset Code Sent", client_ip, admin_security.get("username", "admin"), "success", f"Sent via {', '.join(sent_channels)}")
    return {"ok": True, "message": f"6-digit Password Reset Code sent to {' & '.join(sent_channels)}!"}

@app.post("/api/admin/verify-reset-code")
async def admin_verify_reset_code(request: Request):
    client_ip = request.client.host if request.client else "unknown"
    now_ts = time.time()
    if admin_lockouts.get(client_ip, 0) > now_ts:
        wait_sec = int(admin_lockouts[client_ip] - now_ts)
        return JSONResponse(status_code=429, content={"ok": False, "error": f"Temporarily locked. Try again in {wait_sec}s."})

    body = await request.json() if (await request.body()) else {}
    code = str(body.get("code") or "").strip()
    if not code:
        return JSONResponse(status_code=400, content={"ok": False, "error": "Please enter the 6-digit Password Reset Code."})

    if not admin_reset_otp_state.get("hash") or now_ts > admin_reset_otp_state.get("expires_at", 0):
        admin_reset_otp_state.clear()
        return JSONResponse(status_code=400, content={"ok": False, "error": "Recovery code expired or not requested. Send a new code."})

    admin_reset_otp_state["attempts"] = admin_reset_otp_state.get("attempts", 0) + 1
    if admin_reset_otp_state["attempts"] > 5:
        admin_reset_otp_state.clear()
        admin_lockouts[client_ip] = now_ts + 300
        log_admin_security_event("Reset OTP Failed", client_ip, admin_security.get("username", "admin"), "locked", "Too many wrong OTP attempts")
        return JSONResponse(status_code=429, content={"ok": False, "error": "Too many wrong OTP attempts. Locked for 5 minutes."})

    cand_hash = hash_admin_secret(code, admin_reset_otp_state["salt"])
    if not hmac.compare_digest(cand_hash, admin_reset_otp_state["hash"]):
        log_admin_security_event("Reset OTP Failed", client_ip, admin_security.get("username", "admin"), "failed", "Incorrect recovery OTP")
        return JSONResponse(status_code=401, content={"ok": False, "error": "Incorrect 6-digit recovery code."})

    reset_token = secrets.token_urlsafe(24)
    admin_reset_otp_state["verified"] = True
    admin_reset_otp_state["reset_token"] = reset_token
    return {"ok": True, "reset_token": reset_token, "message": "Code verified! Enter your new Admin password."}

@app.post("/api/admin/reset-password")
async def admin_reset_password(request: Request):
    client_ip = request.client.host if request.client else "unknown"
    now_ts = time.time()
    if admin_lockouts.get(client_ip, 0) > now_ts:
        wait_sec = int(admin_lockouts[client_ip] - now_ts)
        return JSONResponse(status_code=429, content={"ok": False, "error": f"Temporarily locked. Try again in {wait_sec}s."})

    body = await request.json() if (await request.body()) else {}
    reset_token = str(body.get("reset_token") or "").strip()
    new_pw = str(body.get("new_password") or "")
    confirm_pw = str(body.get("confirm_password") or "")

    if not reset_token or not admin_reset_otp_state.get("verified") or now_ts > admin_reset_otp_state.get("expires_at", 0):
        return JSONResponse(status_code=403, content={"ok": False, "error": "Please verify the 6-digit Password Reset Code first."})

    if not hmac.compare_digest(admin_reset_otp_state.get("reset_token", ""), reset_token):
        return JSONResponse(status_code=403, content={"ok": False, "error": "Invalid verification session."})

    if len(new_pw) < 6:
        return JSONResponse(status_code=400, content={"ok": False, "error": "New password must be at least 6 characters."})
    if new_pw != confirm_pw:
        return JSONResponse(status_code=400, content={"ok": False, "error": "Passwords do not match."})

    new_salt = secrets.token_hex(16)
    admin_security["password_salt"] = new_salt
    admin_security["password_hash"] = hash_admin_secret(new_pw, new_salt)
    admin_security["is_default_password"] = False
    admin_security["sessions"] = {}
    admin_reset_otp_state.clear()
    log_admin_security_event("Password Reset", client_ip, admin_security.get("username", "admin"), "success", "Admin password recovered via verified OTP")
    save_admin_security()
    return {"ok": True, "message": "Admin password updated! You can now sign in."}

@app.get("/api/admin/security")
async def admin_get_security(request: Request):
    cleanup_expired_admin_sessions()
    current_hash = verify_admin_session(request)
    sessions_list = []
    for k, s in admin_security.get("sessions", {}).items():
        sessions_list.append({
            "token_id": s.get("token_id", k[:10]),
            "ip": s.get("ip", "unknown"),
            "user_agent": s.get("user_agent", "Browser"),
            "created_at": s.get("created_at", ""),
            "is_current": (k == current_hash)
        })
    now_utc = datetime.now(timezone.utc)
    logs = admin_security.get("login_logs", [])
    failed_24h = 0
    for l in logs:
        if l.get("status") in ("failed", "locked"):
            try:
                t = datetime.fromisoformat(l["time"].replace("Z", "+00:00"))
                if (now_utc - t).total_seconds() <= 86400:
                    failed_24h += 1
            except Exception:
                pass
    return {
        "ok": True,
        "username": admin_security.get("username", "admin"),
        "is_default_password": bool(admin_security.get("is_default_password", False)),
        "pin_enabled": bool(admin_security.get("pin_enabled", False)),
        "session_timeout_hours": int(admin_security.get("session_timeout_hours", 24)),
        "telegram_login_alert": bool(admin_security.get("telegram_login_alert", True)),
        "active_sessions": sessions_list,
        "login_logs": logs[:20],
        "failed_24h": failed_24h
    }

@app.post("/api/admin/security/password")
async def admin_change_password(request: Request):
    body = await request.json() if (await request.body()) else {}
    current_pw = str(body.get("current_password") or "")
    new_user = str(body.get("new_username") or admin_security.get("username", "admin")).strip()
    new_pw = str(body.get("new_password") or "")
    confirm_pw = str(body.get("confirm_password") or "")

    stored_salt = admin_security.get("password_salt", "")
    stored_hash = admin_security.get("password_hash", "")
    if not hmac.compare_digest(hash_admin_secret(current_pw, stored_salt), stored_hash):
        return JSONResponse(status_code=403, content={"ok": False, "error": "Current password is incorrect."})

    if not new_user or len(new_user) < 3:
        return JSONResponse(status_code=400, content={"ok": False, "error": "Username must be at least 3 characters."})
    if len(new_pw) < 6:
        return JSONResponse(status_code=400, content={"ok": False, "error": "New password must be at least 6 characters."})
    if new_pw != confirm_pw:
        return JSONResponse(status_code=400, content={"ok": False, "error": "New password and confirmation do not match."})

    new_salt = secrets.token_hex(16)
    admin_security["username"] = new_user
    admin_security["password_salt"] = new_salt
    admin_security["password_hash"] = hash_admin_secret(new_pw, new_salt)
    admin_security["is_default_password"] = False

    # Revoke all other sessions except current
    current_hash = verify_admin_session(request)
    if current_hash and current_hash in admin_security.get("sessions", {}):
        curr = admin_security["sessions"][current_hash]
        admin_security["sessions"] = {current_hash: curr}

    client_ip = request.client.host if request.client else "unknown"
    log_admin_security_event("Credentials Updated", client_ip, new_user, "success", "Admin password & username updated; other sessions revoked")
    save_admin_security()
    return {"ok": True, "message": "Admin credentials updated securely!"}

@app.post("/api/admin/security/policy")
async def admin_update_security_policy(request: Request):
    body = await request.json() if (await request.body()) else {}
    pin_enabled = bool(body.get("pin_enabled", False))
    new_pin = str(body.get("new_pin") or "").strip()
    timeout_hours = int(body.get("session_timeout_hours", 24))
    telegram_alert = bool(body.get("telegram_login_alert", True))

    if pin_enabled:
        if new_pin:
            if not new_pin.isdigit() or not (4 <= len(new_pin) <= 8):
                return JSONResponse(status_code=400, content={"ok": False, "error": "Security PIN must be 4 to 8 digits."})
            pin_salt = secrets.token_hex(16)
            admin_security["pin_salt"] = pin_salt
            admin_security["pin_hash"] = hash_admin_secret(new_pin, pin_salt)
        elif not admin_security.get("pin_hash"):
            return JSONResponse(status_code=400, content={"ok": False, "error": "Please enter a 4-8 digit Security PIN to enable 2FA."})

    admin_security["pin_enabled"] = pin_enabled
    admin_security["session_timeout_hours"] = max(1, min(168, timeout_hours))
    admin_security["telegram_login_alert"] = telegram_alert

    client_ip = request.client.host if request.client else "unknown"
    log_admin_security_event("Policy Updated", client_ip, admin_security.get("username", "admin"), "success", f"2FA PIN: {'ON' if pin_enabled else 'OFF'}, Timeout: {admin_security['session_timeout_hours']}h")
    save_admin_security()
    return {"ok": True, "message": "Security policies saved!"}

@app.post("/api/admin/security/revoke-sessions")
async def admin_revoke_sessions(request: Request):
    current_hash = verify_admin_session(request)
    if current_hash and current_hash in admin_security.get("sessions", {}):
        curr = admin_security["sessions"][current_hash]
        admin_security["sessions"] = {current_hash: curr}
    else:
        admin_security["sessions"] = {}
    client_ip = request.client.host if request.client else "unknown"
    log_admin_security_event("Sessions Revoked", client_ip, admin_security.get("username", "admin"), "success", "All other active devices signed out")
    save_admin_security()
    return {"ok": True, "message": "All other sessions revoked."}

@app.get("/api/admin/stats")
async def admin_stats():
    product_orders = [
        o for o in orders 
        if o.get("type") != "wallet_topup" 
        and o.get("product_type") != "wallet" 
        and not str(o.get("order_id", "")).startswith("WLT")
    ]
    revenue = sum(float(o.get("amount", 0)) for o in product_orders if o.get("paid"))
    robux_del = sum(float(o.get("robux_amount", 0)) for o in product_orders if o.get("delivered"))
    pending = len([o for o in product_orders if not o.get("paid") and o.get("status") not in ["failed", "expired"]])
    return {
        "ok": True,
        "stats": {
            "revenue": round(revenue, 2),
            "total_orders": len(product_orders),
            "robux_delivered": robux_del,
            "pending_orders": pending
        }
    }

@app.get("/api/admin/orders")
async def admin_get_orders():
    # Only show product orders that need fulfillment, NOT wallet deposits
    product_orders = [
        o for o in orders 
        if o.get("type") != "wallet_topup" 
        and o.get("product_type") != "wallet" 
        and not str(o.get("order_id", "")).startswith("WLT")
    ]
    return {"ok": True, "orders": product_orders}

@app.post("/api/admin/order-action")
async def admin_order_action(request: Request):
    body = await request.json() if (await request.body()) else {}
    order_id = body.get("order_id")
    action = body.get("action")

    idx = next((i for i, o in enumerate(orders) if o.get("order_id") == order_id), -1)
    if idx == -1:
        return JSONResponse(status_code=404, content={"ok": False, "error": "Order not found"})

    order = orders[idx]

    if action == "delete":
        orders.pop(idx)
        save_orders()
        return {"ok": True, "message": "Order deleted"}

    if action == "mark_paid":
        order["paid"] = True
        order["status"] = "paid"
        order["step"] = "sending"
        order["label"] = "Payment verified by Admin"
        if order.get("type") == "wallet_topup" and not order.get("wallet_credited"):
            order["wallet_credited"] = True
            u = next((usr for usr in users if usr.get("id") == order.get("user_id")), None)
            if u:
                u["balance"] = round(float(u.get("balance", 0.0)) + float(order["amount"]), 2)
                save_users()
                wallet_transactions.insert(0, {
                    "id": "wtx_" + secrets.token_hex(4),
                    "user_id": u["id"],
                    "type": "deposit",
                    "amount": float(order["amount"]),
                    "order_id": order["order_id"],
                    "product": "Wallet Top-up (Admin Action)",
                    "date": datetime.now(timezone.utc).isoformat()
                })
                save_wallet_tx()

        save_orders()
        asyncio.create_task(send_telegram_paid_alert(order))

        if settings.get("auto_deliver"):
            async def auto_del_task(tgt_id):
                await asyncio.sleep(3.5)
                live = next((o for o in orders if o.get("order_id") == tgt_id), None)
                if live and live.get("paid"):
                    live["status"] = "completed"
                    live["delivered"] = True
                    live["step"] = "delivered"
                    live["label"] = "Delivery confirmed!"
                    save_orders()
            asyncio.create_task(auto_del_task(order_id))

    elif action == "deliver":
        order["paid"] = True
        order["delivered"] = True
        order["status"] = "completed"
        order["step"] = "delivered"
        order["label"] = "Order fulfilled successfully!"
        asyncio.create_task(notify_customer_order_completed(order))
        if order.get("type") == "wallet_topup" and not order.get("wallet_credited"):
            order["wallet_credited"] = True
            u = next((usr for usr in users if usr.get("id") == order.get("user_id")), None)
            if u:
                u["balance"] = round(float(u.get("balance", 0.0)) + float(order["amount"]), 2)
                save_users()
                wallet_transactions.insert(0, {
                    "id": "wtx_" + secrets.token_hex(4),
                    "user_id": u["id"],
                    "type": "deposit",
                    "amount": float(order["amount"]),
                    "order_id": order["order_id"],
                    "product": "Wallet Top-up (Admin Action)",
                    "date": datetime.now(timezone.utc).isoformat()
                })
                save_wallet_tx()
        save_orders()
        asyncio.create_task(send_telegram_paid_alert(order))

    elif action == "hold":
        order["step"] = "hold"
        order["label"] = "Order on hold (manual review)"
        save_orders()
    elif action == "failed":
        order["status"] = "failed"
        order["step"] = "failed"
        order["label"] = "Order marked failed by Admin"
        save_orders()

    return {"ok": True, "order": order}

# Games Admin
@app.get("/api/admin/games")
async def admin_get_games():
    return {"ok": True, "games": games}

@app.post("/api/admin/games/edit")
async def admin_edit_game(request: Request):
    body = await request.json() if (await request.body()) else {}
    gid = body.get("id")
    if not gid or gid not in games:
        return JSONResponse(status_code=404, content={"ok": False, "error": "Game not found"})
    g = games[gid]
    for field in ["name", "category", "kicker", "unit", "logo", "banner", "badge"]:
        if field in body and body[field] is not None:
            g[field] = body[field]
    if "enabled" in body:
        g["enabled"] = bool(body["enabled"])
    save_games()
    return {"ok": True, "game": g}

@app.post("/api/admin/games/add")
async def admin_add_game(request: Request):
    body = await request.json() if (await request.body()) else {}
    name = (body.get("name") or "").strip()
    if not name:
        return JSONResponse(status_code=400, content={"ok": False, "error": "Game name is required"})

    gid = (body.get("id") or "").strip().lower()
    if not gid:
        gid = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    else:
        gid = re.sub(r"[^a-z0-9_-]+", "", gid)

    if not gid:
        gid = "game_" + str(int(time.time()))
    if gid in games:
        gid = f"{gid}_{secrets.token_hex(2)}"

    unit = (body.get("unit") or "Units").strip()
    logo = (body.get("logo") or "/media/rolea-logo.webp").strip()
    banner = (body.get("banner") or "/media/banner1.webp").strip()

    new_game = {
        "id": gid,
        "name": name,
        "category": (body.get("category") or "Topup & Game Services").strip(),
        "kicker": (body.get("kicker") or f"{name.upper()} • TOPUP").strip(),
        "unit": unit,
        "type": gid,
        "enabled": bool(body.get("enabled", True)),
        "logo": logo,
        "banner": banner,
        "badge": body.get("badge") or "NEW"
    }
    games[gid] = new_game
    save_games()

    packages.extend([
        {
            "id": f"pkg_{gid}_1",
            "game": gid,
            "name": f"100 {unit}",
            "robux": 100,
            "price": 1.00,
            "badge": "STARTER",
            "icon": logo,
            "ok": 1
        },
        {
            "id": f"pkg_{gid}_2",
            "game": gid,
            "name": f"500 {unit}",
            "robux": 500,
            "price": 4.50,
            "badge": "POPULAR",
            "icon": logo,
            "ok": 1
        }
    ])
    save_packages()

    return {"ok": True, "game": new_game, "id": gid}

@app.post("/api/admin/games/delete")
async def admin_delete_game(request: Request):
    global packages
    body = await request.json() if (await request.body()) else {}
    gid = body.get("id")
    if not gid or gid not in games:
        return JSONResponse(status_code=404, content={"ok": False, "error": "Game not found"})

    if len(games) <= 1:
        return JSONResponse(status_code=400, content={"ok": False, "error": "Cannot delete the only remaining game."})

    del_name = games[gid]["name"]
    del games[gid]
    save_games()

    packages = [p for p in packages if p.get("game", "roblox") != gid]
    save_packages()

    return {"ok": True, "message": f"Game {del_name} deleted", "remainingGames": list(games.keys())}

@app.post("/api/admin/games/toggle")
async def admin_toggle_game(request: Request):
    body = await request.json() if (await request.body()) else {}
    gid = body.get("id")
    if not gid or gid not in games:
        return JSONResponse(status_code=404, content={"ok": False, "error": "Game not found"})
    games[gid]["enabled"] = not games[gid].get("enabled", True)
    save_games()
    return {"ok": True, "game": games[gid]}

@app.post("/api/admin/games/upload-logo")
async def admin_upload_game_logo(request: Request):
    body = await request.json() if (await request.body()) else {}
    gid = body.get("id")
    image_url = body.get("image_url")
    image_base64 = body.get("image_base64")

    if image_url:
        url = str(image_url).strip()
        if gid and gid in games:
            games[gid]["logo"] = url
            save_games()
        return {"ok": True, "logo": url}

    if image_base64:
        try:
            m = re.match(r"^data:image/([a-zA-Z0-9+]+);base64,(.+)$", image_base64)
            ext = "webp"
            data = image_base64
            if m:
                ext = "jpg" if m.group(1) == "jpeg" else ("png" if m.group(1) == "png" else "webp")
                data = m.group(2)
            buf = base64.b64decode(data)
            safe_id = re.sub(r"[^a-zA-Z0-9_-]", "", gid or "game")
            filename = f"logo_{safe_id}_{int(time.time() * 1000)}.{ext}"
            with open(MEDIA_DIR / filename, "wb") as f:
                f.write(buf)
            final_logo_url = f"/media/{filename}"
            if gid and gid in games:
                games[gid]["logo"] = final_logo_url
                save_games()
            return {"ok": True, "logo": final_logo_url}
        except Exception as err:
            return JSONResponse(status_code=500, content={"ok": False, "error": "Failed to upload game logo"})

    return JSONResponse(status_code=400, content={"ok": False, "error": "No image provided"})

# Packages Admin
@app.get("/api/admin/packages")
async def admin_get_packages(game: Optional[str] = None):
    if game:
        return {"ok": True, "packages": [p for p in packages if p.get("game", "roblox") == game]}
    return {"ok": True, "packages": packages}

@app.post("/api/admin/packages/add")
async def admin_add_package(request: Request):
    body = await request.json() if (await request.body()) else {}
    name = body.get("name")
    robux = body.get("robux")
    price = body.get("price")
    if not name or robux is None or price is None:
        return JSONResponse(status_code=400, content={"ok": False, "error": "Missing package fields"})

    game_key = body.get("game") or "roblox"
    default_icon = games.get(game_key, {}).get("logo") or "/media/rolea-logo.webp"
    new_pkg = {
        "id": "pkg_" + secrets.token_hex(4),
        "game": game_key,
        "name": name,
        "robux": float(robux),
        "price": float(price),
        "badge": str(body.get("badge") or "").strip().upper(),
        "ok": 1,
        "in_stock": bool(body.get("in_stock", True)),
        "icon": body.get("icon") or default_icon
    }
    packages.append(new_pkg)
    save_packages()
    return {"ok": True, "package": new_pkg}

@app.post("/api/admin/packages/edit")
async def admin_edit_package(request: Request):
    body = await request.json() if (await request.body()) else {}
    pid = body.get("id")
    pkg = next((p for p in packages if p.get("id") == pid), None)
    if not pkg:
        return JSONResponse(status_code=404, content={"ok": False, "error": "Package not found"})

    if "name" in body: pkg["name"] = body["name"]
    if "robux" in body: pkg["robux"] = float(body["robux"])
    if "price" in body: pkg["price"] = float(body["price"])
    if "badge" in body: pkg["badge"] = str(body["badge"]).strip().upper()
    if "ok" in body: pkg["ok"] = 1 if body["ok"] else 0
    if "icon" in body: pkg["icon"] = body["icon"]
    if "game" in body: pkg["game"] = body["game"]
    if "in_stock" in body: pkg["in_stock"] = bool(body["in_stock"])

    save_packages()
    return {"ok": True, "package": pkg}

@app.post("/api/admin/packages/toggle")
async def admin_toggle_package(request: Request):
    body = await request.json() if (await request.body()) else {}
    pid = body.get("id")
    pkg = next((p for p in packages if p.get("id") == pid), None)
    if not pkg:
        return JSONResponse(status_code=404, content={"ok": False, "error": "Package not found"})
    pkg["ok"] = 0 if pkg.get("ok") == 1 else 1
    save_packages()
    return {"ok": True, "package": pkg}

@app.post("/api/admin/packages/delete")
async def admin_delete_package(request: Request):
    global packages
    body = await request.json() if (await request.body()) else {}
    pid = body.get("id")
    packages = [p for p in packages if p.get("id") != pid]
    save_packages()
    return {"ok": True}

# Settings Admin
@app.get("/api/admin/settings")
async def admin_get_settings():
    return {"ok": True, "settings": settings}

@app.post("/api/admin/settings")
async def admin_save_settings(request: Request):
    body = await request.json() if (await request.body()) else {}
    for key in ["store_name", "telegram_handle", "khqr_merchant_name", "khqr_account", "khqrpay_api_key", "khqrpay_base_url", "home_banner", "roblox_banner", "google_client_id"]:
        if key in body and body[key] is not None:
            settings[key] = str(body[key]).strip()
    if "telegram_bot_token" in body and body["telegram_bot_token"] is not None:
        settings["telegram_bot_token"] = str(body["telegram_bot_token"]).strip()
    if "telegram_chat_id" in body and body["telegram_chat_id"] is not None:
        settings["telegram_chat_id"] = str(body["telegram_chat_id"]).strip()
    for sm_key in ["smtp_host", "smtp_email", "smtp_password", "admin_recovery_email"]:
        if sm_key in body and body[sm_key] is not None:
            settings[sm_key] = str(body[sm_key]).strip()
    if "smtp_port" in body and body["smtp_port"] is not None:
        try:
            settings["smtp_port"] = int(body["smtp_port"])
        except Exception:
            settings["smtp_port"] = 587
    if "auto_deliver" in body and isinstance(body["auto_deliver"], bool):
        settings["auto_deliver"] = body["auto_deliver"]

    save_settings()
    return {"ok": True, "settings": settings}

@app.post("/api/admin/email/test")
async def admin_test_email(request: Request):
    body = await request.json() if (await request.body()) else {}
    target = str(body.get("to_email") or settings.get("admin_recovery_email") or settings.get("smtp_email") or "").strip()
    if not target:
        return JSONResponse(status_code=400, content={"ok": False, "error": "Please enter Sender Email & Admin Recovery Email first, then Save Settings."})
    store_name = settings.get("store_name", "Rolea Topup")
    sample_code = "570929"
    client_ip = request.client.host if request.client else "127.0.0.1"
    html_body = build_password_reset_email_html(store_name, admin_security.get("username", "admin"), sample_code, client_ip)
    txt_body = f"{store_name} Test Password Reset Code: {sample_code}"
    ok_mail, err = await send_smtp_email(target, f"{store_name} Password Reset Code: {sample_code}", html_body, txt_body)
    if ok_mail:
        return {"ok": True, "message": f"Test Password Reset email sent to {target}! Check your Gmail inbox."}
    return JSONResponse(status_code=400, content={"ok": False, "error": f"SMTP Error: {err}"})



# ==========================================
# PROFIT CALCULATOR & TELEGRAM BROADCAST API
# ==========================================

@app.get("/api/admin/profit-analytics")
async def admin_profit_analytics():
    total_rev = 0.0
    total_cost = 0.0
    today_rev = 0.0
    today_cost = 0.0
    
    now_date = datetime.now().strftime("%Y-%m-%d")
    
    # Track package sales and profit
    pkg_stats = {}
    
    for o in orders:
        # Ignore unconfirmed / failed orders
        status = str(o.get("status", "")).lower()
        if status in ["failed", "cancelled"]:
            continue
        # Only count product sales (not wallet balance topups)
        if o.get("type") == "wallet_topup" or str(o.get("order_id", "")).startswith("WLT"):
            continue
            
        price = float(o.get("amount") or o.get("price") or 0.0)
        # Check if package has custom cost_price, else default to 75% of retail price (25% margin)
        cost = float(o.get("cost_price") or o.get("cost") or round(price * 0.75, 2))
        profit = round(price - cost, 2)
        
        total_rev += price
        total_cost += cost
        
        o_date = str(o.get("created_at") or o.get("date") or "")
        if now_date in o_date:
            today_rev += price
            today_cost += cost
            
        pkg_name = o.get("package") or o.get("tier_title") or f"{o.get('robux_amount', '')} Units".strip()
        if not pkg_name or pkg_name == "Units":
            pkg_name = "General Package"
            
        if pkg_name not in pkg_stats:
            pkg_stats[pkg_name] = {
                "name": pkg_name,
                "sold_count": 0,
                "revenue": 0.0,
                "cost": 0.0,
                "profit": 0.0
            }
        pkg_stats[pkg_name]["sold_count"] += 1
        pkg_stats[pkg_name]["revenue"] = round(pkg_stats[pkg_name]["revenue"] + price, 2)
        pkg_stats[pkg_name]["cost"] = round(pkg_stats[pkg_name]["cost"] + cost, 2)
        pkg_stats[pkg_name]["profit"] = round(pkg_stats[pkg_name]["profit"] + profit, 2)

    net_profit = round(total_rev - total_cost, 2)
    margin_pct = round((net_profit / total_rev * 100), 1) if total_rev > 0 else 25.0
    today_profit = round(today_rev - today_cost, 2)
    
    breakdown = list(pkg_stats.values())
    breakdown.sort(key=lambda x: x["profit"], reverse=True)
    for b in breakdown:
        b["margin_pct"] = round((b["profit"] / b["revenue"] * 100), 1) if b["revenue"] > 0 else 0.0
        
    return {
        "ok": True,
        "total_revenue": round(total_rev, 2),
        "total_cost": round(total_cost, 2),
        "net_profit": net_profit,
        "margin_pct": margin_pct,
        "today_revenue": round(today_rev, 2),
        "today_cost": round(today_cost, 2),
        "today_profit": today_profit,
        "packages": breakdown
    }

@app.post("/api/admin/telegram/broadcast")
async def admin_telegram_broadcast(request: Request):
    body = await request.json() if (await request.body()) else {}
    title = body.get("title", "").strip() or "Special Promo Announcement"
    message = body.get("message", "").strip()
    button_text = body.get("button_text", "").strip() or "🔥 Shop Offers Now"
    button_url = body.get("button_url", "").strip() or "http://localhost:3000"
    
    if not message:
        return JSONResponse(status_code=400, content={"ok": False, "error": "Message content cannot be empty"})
        
    token = settings.get("telegram_bot_token") or os.environ.get("TELEGRAM_BOT_TOKEN", "")
    admin_chat = settings.get("telegram_chat_id") or "8710759437"
    
    if not token:
        return JSONResponse(status_code=400, content={"ok": False, "error": "Telegram Bot Token is not configured"})
        
    # Gather target chat IDs
    targets = set()
    if admin_chat:
        targets.add(str(admin_chat).strip())
        
    for u in users:
        c_id = u.get("telegram_chat_id")
        if c_id:
            targets.add(str(c_id).strip())
            
    # Compose Telegram HTML Broadcast
    tg_text = (
        f"📢 <b>{title}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"{message}\n\n"
        f"🎮 <b>Rolea Topup</b> — Fast & Reliable"
    )
    
    reply_markup = None
    if button_url:
        reply_markup = {
            "inline_keyboard": [
                [{"text": button_text, "url": button_url}]
            ]
        }
        
    sent_count = 0
    errors = []
    
    for cid in targets:
        try:
            await send_telegram_direct_message(token, cid, tg_text, reply_markup)
            sent_count += 1
        except Exception as e:
            errors.append(str(e))
            
    return {
        "ok": True,
        "sent_count": sent_count,
        "total_targets": len(targets),
        "errors": errors[:3]
    }

@app.post("/api/admin/telegram/test")
async def admin_telegram_test():
    token = settings.get("telegram_bot_token") or os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = settings.get("telegram_chat_id") or "8710759437"
    now_ict = datetime.now(timezone(timedelta(hours=7))).strftime("%m/%d/%Y, %I:%M:%S %p")
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(
                url,
                json={
                    "chat_id": chat_id,
                    "text": f"🔔 <b>[TEST NOTIFICATION]</b>\n✨ <b>Rolea Topup:</b> Telegram Order Alert bot is connected successfully.\n🕒 <b>Time:</b> {now_ict}",
                    "parse_mode": "HTML"
                }
            )
            j = resp.json()
            if j and j.get("ok"):
                return {"ok": True, "message": "Test message sent to Telegram!"}
            return JSONResponse(status_code=400, content={"ok": False, "error": j.get("description", "Telegram rejected message")})
    except Exception as err:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(err)})


# ==========================================
# FEATURE 1: ROBUX INVENTORY & BOT POOL SYSTEM
# ==========================================


def is_blacklisted(player_id: str = "", username: str = "", email: str = "", ip: str = "") -> tuple[bool, str]:
    global blacklist
    b_users = [str(u).lower().strip() for u in blacklist.get("blocked_users", [])]
    b_ips = [str(i).strip() for i in blacklist.get("blocked_ips", [])]
    b_emails = [str(e).lower().strip() for e in blacklist.get("blocked_emails", [])]

    if player_id and str(player_id).lower().strip() in b_users:
        return True, f"Username/Player '{player_id}' is blacklisted."
    if username and str(username).lower().strip() in b_users:
        return True, f"Username '{username}' is blacklisted."
    if email and str(email).lower().strip() in b_emails:
        return True, f"Email '{email}' is blocked from placing orders."
    if ip and str(ip).strip() in b_ips:
        return True, f"IP address ({ip}) has been blacklisted."
    return False, ""

def get_total_inventory_stock() -> int:
    global inventory
    bots = inventory.get("bots", [])
    if bots:
        return sum(int(b.get("group_funds", 0)) for b in bots)
    if inventory.get("manual_stock_enabled", False):
        return int(inventory.get("manual_stock_robux", 0))
    return 0

async def check_and_send_low_stock_alert():
    global inventory, settings
    if not inventory.get("telegram_alert_enabled", True):
        return
    current_stock = get_total_inventory_stock()
    threshold = int(inventory.get("low_stock_threshold", 5000))
    if current_stock <= threshold:
        # Rate limit alert to once every 15 minutes
        last_alert = inventory.get("last_alert_sent_at")
        now_ts = time.time()
        if last_alert and (now_ts - last_alert) < 900:
            return
        inventory["last_alert_sent_at"] = now_ts
        save_inventory()

        token = settings.get("telegram_bot_token")
        chat_id = settings.get("telegram_chat_id")
        if token and chat_id:
            msg = (
                f"🚨 <b>[ROLEA TOPUP — LOW STOCK ALERT]</b>\n\n"
                f"⚠️ <b>Robux Inventory is Running Low!</b>\n"
                f"• Current Stock: <b>{current_stock:,} Robux</b>\n"
                f"• Alert Threshold: <b>{threshold:,} Robux</b>\n\n"
                f"👉 Please replenish your Roblox Group Funds or add more Payout Bots promptly!\n"
                f"🔗 <a href='http://localhost:3000/admin'>Open Admin Inventory</a>"
            )
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            try:
                async with httpx.AsyncClient(timeout=8.0) as client:
                    await client.post(url, json={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"})
            except Exception as e:
                print("Low stock alert error:", e)

def deduct_inventory_on_deliver(order: dict):
    global inventory
    if order.get("inventory_deducted"):
        return
    game = (order.get("game") or "roblox").lower()
    if "roblox" not in game and not order.get("robux_amount"):
        return
    amount = int(float(order.get("robux_amount") or 0))
    if amount <= 0:
        return

    order["inventory_deducted"] = True
    current_stock = get_total_inventory_stock()
    new_stock = max(0, current_stock - amount)

    if inventory.get("manual_stock_enabled", True):
        inventory["manual_stock_robux"] = new_stock
    else:
        bots = inventory.get("bots", [])
        if bots:
            for b in bots:
                if int(b.get("group_funds", 0)) >= amount:
                    b["group_funds"] = int(b.get("group_funds", 0)) - amount
                    break
            else:
                bots[0]["group_funds"] = max(0, int(bots[0].get("group_funds", 0)) - amount)

    if "history" not in inventory:
        inventory["history"] = []
    
    player_id = order.get("player_id") or order.get("roblox_username") or order.get("buyer_account") or "Customer"
    history_item = {
        "id": "inv_" + str(int(time.time() * 1000)),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "type": "deduct",
        "amount": amount,
        "balance": get_total_inventory_stock(),
        "order_id": order.get("order_id", "-"),
        "note": f"Delivered {amount:,} Robux to {player_id}"
    }
    inventory["history"].insert(0, history_item)
    if len(inventory["history"]) > 100:
        inventory["history"] = inventory["history"][:100]

    save_inventory()
    save_orders()
    asyncio.create_task(check_and_send_low_stock_alert())

@app.get("/api/admin/inventory")
async def admin_get_inventory():
    global inventory
    total_stock = get_total_inventory_stock()
    threshold = int(inventory.get("low_stock_threshold", 5000))
    is_low = total_stock <= threshold
    avg_pkg_size = 400
    orders_covered = round(total_stock / avg_pkg_size) if total_stock > 0 else 0

    return {
        "ok": True,
        "total_stock": total_stock,
        "low_stock_threshold": threshold,
        "is_low_stock": is_low,
        "orders_covered": orders_covered,
        "manual_stock_enabled": bool(inventory.get("manual_stock_enabled", True)),
        "manual_stock_robux": int(inventory.get("manual_stock_robux", 0)),
        "telegram_alert_enabled": bool(inventory.get("telegram_alert_enabled", True)),
        "bots": inventory.get("bots", []),
        "history": inventory.get("history", [])[:50]
    }

@app.post("/api/admin/inventory/settings")
async def admin_inventory_settings(request: Request):
    global inventory
    body = await request.json() if (await request.body()) else {}
    if "manual_stock_enabled" in body:
        inventory["manual_stock_enabled"] = bool(body["manual_stock_enabled"])
    if "manual_stock_robux" in body:
        inventory["manual_stock_robux"] = int(float(body["manual_stock_robux"]))
    if "low_stock_threshold" in body:
        inventory["low_stock_threshold"] = int(float(body["low_stock_threshold"]))
    if "telegram_alert_enabled" in body:
        inventory["telegram_alert_enabled"] = bool(body["telegram_alert_enabled"])
    save_inventory()
    return {"ok": True, "total_stock": get_total_inventory_stock(), "settings": inventory}

@app.post("/api/admin/inventory/adjust")
async def admin_inventory_adjust(request: Request):
    global inventory
    body = await request.json() if (await request.body()) else {}
    adj_type = str(body.get("type", "restock")).lower() # restock (+) or deduct (-)
    amount = int(float(body.get("amount", 0)))
    note = str(body.get("note", "")).strip() or ("Stock Adjustment" if adj_type == "restock" else "Manual Deduction")

    if amount <= 0:
        return JSONResponse(status_code=400, content={"ok": False, "error": "Amount must be greater than 0"})

    current_stock = get_total_inventory_stock()
    if adj_type == "restock":
        new_stock = current_stock + amount
    else:
        new_stock = max(0, current_stock - amount)

    if inventory.get("manual_stock_enabled", True):
        inventory["manual_stock_robux"] = new_stock
    else:
        bots = inventory.get("bots", [])
        if bots:
            if adj_type == "restock":
                bots[0]["group_funds"] = int(bots[0].get("group_funds", 0)) + amount
            else:
                bots[0]["group_funds"] = max(0, int(bots[0].get("group_funds", 0)) - amount)
        else:
            inventory["manual_stock_robux"] = new_stock

    if "history" not in inventory:
        inventory["history"] = []
    
    history_item = {
        "id": "inv_" + str(int(time.time() * 1000)),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "type": adj_type,
        "amount": amount,
        "balance": get_total_inventory_stock(),
        "order_id": "-",
        "note": note
    }
    inventory["history"].insert(0, history_item)
    if len(inventory["history"]) > 100:
        inventory["history"] = inventory["history"][:100]

    save_inventory()
    return {"ok": True, "total_stock": get_total_inventory_stock(), "history_item": history_item}

@app.post("/api/admin/inventory/bot/add")
async def admin_inventory_add_bot(request: Request):
    global inventory
    body = await request.json() if (await request.body()) else {}
    name = str(body.get("name", "")).strip() or "Payout Bot"
    group_id = str(body.get("group_id", "")).strip()
    cookie = str(body.get("cookie", "")).strip()
    initial_funds = int(float(body.get("group_funds", 0)))
    notes = str(body.get("notes", "")).strip()

    if not group_id and not cookie and initial_funds <= 0:
        return JSONResponse(status_code=400, content={"ok": False, "error": "Please enter a Group ID, Cookie, or initial funds balance"})

    bot_id = "bot_" + str(int(time.time() * 1000))
    group_name = f"Group #{group_id}" if group_id else "Roblox Payout Group"

    # Attempt public Roblox group info lookup if group_id provided
    if group_id:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(f"https://groups.roblox.com/v1/groups/{group_id}")
                if r.status_code == 200:
                    g_json = r.json()
                    group_name = g_json.get("name", group_name)
        except Exception:
            pass

    # If cookie is provided, test cookie and group currency
    funds_found = initial_funds
    status_bot = "active"
    if cookie and group_id:
        try:
            clean_c = cookie if cookie.startswith(".ROBLOSECURITY=") else f".ROBLOSECURITY={cookie}"
            async with httpx.AsyncClient(timeout=6.0) as client:
                r_c = await client.get(
                    f"https://economy.roblox.com/v1/groups/{group_id}/currency",
                    headers={"Cookie": clean_c}
                )
                if r_c.status_code == 200:
                    funds_found = int(r_c.json().get("robux", funds_found))
                    status_bot = "active"
                elif r_c.status_code == 401:
                    status_bot = "error"
        except Exception:
            pass

    new_bot = {
        "id": bot_id,
        "name": name,
        "group_id": group_id,
        "group_name": group_name,
        "cookie": cookie,
        "group_funds": funds_found,
        "status": status_bot,
        "last_synced": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "notes": notes
    }

    if "bots" not in inventory:
        inventory["bots"] = []
    inventory["bots"].append(new_bot)
    save_inventory()

    return {"ok": True, "bot": new_bot, "total_stock": get_total_inventory_stock()}

@app.post("/api/admin/inventory/bot/sync")
async def admin_inventory_sync_bot(request: Request):
    global inventory
    body = await request.json() if (await request.body()) else {}
    bot_id = body.get("bot_id")
    bots = inventory.get("bots", [])

    synced_count = 0
    errors = []

    for b in bots:
        if bot_id and b.get("id") != bot_id:
            continue
        g_id = b.get("group_id")
        cookie = b.get("cookie")
        b["last_synced"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        if cookie and g_id:
            try:
                clean_c = cookie if cookie.startswith(".ROBLOSECURITY=") else f".ROBLOSECURITY={cookie}"
                async with httpx.AsyncClient(timeout=6.0) as client:
                    r_c = await client.get(
                        f"https://economy.roblox.com/v1/groups/{g_id}/currency",
                        headers={"Cookie": clean_c}
                    )
                    if r_c.status_code == 200:
                        b["group_funds"] = int(r_c.json().get("robux", b.get("group_funds", 0)))
                        b["status"] = "active"
                        synced_count += 1
                    else:
                        b["status"] = "error"
                        errors.append(f"Bot {b.get('name')}: HTTP {r_c.status_code}")
            except Exception as e:
                b["status"] = "warning"
                errors.append(f"Bot {b.get('name')}: {e}")
        else:
            b["status"] = "active"
            synced_count += 1

    save_inventory()
    return {
        "ok": True,
        "synced_count": synced_count,
        "errors": errors,
        "total_stock": get_total_inventory_stock(),
        "bots": bots
    }

@app.post("/api/admin/inventory/bot/delete")
async def admin_inventory_delete_bot(request: Request):
    global inventory
    body = await request.json() if (await request.body()) else {}
    bot_id = body.get("bot_id")
    if not bot_id:
        return JSONResponse(status_code=400, content={"ok": False, "error": "Bot ID is required"})

    inventory["bots"] = [b for b in inventory.get("bots", []) if b.get("id") != bot_id]
    save_inventory()
    return {"ok": True, "total_stock": get_total_inventory_stock()}



@app.post("/api/admin/inventory/cookie/save")
async def admin_inventory_cookie_save(request: Request):
    global inventory
    body = await request.json() if (await request.body()) else {}
    cookie = str(body.get("cookie", "")).strip()
    group_id = str(body.get("group_id", "")).strip()
    name = str(body.get("name", "")).strip() or "Payout Bot"

    if not cookie:
        return JSONResponse(status_code=400, content={"ok": False, "error": "Please enter your Roblox .ROBLOSECURITY cookie"})

    # Clean cookie prefix
    clean_c = cookie
    if clean_c.startswith(".ROBLOSECURITY="):
        clean_c = clean_c[len(".ROBLOSECURITY="):].strip()
    header_cookie = f".ROBLOSECURITY={clean_c}"

    # Verify cookie with Roblox
    try:
        async with httpx.AsyncClient(timeout=9.0) as client:
            r_auth = await client.get(
                "https://users.roblox.com/v1/users/authenticated",
                headers={"Cookie": header_cookie, "User-Agent": "Mozilla/5.0"}
            )
            if r_auth.status_code != 200:
                return JSONResponse(status_code=400, content={
                    "ok": False,
                    "error": f"Roblox Cookie verification failed (HTTP {r_auth.status_code}). Cookie is invalid or expired."
                })
            user_data = r_auth.json()
            roblox_user_id = user_data.get("id")
            roblox_username = user_data.get("name")
            display_name = user_data.get("displayName")
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": f"Failed to reach Roblox API: {e}"})

    # Fetch Avatar
    avatar_url = "/media/rolea-logo.webp"
    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            r_thumb = await client.get(
                f"https://thumbnails.roblox.com/v1/users/avatar-headshot?userIds={roblox_user_id}&size=150x150&format=Png&isCircular=true"
            )
            if r_thumb.status_code == 200:
                t_arr = r_thumb.json().get("data", [])
                if t_arr and t_arr[0].get("imageUrl"):
                    avatar_url = t_arr[0]["imageUrl"]
    except Exception:
        pass

    # Fetch Real Funds (Group or Personal)
    funds = 0
    group_name = ""
    if group_id:
        group_name = f"Group #{group_id}"
        try:
            async with httpx.AsyncClient(timeout=7.0) as client:
                rg = await client.get(f"https://groups.roblox.com/v1/groups/{group_id}")
                if rg.status_code == 200:
                    group_name = rg.json().get("name", group_name)
                rc = await client.get(
                    f"https://economy.roblox.com/v1/groups/{group_id}/currency",
                    headers={"Cookie": header_cookie, "User-Agent": "Mozilla/5.0"}
                )
                if rc.status_code == 200:
                    funds = int(rc.json().get("robux", 0))
        except Exception:
            pass
    else:
        try:
            async with httpx.AsyncClient(timeout=7.0) as client:
                rc = await client.get(
                    f"https://economy.roblox.com/v1/users/{roblox_user_id}/currency",
                    headers={"Cookie": header_cookie, "User-Agent": "Mozilla/5.0"}
                )
                if rc.status_code == 200:
                    funds = int(rc.json().get("robux", 0))
        except Exception:
            pass

    bot_item = {
        "id": "bot_primary",
        "name": name,
        "roblox_user_id": roblox_user_id,
        "roblox_username": roblox_username,
        "display_name": display_name,
        "avatar_url": avatar_url,
        "group_id": group_id,
        "group_name": group_name,
        "cookie": clean_c,
        "group_funds": funds,
        "status": "active",
        "last_synced": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    inventory["bots"] = [bot_item]
    inventory["manual_stock_enabled"] = False
    save_inventory()

    return {"ok": True, "bot": bot_item, "total_stock": funds}

async def sync_primary_bot_balance() -> Dict[str, Any]:
    global inventory
    bots = inventory.get("bots", [])
    if not bots:
        return {"ok": False, "status_code": 400, "error": "No bot cookie configured to sync"}

    b = bots[0]
    cookie = b.get("cookie", "")
    group_id = b.get("group_id", "")
    if not cookie:
        return {"ok": False, "status_code": 400, "error": "Empty bot cookie"}
    header_cookie = f".ROBLOSECURITY={cookie}" if not cookie.startswith(".ROBLOSECURITY=") else cookie

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r_auth = await client.get(
                "https://users.roblox.com/v1/users/authenticated",
                headers={"Cookie": header_cookie, "User-Agent": "Mozilla/5.0"}
            )
            if r_auth.status_code != 200:
                b["status"] = "error"
                save_inventory()
                return {"ok": False, "status_code": 400, "error": "Cookie expired or invalid"}

            user_data = r_auth.json()
            b["roblox_username"] = user_data.get("name", b.get("roblox_username"))
            b["roblox_user_id"] = user_data.get("id", b.get("roblox_user_id"))
            b["status"] = "active"

            if group_id:
                rc = await client.get(
                    f"https://economy.roblox.com/v1/groups/{group_id}/currency",
                    headers={"Cookie": header_cookie, "User-Agent": "Mozilla/5.0"}
                )
                if rc.status_code == 200:
                    b["group_funds"] = int(rc.json().get("robux", 0))
            else:
                rc = await client.get(
                    f"https://economy.roblox.com/v1/users/{b.get('roblox_user_id')}/currency",
                    headers={"Cookie": header_cookie, "User-Agent": "Mozilla/5.0"}
                )
                if rc.status_code == 200:
                    b["group_funds"] = int(rc.json().get("robux", 0))

            b["last_synced"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            save_inventory()
            asyncio.create_task(check_and_send_low_stock_alert())
            return {"ok": True, "bot": b, "total_stock": b["group_funds"]}
    except Exception as e:
        return {"ok": False, "status_code": 500, "error": f"Sync failed: {e}"}

async def robux_balance_auto_sync_loop():
    await asyncio.sleep(3)
    while True:
        try:
            bots = inventory.get("bots", [])
            if bots and bots[0].get("cookie"):
                await sync_primary_bot_balance()
        except Exception as e:
            print(f"[Robux AutoSync] Error: {e}")
        await asyncio.sleep(15)

@app.post("/api/admin/inventory/cookie/sync")
async def admin_inventory_cookie_sync():
    res = await sync_primary_bot_balance()
    if not res.get("ok"):
        return JSONResponse(status_code=res.get("status_code", 400), content={"ok": False, "error": res.get("error", "Sync failed")})
    return {"ok": True, "bot": res["bot"], "total_stock": res["total_stock"]}

@app.post("/api/admin/inventory/cookie/delete")
async def admin_inventory_cookie_delete():
    global inventory
    inventory["bots"] = []
    inventory["manual_stock_enabled"] = False
    inventory["manual_stock_robux"] = 0
    save_inventory()
    return {"ok": True, "total_stock": 0}


# ==========================================
# FRAUD PREVENTION & BLACKLIST APIS
# ==========================================
@app.get("/api/admin/blacklist")
async def admin_get_blacklist():
    global blacklist
    total_blocked = len(blacklist.get("blocked_users", [])) + len(blacklist.get("blocked_ips", [])) + len(blacklist.get("blocked_emails", []))
    return {
        "ok": True,
        "blacklist": blacklist,
        "total_blocked": total_blocked,
        "blocked_users": blacklist.get("blocked_users", []),
        "blocked_ips": blacklist.get("blocked_ips", []),
        "blocked_emails": blacklist.get("blocked_emails", []),
        "rules": blacklist.get("rules", {}),
        "logs": blacklist.get("logs", [])[:50]
    }

@app.post("/api/admin/blacklist/add")
async def admin_add_blacklist(request: Request):
    global blacklist
    body = await request.json() if (await request.body()) else {}
    target = str(body.get("target", "")).strip()
    btype = str(body.get("type", "username")).lower().strip() # username, ip, email
    reason = str(body.get("reason", "")).strip() or "Suspected fraudulent activity"

    if not target:
        return JSONResponse(status_code=400, content={"ok": False, "error": "Target to block is required"})

    key = "blocked_users" if btype == "username" else ("blocked_ips" if btype == "ip" else "blocked_emails")
    if key not in blacklist:
        blacklist[key] = []

    clean_target = target.lower() if btype in ["username", "email"] else target
    if clean_target not in blacklist[key]:
        blacklist[key].append(clean_target)

    log_item = {
        "id": "blk_" + str(int(time.time() * 1000)),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "target": target,
        "type": btype,
        "reason": reason,
        "blocked_by": "Admin"
    }
    if "logs" not in blacklist:
        blacklist["logs"] = []
    blacklist["logs"].insert(0, log_item)
    if len(blacklist["logs"]) > 100:
        blacklist["logs"] = blacklist["logs"][:100]

    save_blacklist()
    return {"ok": True, "message": f"{target} added to {btype} blacklist", "blacklist": blacklist}

@app.post("/api/admin/blacklist/remove")
async def admin_remove_blacklist(request: Request):
    global blacklist
    body = await request.json() if (await request.body()) else {}
    target = str(body.get("target", "")).strip()
    btype = str(body.get("type", "username")).lower().strip()

    if not target:
        return JSONResponse(status_code=400, content={"ok": False, "error": "Target is required"})

    key = "blocked_users" if btype == "username" else ("blocked_ips" if btype == "ip" else "blocked_emails")
    clean_target = target.lower() if btype in ["username", "email"] else target

    if key in blacklist and clean_target in blacklist[key]:
        blacklist[key].remove(clean_target)

    save_blacklist()
    return {"ok": True, "message": f"{target} removed from blacklist", "blacklist": blacklist}

@app.post("/api/admin/blacklist/rules")
async def admin_update_blacklist_rules(request: Request):
    global blacklist
    body = await request.json() if (await request.body()) else {}
    if "rules" not in blacklist:
        blacklist["rules"] = {}
    for k in ["block_duplicate_unpaid_orders", "auto_flag_suspicious"]:
        if k in body:
            blacklist["rules"][k] = bool(body[k])
    if "max_unpaid_orders_per_ip" in body:
        blacklist["rules"]["max_unpaid_orders_per_ip"] = int(body["max_unpaid_orders_per_ip"])

    save_blacklist()
    return {"ok": True, "rules": blacklist["rules"]}

# ==========================================
# TOGGLE PACKAGE STOCK API (IN STOCK / OUT OF STOCK)
# ==========================================
@app.post("/api/admin/packages/toggle-stock")
async def admin_toggle_package_stock(request: Request):
    global packages
    body = await request.json() if (await request.body()) else {}
    pid = body.get("id")
    pkg = next((p for p in packages if p.get("id") == pid), None)
    if not pkg:
        return JSONResponse(status_code=404, content={"ok": False, "error": "Package not found"})

    current_stock = bool(pkg.get("in_stock", True))
    pkg["in_stock"] = not current_stock
    save_packages()
    return {"ok": True, "package": pkg, "in_stock": pkg["in_stock"]}

# ==========================================
# EXPORT ORDERS CSV (EXCEL COMPATIBLE WITH UTF-8 BOM)
# ==========================================
@app.get("/api/admin/orders/export-csv")
async def admin_export_orders_csv(date_filter: Optional[str] = "all"):
    global orders
    items = [
        o for o in orders
        if o.get("type") != "wallet_topup" and not str(o.get("order_id", "")).startswith("WLT")
    ]

    now_date = datetime.now().strftime("%Y-%m-%d")
    now_month = datetime.now().strftime("%Y-%m")

    if date_filter == "today":
        items = [o for o in items if now_date in str(o.get("created_at") or o.get("date") or "")]
    elif date_filter == "month":
        items = [o for o in items if now_month in str(o.get("created_at") or o.get("date") or "")]

    import io, csv
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Order ID", "Date & Time", "Customer / Player", "Game", "Package",
        "Units / Robux", "Amount ($ USD)", "Payment Method", "Status", "Delivery Step"
    ])

    for o in items:
        writer.writerow([
            o.get("order_id", ""),
            o.get("created_at") or o.get("date") or "",
            o.get("player_id") or o.get("roblox_username") or o.get("buyer_account") or "",
            o.get("product_name") or o.get("game") or "Roblox",
            o.get("package") or "",
            o.get("robux_amount") or 0,
            f"{float(o.get('amount') or 0):.2f}",
            o.get("payment_method") or "KHQR",
            o.get("status") or "pending",
            o.get("step") or ""
        ])

    csv_data = "﻿" + output.getvalue()
    filename = f"Rolea_Topup_Orders_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    return Response(
        content=csv_data.encode("utf-8"),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.post("/api/admin/upload-banner")
async def admin_upload_banner(request: Request):
    body = await request.json() if (await request.body()) else {}
    btype = body.get("type")
    game_id = body.get("game_id")
    image_base64 = body.get("image_base64")
    image_url = body.get("image_url")
    target_game = game_id or (btype if btype and btype != "home" else None)

    # Home banner
    if not target_game or btype == "home":
        if image_url:
            settings["home_banner"] = str(image_url).strip()
            save_settings()
            return {"ok": True, "banner_url": settings["home_banner"], "type": "home"}
        if image_base64:
            try:
                m = re.match(r"^data:image/([a-zA-Z0-9+]+);base64,(.+)$", image_base64)
                ext = "webp"
                data = image_base64
                if m:
                    ext = "jpg" if m.group(1) == "jpeg" else ("png" if m.group(1) == "png" else "webp")
                    data = m.group(2)
                buf = base64.b64decode(data)
                filename = f"banner_home_{int(time.time() * 1000)}.{ext}"
                with open(MEDIA_DIR / filename, "wb") as f:
                    f.write(buf)
                saved_url = f"/media/{filename}"
                settings["home_banner"] = saved_url
                save_settings()
                return {"ok": True, "banner_url": saved_url, "type": "home"}
            except Exception as err:
                return JSONResponse(status_code=500, content={"ok": False, "error": "Failed to save banner image"})
        return JSONResponse(status_code=400, content={"ok": False, "error": "No image data or URL provided"})

    # Game banner
    if target_game not in games:
        return JSONResponse(status_code=404, content={"ok": False, "error": f"Game {target_game} not found"})

    if image_url:
        games[target_game]["banner"] = str(image_url).strip()
        save_games()
        if target_game == "roblox":
            settings["roblox_banner"] = games[target_game]["banner"]
            save_settings()
        return {"ok": True, "banner_url": games[target_game]["banner"], "game_id": target_game}

    if image_base64:
        try:
            m = re.match(r"^data:image/([a-zA-Z0-9+]+);base64,(.+)$", image_base64)
            ext = "webp"
            data = image_base64
            if m:
                ext = "jpg" if m.group(1) == "jpeg" else ("png" if m.group(1) == "png" else "webp")
                data = m.group(2)
            buf = base64.b64decode(data)
            filename = f"banner_{target_game}_{int(time.time() * 1000)}.{ext}"
            with open(MEDIA_DIR / filename, "wb") as f:
                f.write(buf)
            saved_url = f"/media/{filename}"
            games[target_game]["banner"] = saved_url
            save_games()
            if target_game == "roblox":
                settings["roblox_banner"] = saved_url
                save_settings()
            return {"ok": True, "banner_url": saved_url, "game_id": target_game}
        except Exception as err:
            return JSONResponse(status_code=500, content={"ok": False, "error": "Failed to save banner image"})

    return JSONResponse(status_code=400, content={"ok": False, "error": "No image data or URL provided"})

# Promos Admin
@app.get("/api/admin/promos")
async def admin_get_promos():
    return {"ok": True, "promos": coupons}

@app.post("/api/admin/promos/add")
async def admin_add_promo(request: Request):
    body = await request.json() if (await request.body()) else {}
    code = body.get("code")
    if not code or not isinstance(code, str):
        return JSONResponse(status_code=400, content={"ok": False, "error": "Promo code is required"})

    clean_code = code.strip().upper()
    if any(c.get("code", "").upper() == clean_code for c in coupons):
        return JSONResponse(status_code=400, content={"ok": False, "error": "Promo code already exists"})

    try:
        val = float(body.get("value", 0))
    except Exception:
        val = 0.0

    if val <= 0:
        return JSONResponse(status_code=400, content={"ok": False, "error": "Discount value must be greater than 0"})

    ptype = "fixed" if body.get("type") == "fixed" else "percentage"
    new_promo = {
        "id": "cpn_" + secrets.token_hex(4),
        "code": clean_code,
        "type": ptype,
        "value": val,
        "min_spend": float(body.get("min_spend", 0) or 0),
        "max_uses": int(body.get("max_uses", 0) or 0),
        "used_count": 0,
        "enabled": True,
        "description": (body.get("description") or f"{val}{'$' if ptype == 'fixed' else '%'} Discount").strip()
    }
    coupons.insert(0, new_promo)
    save_coupons()
    return {"ok": True, "promo": new_promo}

@app.post("/api/admin/promos/toggle")
async def admin_toggle_promo(request: Request):
    body = await request.json() if (await request.body()) else {}
    pid = body.get("id")
    cp = next((c for c in coupons if c.get("id") == pid or c.get("code") == pid), None)
    if not cp:
        return JSONResponse(status_code=404, content={"ok": False, "error": "Promo code not found"})
    cp["enabled"] = not cp.get("enabled", True)
    save_coupons()
    return {"ok": True, "promo": cp}

@app.post("/api/admin/promos/delete")
async def admin_delete_promo(request: Request):
    body = await request.json() if (await request.body()) else {}
    pid = body.get("id")
    idx = next((i for i, c in enumerate(coupons) if c.get("id") == pid or c.get("code") == pid), -1)
    if idx == -1:
        return JSONResponse(status_code=404, content={"ok": False, "error": "Promo code not found"})
    deleted = coupons.pop(idx)
    save_coupons()
    return {"ok": True, "message": f"Promo code {deleted.get('code')} deleted"}

# Reviews Admin
@app.get("/api/admin/reviews")
async def admin_get_reviews():
    return {"ok": True, "reviews": reviews}

@app.post("/api/admin/reviews/toggle")
async def admin_toggle_review(request: Request):
    body = await request.json() if (await request.body()) else {}
    rid = body.get("id")
    r = next((item for item in reviews if item.get("id") == rid), None)
    if not r:
        return JSONResponse(status_code=404, content={"ok": False, "error": "Review not found"})
    r["approved"] = not r.get("approved", True)
    save_reviews()
    return {"ok": True, "review": r}

@app.post("/api/admin/reviews/delete")
async def admin_delete_review(request: Request):
    body = await request.json() if (await request.body()) else {}
    rid = body.get("id")
    idx = next((i for i, item in enumerate(reviews) if item.get("id") == rid), -1)
    if idx == -1:
        return JSONResponse(status_code=404, content={"ok": False, "error": "Review not found"})
    reviews.pop(idx)
    save_reviews()
    return {"ok": True, "message": "Review deleted"}

@app.post("/api/admin/reviews/add")
async def admin_add_review(request: Request):
    body = await request.json() if (await request.body()) else {}
    comment = body.get("comment", "")
    if not comment or not isinstance(comment, str):
        return JSONResponse(status_code=400, content={"ok": False, "error": "Comment required"})

    game_key = body.get("game", "roblox")
    g = games.get(game_key, {})
    try:
        rating = max(1, min(5, int(body.get("rating", 5))))
    except Exception:
        rating = 5

    new_rev = {
        "id": "rev_" + secrets.token_hex(4),
        "order_id": "ADMIN_" + secrets.token_hex(4).upper(),
        "game": game_key,
        "game_name": g.get("name") or "Rolea Topup",
        "username": (body.get("username") or "Verified Buyer").strip(),
        "rating": rating,
        "comment": comment.strip(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "approved": True
    }
    reviews.insert(0, new_rev)
    save_reviews()
    return {"ok": True, "review": new_rev}

# Users & Wallets Admin
@app.get("/api/admin/users")
async def admin_get_users():
    safe_users = [
        {
            "id": u.get("id"),
            "username": u.get("username"),
            "email": u.get("email"),
            "balance": u.get("balance", 0.0),
            "created_at": u.get("created_at"),
            "total_orders": len([o for o in orders if o.get("user_id") == u.get("id")])
        }
        for u in users
    ]
    return {"ok": True, "users": safe_users}

@app.post("/api/admin/users/edit")
async def admin_edit_user(request: Request):
    body = await request.json() if (await request.body()) else {}
    user_id = body.get("user_id")
    user = next((u for u in users if u.get("id") == user_id or u.get("username") == user_id), None)
    if not user:
        return JSONResponse(status_code=404, content={"ok": False, "error": "User not found"})

    username = body.get("username")
    if username and isinstance(username, str) and len(username.strip()) >= 3:
        clean_uname = username.strip()
        conflict = next((u for u in users if u.get("id") != user.get("id") and u.get("username", "").lower() == clean_uname.lower()), None)
        if conflict:
            return JSONResponse(status_code=400, content={"ok": False, "error": "Username already taken by another account"})
        user["username"] = clean_uname

    if "email" in body:
        user["email"] = (body.get("email") or "").strip().lower()

    password = body.get("password")
    if password and isinstance(password, str) and len(password.strip()) >= 6:
        user["password_hash"] = hash_password(password.strip())

    save_users()
    return {
        "ok": True,
        "message": f"Account {user['username']} updated successfully",
        "user": {
            "id": user.get("id"),
            "username": user.get("username"),
            "email": user.get("email"),
            "balance": user.get("balance")
        }
    }

@app.post("/api/admin/users/delete")
async def admin_delete_user(request: Request):
    body = await request.json() if (await request.body()) else {}
    user_id = body.get("user_id")
    idx = next((i for i, u in enumerate(users) if u.get("id") == user_id or u.get("username") == user_id), -1)
    if idx == -1:
        return JSONResponse(status_code=404, content={"ok": False, "error": "User not found"})
    deleted = users.pop(idx)
    save_users()
    return {"ok": True, "message": f"Account {deleted.get('username')} deleted"}

@app.post("/api/admin/users/adjust-balance")
async def admin_adjust_balance(request: Request):
    body = await request.json() if (await request.body()) else {}
    user_id = body.get("user_id")
    action = body.get("action")
    amount = body.get("amount")
    reason = body.get("reason", "")

    user = next((u for u in users if u.get("id") == user_id or u.get("username") == user_id), None)
    if not user:
        return JSONResponse(status_code=404, content={"ok": False, "error": "User not found"})

    try:
        num = abs(float(amount))
    except (ValueError, TypeError):
        return JSONResponse(status_code=400, content={"ok": False, "error": "Invalid amount"})

    if action == "deduct":
        num = -num

    current_bal = float(user.get("balance", 0.0))
    user["balance"] = max(0.0, round(current_bal + num, 2))
    save_users()

    wallet_transactions.insert(0, {
        "id": "wtx_" + secrets.token_hex(4),
        "user_id": user["id"],
        "type": "admin_credit" if num >= 0 else "admin_debit",
        "amount": num,
        "order_id": "ADMIN",
        "product": reason or ("Admin Deposit" if num >= 0 else "Admin Deduction"),
        "date": datetime.now(timezone.utc).isoformat()
    })
    save_wallet_tx()

    return {"ok": True, "message": f"Balance updated for {user.get('username')}", "balance": user["balance"]}

# ==========================================
# PAGE WEB ROUTES
# ==========================================

@app.get("/")
async def page_index():
    return FileResponse(PUBLIC_DIR / "index.html")

@app.get("/games")
async def page_games():
    return FileResponse(PUBLIC_DIR / "index.html")

@app.get("/game/{game_name}")
async def page_game(game_name: str):
    return FileResponse(PUBLIC_DIR / "roblox.html")

@app.get("/spin")
async def page_spin():
    return FileResponse(PUBLIC_DIR / "spin.html")

@app.get("/check-order")
async def page_check_order():
    return FileResponse(PUBLIC_DIR / "check_order.html")

@app.get("/my-account")
@app.get("/profile")
async def page_my_account():
    return FileResponse(PUBLIC_DIR / "my_account.html")

@app.get("/api/auth/google/callback")
async def google_oauth_callback(code: str = "", error: str = ""):
    html = """<!DOCTYPE html>
<html>
<head><title>Google Authenticated</title></head>
<body style="font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;background:#f8fafc">
  <div style="text-align:center;background:#fff;padding:30px;border-radius:16px;box-shadow:0 4px 20px rgba(0,0,0,0.08)">
    <h3>Redirecting to your account...</h3>
  </div>
  <script>
    if (window.opener) {
      window.opener.postMessage({ type: 'GOOGLE_AUTH_CALLBACK' }, '*');
      window.close();
    } else {
      window.location.replace('/my-account');
    }
  </script>
</body>
</html>"""
    return HTMLResponse(content=html)

@app.get("/signin")
@app.get("/login")
@app.get("/register")
async def page_signin():
    return FileResponse(PUBLIC_DIR / "signin.html")

@app.get("/order/success/{order_id}")
async def page_receipt(order_id: str):
    return FileResponse(PUBLIC_DIR / "receipt.html")

@app.get("/admin")
async def page_admin():
    return FileResponse(
        PUBLIC_DIR / "admin.html",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )

@app.get("/admin/login")
async def page_admin_login():
    return FileResponse(PUBLIC_DIR / "admin_login.html")

# Mount public directory for CSS, JS, Media, SVGs
app.mount("/", StaticFiles(directory=str(PUBLIC_DIR)), name="public")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("SERVER_PORT") or os.environ.get("PORT") or os.environ.get("APP_PORT") or 3000)
    print(f"===============================================")
    print(f"ROLEA TOPUP FastAPI Server running at:")
    print(f"- http://localhost:{port}")
    print(f"- http://localhost:{port}/game/roblox")
    print(f"- http://localhost:{port}/check-order")
    print(f"- http://localhost:{port}/admin (Admin Console Protected)")
    print(f"===============================================")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False, proxy_headers=True, forwarded_allow_ips="*")
