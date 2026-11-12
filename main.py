import asyncio
import base64
import hashlib
import hmac
import html
import io
import ipaddress
import json
import math
import os
import re
import secrets
import smtplib
import ssl
import struct
import threading
import time
from urllib.parse import urlparse, unquote, quote_plus
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

try:
    import pymysql
except ImportError:
    pymysql = None

_mysql_lock = threading.Lock()
_mysql_conn = None
_mysql_ready = False

def _get_mysql_cfg() -> Optional[Dict[str, Any]]:
    raw_url = (os.environ.get("MYSQL_URL") or os.environ.get("DATABASE_URL") or "").strip()
    if raw_url:
        if raw_url.startswith("jdbc:"):
            raw_url = raw_url[5:]
        u = urlparse(raw_url)
        if u.hostname and u.username:
            return {
                "host": u.hostname,
                "port": u.port or 3306,
                "user": unquote(u.username),
                "password": unquote(u.password or ""),
                "database": (u.path or "/").lstrip("/") or "rolea_topup",
            }
    host = os.environ.get("MYSQL_HOST", "").strip()
    user = os.environ.get("MYSQL_USER", "").strip()
    db = os.environ.get("MYSQL_DATABASE", "").strip()
    if host and user and db:
        return {
            "host": host,
            "port": int(os.environ.get("MYSQL_PORT") or 3306),
            "user": user,
            "password": os.environ.get("MYSQL_PASSWORD", ""),
            "database": db,
        }
    return None

def _mysql_connect():
    global _mysql_conn, _mysql_ready
    if pymysql is None:
        return None
    cfg = _get_mysql_cfg()
    if not cfg:
        return None
    if _mysql_conn is not None:
        try:
            _mysql_conn.ping(reconnect=True)
            return _mysql_conn
        except Exception:
            _mysql_conn = None
    _mysql_conn = pymysql.connect(
        host=cfg["host"],
        port=cfg["port"],
        user=cfg["user"],
        password=cfg["password"],
        database=cfg["database"],
        charset="utf8mb4",
        autocommit=True,
        connect_timeout=6,
        read_timeout=10,
        write_timeout=10,
    )
    if not _mysql_ready:
        with _mysql_conn.cursor() as cur:
            cur.execute(
                "CREATE TABLE IF NOT EXISTS rolea_store ("
                "store_key VARCHAR(64) PRIMARY KEY, "
                "payload LONGTEXT NOT NULL, "
                "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
                ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci"
            )
        _mysql_ready = True
        print(f"[MySQL] Connected & initialized rolea_store on {cfg['host']}/{cfg['database']}")
    return _mysql_conn

def _mysql_get(store_key: str) -> Optional[Any]:
    if not _get_mysql_cfg() or pymysql is None:
        return None
    with _mysql_lock:
        try:
            conn = _mysql_connect()
            if not conn:
                return None
            with conn.cursor() as cur:
                cur.execute("SELECT payload FROM rolea_store WHERE store_key = %s", (store_key,))
                row = cur.fetchone()
                if row and row[0]:
                    return json.loads(row[0])
        except Exception as e:
            print(f"[MySQL] Read failed ({store_key}): {e}")
    return None

def _mysql_set(store_key: str, data: Any):
    if not _get_mysql_cfg() or pymysql is None:
        return
    with _mysql_lock:
        try:
            conn = _mysql_connect()
            if not conn:
                return
            payload_str = json.dumps(data, ensure_ascii=False)
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO rolea_store (store_key, payload) VALUES (%s, %s) "
                    "ON DUPLICATE KEY UPDATE payload = VALUES(payload)",
                    (store_key, payload_str),
                )
        except Exception as e:
            print(f"[MySQL] Write failed ({store_key}): {e}")


# ==========================================
# REDIS CACHE-ASIDE LAYER (WITH MEMORY FALLBACK)
# ==========================================
try:
    import redis as redis_lib
except ImportError:
    redis_lib = None

_cache_lock = threading.Lock()
_redis_client = None
_redis_retry_after = 0.0
_mem_cache: Dict[str, tuple[float, str]] = {}
_MEM_CACHE_MAX = 1024
_cache_stats: Dict[str, Any] = {
    "hits": 0,
    "misses": 0,
    "writes": 0,
    "invalidations": 0,
    "errors": 0,
    "last_error": "",
}

_STORE_CACHE_INVALIDATION_MAP: Dict[str, tuple[str, ...]] = {
    "settings": ("rolea:settings:public",),
    "games": ("rolea:games:all", "rolea:game:*", "rolea:live_proof"),
    "packages": ("rolea:packages:*", "rolea:game:*"),
    "reviews": ("rolea:reviews:approved",),
    "orders": ("rolea:live_proof",),
    "spin": ("rolea:spin:config",),
}


def _get_redis_url() -> str:
    url = (os.environ.get("REDIS_URL") or "").strip()
    if url:
        return url
    host = (os.environ.get("REDIS_HOST") or "").strip()
    if not host:
        return ""
    port = (os.environ.get("REDIS_PORT") or "6379").strip()
    db = (os.environ.get("REDIS_DB") or "0").strip()
    pwd = (os.environ.get("REDIS_PASSWORD") or "").strip()
    user = (os.environ.get("REDIS_USER") or "default").strip()
    if pwd:
        return f"redis://{quote_plus(user)}:{quote_plus(pwd)}@{host}:{port}/{db}"
    return f"redis://{host}:{port}/{db}"


def _get_redis():
    global _redis_client, _redis_retry_after
    if _redis_client is not None:
        return _redis_client
    if redis_lib is None:
        return None
    url = _get_redis_url()
    if not url:
        return None
    now = time.time()
    if now < _redis_retry_after:
        return None
    try:
        client = redis_lib.Redis.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=1.5,
            socket_timeout=1.5,
        )
        client.ping()
        _redis_client = client
        print(f"[Redis] Connected cache-aside store")
        return _redis_client
    except Exception as e:
        _redis_client = None
        _redis_retry_after = now + 30.0
        _cache_stats["errors"] += 1
        _cache_stats["last_error"] = str(e)
        return None


def cache_backend_name() -> str:
    return "redis" if _get_redis() is not None else "memory-fallback"


def cache_get(key: str) -> Optional[Any]:
    r = _get_redis()
    if r is not None:
        try:
            raw = r.get(key)
            if raw is not None:
                _cache_stats["hits"] += 1
                return json.loads(raw)
            _cache_stats["misses"] += 1
            return None
        except Exception as e:
            global _redis_client, _redis_retry_after
            _redis_client = None
            _redis_retry_after = time.time() + 30.0
            _cache_stats["errors"] += 1
            _cache_stats["last_error"] = str(e)

    with _cache_lock:
        entry = _mem_cache.get(key)
        if entry is not None:
            exp, raw = entry
            if time.time() < exp:
                _cache_stats["hits"] += 1
                return json.loads(raw)
            _mem_cache.pop(key, None)
        _cache_stats["misses"] += 1
    return None


def cache_set(key: str, value: Any, ttl_seconds: int = 300):
    if ttl_seconds <= 0:
        return
    try:
        raw = json.dumps(value, ensure_ascii=False)
    except Exception:
        return

    r = _get_redis()
    if r is not None:
        try:
            r.setex(key, int(ttl_seconds), raw)
            _cache_stats["writes"] += 1
            return
        except Exception as e:
            global _redis_client, _redis_retry_after
            _redis_client = None
            _redis_retry_after = time.time() + 30.0
            _cache_stats["errors"] += 1
            _cache_stats["last_error"] = str(e)

    with _cache_lock:
        if len(_mem_cache) >= _MEM_CACHE_MAX:
            now = time.time()
            expired = [k for k, (exp, _) in _mem_cache.items() if exp <= now]
            for k in expired:
                _mem_cache.pop(k, None)
            if len(_mem_cache) >= _MEM_CACHE_MAX:
                _mem_cache.pop(next(iter(_mem_cache)), None)
        _mem_cache[key] = (time.time() + int(ttl_seconds), raw)
        _cache_stats["writes"] += 1


def cache_delete(*keys_or_patterns: str):
    if not keys_or_patterns:
        return
    r = _get_redis()
    for pat in keys_or_patterns:
        if not pat:
            continue
        if r is not None:
            try:
                if "*" in pat:
                    batch = list(r.scan_iter(match=pat, count=100))
                    if batch:
                        r.delete(*batch)
                else:
                    r.delete(pat)
            except Exception as e:
                _cache_stats["errors"] += 1
                _cache_stats["last_error"] = str(e)

        with _cache_lock:
            if "*" in pat:
                prefix = pat.split("*", 1)[0]
                doomed = [k for k in _mem_cache if k.startswith(prefix)]
                for k in doomed:
                    _mem_cache.pop(k, None)
            else:
                _mem_cache.pop(pat, None)
    _cache_stats["invalidations"] += 1


def cache_invalidate_store(store_key: str):
    pats = _STORE_CACHE_INVALIDATION_MAP.get(store_key)
    if pats:
        cache_delete(*pats)


def cache_aside_get(key: str, ttl_seconds: int, loader_fn) -> tuple[Any, str]:
    cached = cache_get(key)
    if cached is not None:
        return cached, "HIT"
    data = loader_fn()
    if data is not None:
        cache_set(key, data, ttl_seconds)
    return data, "MISS"


_MASTER_KEY_FILE = DATA_DIR / ".master.key"
_ENC_PREFIX = "enc:v1:"
_SETTINGS_SECRET_KEYS = ("khqrpay_api_key", "telegram_bot_token", "smtp_password", "turnstile_secret_key")

def _get_encryption_subkeys() -> tuple[bytes, bytes]:
    raw_secret = (os.environ.get("DATA_ENCRYPTION_KEY") or "").strip()
    if not raw_secret:
        if _MASTER_KEY_FILE.exists():
            try:
                raw_secret = _MASTER_KEY_FILE.read_text(encoding="utf-8").strip()
            except Exception:
                raw_secret = ""
        if not raw_secret:
            raw_secret = secrets.token_urlsafe(32)
            try:
                _MASTER_KEY_FILE.write_text(raw_secret, encoding="utf-8")
                try:
                    os.chmod(_MASTER_KEY_FILE, 0o600)
                except Exception:
                    pass
            except Exception:
                pass
    master_bytes = raw_secret.encode("utf-8")
    enc_key = hashlib.sha256(b"rolea-enc-v1:" + master_bytes).digest()
    mac_key = hashlib.sha256(b"rolea-mac-v1:" + master_bytes).digest()
    return enc_key, mac_key

def _encrypt_secret(plain: Any) -> str:
    s = str(plain or "")
    if not s:
        return ""
    if s.startswith(_ENC_PREFIX):
        return s
    enc_key, mac_key = _get_encryption_subkeys()
    pt = s.encode("utf-8")
    nonce = secrets.token_bytes(16)
    stream = bytearray()
    blk_idx = 0
    while len(stream) < len(pt):
        stream.extend(hashlib.sha256(enc_key + nonce + struct.pack(">I", blk_idx)).digest())
        blk_idx += 1
    ct = bytes(a ^ b for a, b in zip(pt, stream))
    tag = hmac.new(mac_key, b"enc:v1:" + nonce + ct, hashlib.sha256).digest()
    return _ENC_PREFIX + base64.urlsafe_b64encode(nonce + ct + tag).decode("ascii")

def _decrypt_secret(val: Any) -> str:
    s = str(val or "")
    if not s or not s.startswith(_ENC_PREFIX):
        return s
    try:
        blob = base64.urlsafe_b64decode(s[len(_ENC_PREFIX):].encode("ascii"))
        if len(blob) < 48:
            return ""
        nonce = blob[:16]
        tag = blob[-32:]
        ct = blob[16:-32]
        enc_key, mac_key = _get_encryption_subkeys()
        expected_tag = hmac.new(mac_key, b"enc:v1:" + nonce + ct, hashlib.sha256).digest()
        if not hmac.compare_digest(tag, expected_tag):
            return ""
        stream = bytearray()
        blk_idx = 0
        while len(stream) < len(ct):
            stream.extend(hashlib.sha256(enc_key + nonce + struct.pack(">I", blk_idx)).digest())
            blk_idx += 1
        pt = bytes(a ^ b for a, b in zip(ct, stream))
        return pt.decode("utf-8")
    except Exception:
        return ""

def _get_bot_cookie(bot_obj: Dict[str, Any]) -> str:
    return _decrypt_secret(bot_obj.get("cookie", ""))

def load_json(path: Path, default: Any) -> Any:
    key = path.stem
    db_val = _mysql_get(key)
    if db_val is not None:
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(db_val, f, indent=2, ensure_ascii=False)
        except Exception:
            pass
        return db_val

    loaded = default
    found_local = False
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                found_local = True
        except Exception as e:
            print(f"Error loading {path}: {e}")

    if found_local and _get_mysql_cfg():
        _mysql_set(key, loaded)
    return loaded

def save_json(path: Path, data: Any):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving {path}: {e}")
    _mysql_set(path.stem, data)
    cache_invalidate_store(path.stem)

# Load initial data
orders = load_json(DB_PATH, orders)
packages = load_json(PACKAGES_PATH, packages)
settings = load_json(SETTINGS_PATH, settings)
_settings_needs_reencrypt = False
for _sk in _SETTINGS_SECRET_KEYS:
    _val = str(settings.get(_sk) or "")
    if _val.startswith(_ENC_PREFIX):
        settings[_sk] = _decrypt_secret(_val)
    elif _val:
        _settings_needs_reencrypt = True
for _env_k, _set_k in (
    ("TELEGRAM_BOT_TOKEN", "telegram_bot_token"),
    ("KHQRPAY_API_KEY", "khqrpay_api_key"),
    ("SMTP_EMAIL", "smtp_email"),
    ("SMTP_PASSWORD", "smtp_password"),
    ("TURNSTILE_SITE_KEY", "turnstile_site_key"),
    ("TURNSTILE_SECRET_KEY", "turnstile_secret_key"),
):
    if not settings.get(_set_k) and os.environ.get(_env_k):
        settings[_set_k] = os.environ[_env_k]
games = load_json(GAMES_PATH, games)
users = load_json(USERS_PATH, users)
_users_dirty = False
for _u in users:
    if isinstance(_u, dict) and "password_plain" in _u:
        if not _u.get("password_hash") and _u.get("password_plain"):
            _u["password_hash"] = hashlib.sha256((str(_u["password_plain"]) + "ROLEA_SECURE_SALT_2026").encode("utf-8")).hexdigest()
        _u.pop("password_plain", None)
        _users_dirty = True
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
_inv_dirty = False
for _b in inventory.get("bots", []):
    _bc = str(_b.get("cookie") or "")
    if _bc and not _bc.startswith(_ENC_PREFIX):
        _b["cookie"] = _encrypt_secret(_bc)
        _inv_dirty = True
if _inv_dirty:
    save_json(INVENTORY_PATH, inventory)

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
def save_settings():
    enc_settings = dict(settings)
    for _sk in _SETTINGS_SECRET_KEYS:
        if enc_settings.get(_sk):
            enc_settings[_sk] = _encrypt_secret(enc_settings[_sk])
    save_json(SETTINGS_PATH, enc_settings)
if _settings_needs_reencrypt:
    save_settings()
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
        "totp_enabled": False,
        "totp_secret_enc": "",
        "totp_pending_secret_enc": "",
        "wallet_daily_limit_usd": 100.0,
        "wallet_velocity_max_tx_5m": 8,
        "session_timeout_hours": 24,
        "telegram_login_alert": True,
        "sessions": {},
        "login_logs": [],
        "audit_logs": []
    }

admin_security: Dict[str, Any] = load_json(ADMIN_SECURITY_PATH, None)
if not admin_security or not admin_security.get("password_hash"):
    admin_security = init_default_admin_security()
    save_json(ADMIN_SECURITY_PATH, admin_security)

admin_security.setdefault("totp_enabled", False)
admin_security.setdefault("totp_secret_enc", "")
admin_security.setdefault("totp_pending_secret_enc", "")
admin_security.setdefault("wallet_daily_limit_usd", 100.0)
admin_security.setdefault("wallet_velocity_max_tx_5m", 8)
admin_security.setdefault("audit_logs", [])

def save_admin_security():
    save_json(ADMIN_SECURITY_PATH, admin_security)

def _generate_totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")

def _totp_code_for_step(secret_b32: str, step: int) -> str:
    pad = "=" * ((8 - len(secret_b32) % 8) % 8)
    key = base64.b32decode(secret_b32.upper() + pad, casefold=True)
    msg = struct.pack(">Q", step)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code_int = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return f"{code_int % 1000000:06d}"

def _verify_totp_code(secret_b32: str, candidate: str, window: int = 1) -> bool:
    code = re.sub(r"\s+", "", str(candidate or ""))
    if not secret_b32 or not re.fullmatch(r"\d{6}", code):
        return False
    now_step = int(time.time() // 30)
    for delta in range(-window, window + 1):
        try:
            expected = _totp_code_for_step(secret_b32, now_step + delta)
            if hmac.compare_digest(code, expected):
                return True
        except Exception:
            return False
    return False

def _totp_qr_data_url(secret_b32: str, username: str) -> tuple[str, str]:
    issuer = "Rolea Topup"
    acct = f"{issuer}:{username}"
    uri = (
        f"otpauth://totp/{quote_plus(acct)}"
        f"?secret={secret_b32}&issuer={quote_plus(issuer)}&algorithm=SHA1&digits=6&period=30"
    )
    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=8, border=2)
    qr.add_data(uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0f172a", back_color="#ffffff")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii"), uri

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

def _record_admin_audit(request: Optional[Request], action: str, target: str, details: str = "", alert_tg: bool = True):
    ip = (get_admin_effective_ip(request) or "unknown") if request else "system"
    adm_user = admin_security.get("username", "admin")
    audits = admin_security.setdefault("audit_logs", [])
    audits.insert(0, {
        "time": datetime.now(timezone.utc).isoformat(),
        "action": str(action)[:80],
        "admin": str(adm_user)[:40],
        "ip": str(ip)[:60],
        "target": str(target)[:80],
        "details": str(details)[:160],
    })
    if len(audits) > 200:
        admin_security["audit_logs"] = audits[:200]
    save_admin_security()
    if alert_tg and admin_security.get("telegram_login_alert", True):
        try:
            loop = asyncio.get_running_loop()
            msg = (
                f"<b>[ADMIN AUDIT] {html.escape(str(action), quote=False)}</b>\n"
                f"Admin: <code>{html.escape(str(adm_user), quote=False)}</code> | IP: <code>{html.escape(str(ip), quote=False)}</code>\n"
                f"Target: <code>{html.escape(str(target), quote=False)}</code>\n"
                f"Details: {html.escape(str(details), quote=False)}"
            )
            loop.create_task(send_admin_security_telegram(msg))
        except RuntimeError:
            pass

def _check_and_enforce_wallet_guard(user: Dict[str, Any], spend_amount: float) -> tuple[bool, str]:
    """Enforce wallet freeze check, daily USD spending cap, and 5-minute rapid-velocity auto-freeze."""
    if user.get("wallet_frozen"):
        reason = str(user.get("wallet_freeze_reason") or "Security review").strip()
        return False, f"គណនី Wallet ត្រូវបានបង្កកបណ្តោះអាសន្ន ({reason})។ សូមទាក់ទង Admin។"

    now_dt = datetime.now(timezone.utc)
    today_prefix = now_dt.strftime("%Y-%m-%d")
    now_ts = now_dt.timestamp()
    uid = user.get("id")

    spent_today = 0.0
    recent_5m_count = 0
    for tx in wallet_transactions:
        if tx.get("user_id") != uid or tx.get("type") != "spend":
            continue
        amt = abs(float(tx.get("amount", 0) or 0))
        d_str = str(tx.get("date") or "")
        if d_str.startswith(today_prefix):
            spent_today += amt
        try:
            tx_ts = datetime.fromisoformat(d_str.replace("Z", "+00:00")).timestamp()
            if (now_ts - tx_ts) <= 300:
                recent_5m_count += 1
        except Exception:
            pass

    try:
        vel_max = max(2, int(admin_security.get("wallet_velocity_max_tx_5m", 8) or 8))
    except (ValueError, TypeError):
        vel_max = 8
    if recent_5m_count >= vel_max:
        user["wallet_frozen"] = True
        user["wallet_freeze_reason"] = f"Auto-frozen: {recent_5m_count} rapid wallet spends within 5 min"
        save_users()
        try:
            asyncio.get_running_loop().create_task(send_admin_security_telegram(
                f"<b>[WALLET AUTO-FREEZE] Velocity Guard Triggered</b>\n"
                f"Customer: <code>{html.escape(str(user.get('username') or uid), quote=False)}</code>\n"
                f"Spends in 5m: <code>{recent_5m_count}/{vel_max}</code>"
            ))
        except RuntimeError:
            pass
        return False, "សុវត្ថិភាព: រកឃើញការចំណាយលឿនខុសប្រក្រតី គណនី Wallet ត្រូវបានបង្កកបណ្តោះអាសន្ន។"

    try:
        daily_limit = float(admin_security.get("wallet_daily_limit_usd", 100.0) or 0.0)
    except (ValueError, TypeError):
        daily_limit = 100.0
    if daily_limit > 0 and round(spent_today + float(spend_amount), 2) > daily_limit:
        return False, f"លើសដែនកំណត់ចំណាយប្រចាំថ្ងៃ (${daily_limit:.2f}/ថ្ងៃ · បានចំណាយ ${spent_today:.2f})។"

    return True, ""

def _get_turnstile_config() -> tuple[str, str]:
    site_key = str(settings.get("turnstile_site_key") or os.environ.get("TURNSTILE_SITE_KEY") or "").strip()
    secret_key = str(settings.get("turnstile_secret_key") or os.environ.get("TURNSTILE_SECRET_KEY") or "").strip()
    return site_key, secret_key

async def _verify_turnstile_if_enabled(request: Request, body: Dict[str, Any]) -> tuple[bool, str]:
    site_key, secret_key = _get_turnstile_config()
    if not site_key or not secret_key:
        return True, ""
    token = str(body.get("cf_turnstile_token") or body.get("cf-turnstile-response") or "").strip()
    if not token:
        return False, "សូមបញ្ជាក់ Cloudflare Security Verification (Turnstile) ជាមុនសិន។"
    remote_ip = get_admin_effective_ip(request)
    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            res = await client.post(
                "https://challenges.cloudflare.com/turnstile/v0/siteverify",
                data={"secret": secret_key, "response": token, "remoteip": remote_ip}
            )
            data = res.json()
            if data.get("success") is True:
                return True, ""
            return False, "ការផ្ទៀងផ្ទាត់ Turnstile មិនត្រឹមត្រូវ ឬផុតកំណត់។ សូមព្យាយាមម្តងទៀត។"
    except Exception:
        return False, "មិនអាចផ្ទៀងផ្ទាត់ Cloudflare Turnstile បានទេ។ សូមព្យាយាមម្តងទៀត។"

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
_LEGACY_CUSTOMER_SALT = "ROLEA_SECURE_SALT_2026"
customer_failed_attempts: Dict[str, List[float]] = {}
customer_lockouts: Dict[str, float] = {}

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120000).hex()
    return f"pbkdf2_sha256${salt}${dk}"

def verify_password(plain_password: str, stored_hash: str) -> tuple[bool, bool]:
    """Verify password against PBKDF2-HMAC-SHA256 or legacy salted SHA-256. Returns (matched, needs_upgrade)."""
    if not plain_password or not stored_hash:
        return False, False
    if stored_hash.startswith("pbkdf2_sha256$"):
        parts = stored_hash.split("$", 2)
        if len(parts) != 3:
            return False, False
        _, salt, expected_hex = parts
        cand_hex = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt.encode("utf-8"), 120000).hex()
        return hmac.compare_digest(cand_hex, expected_hex), False
    legacy_hex = hashlib.sha256((plain_password + _LEGACY_CUSTOMER_SALT).encode("utf-8")).hexdigest()
    matched = hmac.compare_digest(legacy_hex, stored_hash)
    return matched, matched

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
    game_name = html.escape(str(g.get("name") or order.get("game") or "Rolea Topup"), quote=False)
    customer = html.escape(str(order.get("roblox_username") or order.get("username") or order.get("display_name") or "Customer"), quote=False)
    amount = f"{float(order.get('amount') or order.get('price') or 0):.2f}"
    pkg_name = html.escape(str(order.get("package") or f"{order.get('robux_amount', '')} {g.get('unit', 'Units')}".strip()), quote=False)
    pay_method = html.escape(str(order.get("payment_method") or "ABA KHQR"), quote=False)

    is_tiktok = (order.get("game") == "tiktok") or (order.get("product_type") == "smm") or str(order.get("player_id", "")).startswith("http")
    target_link = str(order.get("target_url") or order.get("player_id") or order.get("roblox_username") or "").strip()

    if is_tiktok:
        account_line = f"🔗 <b>Video Link:</b> {html.escape(target_link, quote=False)}"
    else:
        account_line = f"👤 <b>Account:</b> {customer}"

    try:
        dt = datetime.fromisoformat(order.get("created_at", datetime.now(timezone.utc).isoformat()).replace("Z", "+00:00"))
        time_str = dt.astimezone(timezone(timedelta(hours=7))).strftime("%m/%d/%Y, %I:%M:%S %p")
    except Exception:
        time_str = datetime.now().strftime("%m/%d/%Y, %I:%M:%S %p")

    safe_store = html.escape(str(settings.get("store_name", "Rolea Topup")), quote=False)
    safe_oid = html.escape(str(order.get("order_id") or ""), quote=False)
    message = (
        f"🔔 <b>[PAID ORDER NOTIFICATION]</b>\n"
        f"🏪 <b>Store:</b> {safe_store}\n"
        f"🆔 <b>Order ID:</b> <code>{safe_oid}</code>\n"
        f"🎮 <b>Game/Service:</b> {game_name}\n"
        f"{account_line}\n"
        f"📦 <b>Package:</b> {pkg_name}\n"
        f"💵 <b>Amount:</b> ${amount} USD\n"
        f"💳 <b>Payment Gateway:</b> {pay_method}\n"
        f"⚡ <b>Status:</b> PAID - AWAITING ADMIN DELIVERY\n"
        f"🕒 <b>Time:</b> {time_str}"
    )

    inline_keyboard = []
    if is_tiktok and (target_link.startswith("https://") or target_link.startswith("http://")):
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
    safe_store = html.escape(str(store_name or "Rolea Topup"))
    safe_acc = html.escape(str(account_name or "User"))
    safe_otp = html.escape(str(otp_code or ""))
    safe_ip = html.escape(str(client_ip or "unknown"))
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
              <div style="font-size:24px;font-weight:900;letter-spacing:1.2px;color:#ffffff;">{safe_store.upper()}</div>
              <div style="font-size:12px;font-weight:700;color:#38bdf8;margin-top:4px;letter-spacing:0.6px;text-transform:uppercase;">Account Password Recovery</div>
            </td>
          </tr>
          <tr>
            <td style="padding:28px;color:#e2e8f0;font-size:15px;line-height:1.6;">
              <h1 style="margin:0 0 18px;font-size:22px;font-weight:800;color:#ffffff;">Password Reset Code: {safe_otp}</h1>
              <div style="background-color:#0f172a;border:1px solid #334155;border-radius:12px;padding:18px;text-align:center;margin:0 0 20px;">
                <div style="font-size:11px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;">Code Requested</div>
                <div style="font-family:'Courier New',Courier,monospace;font-size:32px;font-weight:900;letter-spacing:8px;color:#ffffff;">{safe_otp}</div>
              </div>
              <p style="margin:0 0 12px;">Hello, <b style="color:#ffffff;">{safe_acc}</b></p>
              <p style="margin:0 0 12px;">A password reset code was requested for your {safe_store} account <b style="color:#ffffff;">{safe_acc}</b>.</p>
              <p style="margin:0 0 12px;color:#cbd5e1;">This request was received from IP <b style="color:#ffffff;">{safe_ip}</b>. This code is valid for 10 minutes.</p>
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


async def send_telegram_admin_alert(text: str):
    """Send an HTML alert message to the configured admin Telegram chat."""
    token = settings.get("telegram_bot_token") or os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = settings.get("telegram_chat_id") or os.environ.get("TELEGRAM_CHAT_ID", "") or "8710759437"
    if not token or not chat_id or not text:
        return
    await send_telegram_direct_message(token, chat_id, text)

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
    game_name = html.escape(str(g.get("name") or order.get("game") or "Rolea Topup"), quote=False)
    customer = html.escape(str(order.get("roblox_username") or order.get("username") or order.get("display_name") or "Customer"), quote=False)
    pkg = html.escape(str(order.get("package") or f"{order.get('robux_amount', '')} {g.get('unit', 'Units')}".strip()), quote=False)
    amount = f"{float(order.get('amount') or order.get('price') or 0):.2f}"

    text = (
        f"<b>ORDER DELIVERED SUCCESSFULLY</b>\n\n"
        f"Hello <b>{customer}</b>, your order has been completed and delivered!\n\n"
        f"<b>Order ID:</b> <code>#{html.escape(str(order.get('order_id') or ''), quote=False)}</code>\n"
        f"<b>Product:</b> {pkg} ({game_name})\n"
        f"<b>Amount:</b> ${amount} USD\n"
        f"<b>Status:</b> Completed & Delivered\n\n"
        f"Thank you for shopping at {html.escape(str(settings.get('store_name', 'Rolea Topup')), quote=False)}!"
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
    async with _tx_lock:
        order = next((o for o in orders if o.get("order_id") == order_id), None)
        if not order:
            await answer_callback_query(token, query_id, "Order not found.")
            return

        now_ict = datetime.now(timezone(timedelta(hours=7))).strftime("%m/%d/%Y, %I:%M:%S %p")
        g = games.get(order.get("game", "roblox"), {})
        game_name = html.escape(str(g.get("name") or order.get("game") or "Rolea Topup"), quote=False)
        customer = html.escape(str(order.get("roblox_username") or order.get("username") or order.get("display_name") or "Customer"), quote=False)
        amount = f"{float(order.get('amount') or order.get('price') or 0):.2f}"
        pkg_name = html.escape(str(order.get("package") or f"{order.get('robux_amount', '')} {g.get('unit', 'Units')}".strip()), quote=False)
        from_user = query.get("from", {})
        raw_admin = f"@{from_user['username']}" if from_user.get("username") else (from_user.get("first_name") or "Admin")
        admin_name = html.escape(str(raw_admin), quote=False)

        if action == "complete":
            if order.get("status") == "refunded":
                await answer_callback_query(token, query_id, f"⚠️ Order #{order_id} was already refunded.")
                return
            order["paid"] = True
            order["delivered"] = True
            order["status"] = "completed"
            order["step"] = "delivered"
            order["label"] = "Order fulfilled and confirmed by Admin via Telegram"
            try:
                deduct_inventory_on_deliver(order)
            except Exception as eInv:
                print("Inventory deduction error:", eInv)
            save_orders()
            asyncio.create_task(notify_customer_order_completed(order))

            await answer_callback_query(token, query_id, f"✅ Order #{order_id} marked as Completed!")

            updated_text = (
                f"✅ <b>[ORDER COMPLETED BY ADMIN]</b>\n"
                f"🏪 <b>Store:</b> {html.escape(str(settings.get('store_name', 'Rolea Topup')), quote=False)}\n"
                f"🆔 <b>Order ID:</b> <code>{html.escape(str(order.get('order_id') or ''), quote=False)}</code>\n"
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
            if order.get("status") == "refunded" or order.get("wallet_refunded"):
                await answer_callback_query(token, query_id, f"⚠️ Order #{order_id} was already refunded.")
                return
            if order.get("delivered") or order.get("status") == "completed":
                await answer_callback_query(token, query_id, f"⚠️ Order #{order_id} is already completed.")
                return
            order["status"] = "refunded"
            order["step"] = "refunded"
            order["delivered"] = False
            order["label"] = "Order rejected and refunded to customer by Admin"
            if order.get("payment_method") == "Rolea Wallet" and order.get("user_id") and order.get("paid") and not order.get("wallet_refunded"):
                order["wallet_refunded"] = True
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
                f"🏪 <b>Store:</b> {html.escape(str(settings.get('store_name', 'Rolea Topup')), quote=False)}\n"
                f"🆔 <b>Order ID:</b> <code>{html.escape(str(order.get('order_id') or ''), quote=False)}</code>\n"
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

def _is_safe_url(val: Any, allow_relative: bool = True, max_len: int = 500) -> bool:
    if not isinstance(val, str):
        return False
    s = val.strip()
    if not s or len(s) > max_len or any(c in s for c in ("\x00", "\r", "\n")):
        return False
    low = s.lower()
    if low.startswith("https://") or low.startswith("http://"):
        return True
    if allow_relative and s.startswith("/") and not s.startswith("//"):
        return True
    return False

def _is_valid_email(val: Any) -> bool:
    if not isinstance(val, str):
        return False
    s = val.strip()
    if len(s) > 160 or any(c in s for c in ("\r", "\n", "\x00", " ")):
        return False
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", s))

def _validate_image_magic(buf: bytes) -> Optional[str]:
    if not buf or len(buf) > MAX_UPLOAD_BODY_BYTES:
        return None
    if buf.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if buf.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if len(buf) >= 12 and buf[:4] == b"RIFF" and buf[8:12] == b"WEBP":
        return "webp"
    if buf.startswith((b"GIF87a", b"GIF89a")):
        return "gif"
    return None

def _sanitize_csv_cell(val: Any) -> str:
    s = str(val if val is not None else "")
    if s and s[0] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + s
    return s

def _is_https_request(request: Request) -> bool:
    xfp = (request.headers.get("x-forwarded-proto") or "").split(",")[0].strip().lower()
    return xfp == "https" or request.url.scheme == "https"

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
    if path in ("/api/settings", "/api/games", "/api/packages") or path.startswith("/api/game/"):
        return ("static", 300, 60)
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

def verify_khqr_bank_payment(live: Optional[Dict[str, Any]], expected_amount: float, expected_order_id: Optional[str] = None) -> tuple[bool, str]:
    """Strict server-side bank/KHQR verification (status + order_id binding + paid amount + currency)."""
    if not isinstance(live, dict):
        return False, "invalid_payload"
    st = str(live.get("status", "")).lower().strip()
    if st not in ("paid", "success", "completed"):
        return False, st or "pending"

    if expected_order_id:
        live_oid = str(live.get("order_id") or "").strip()
        if live_oid and live_oid != str(expected_order_id).strip():
            return False, "order_id_mismatch"

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

_SENSITIVE_PROBE_EXTS = (
    ".env", ".json", ".py", ".pyc", ".pyo", ".db", ".sqlite", ".sqlite3",
    ".bak", ".sql", ".log", ".ini", ".cfg", ".yml", ".yaml", ".toml"
)
_ADMIN_CSRF_MUTATION_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_VERCEL_ID_RE = re.compile(r"^[a-z0-9]{3,12}::\S{4,}$")
_unpaid_order_tracker: Dict[str, List[Dict[str, Any]]] = {}

def _normalize_request_path(raw_path: str) -> tuple[str, bool]:
    """Decode and canonicalize URL path; flag dot/backslash/null-byte evasion attempts."""
    raw = str(raw_path or "/")
    low_raw = raw.lower()
    if "\\" in raw or "%5c" in low_raw or "\x00" in raw or "%00" in low_raw:
        return "/", True
    decoded = unquote(raw)
    if "%" in decoded:
        decoded = unquote(decoded)
    if "\\" in decoded or "\x00" in decoded:
        return "/", True
    parts = []
    for seg in decoded.split("/"):
        if not seg or seg == ".":
            continue
        if seg == "..":
            return "/", True
        parts.append(seg)
    return ("/" + "/".join(parts)).lower(), False

def _is_sensitive_probe_path(norm_path: str) -> bool:
    if norm_path.endswith(_SENSITIVE_PROBE_EXTS):
        return True
    for seg in norm_path.split("/"):
        if seg.startswith(".") and len(seg) > 1:
            return True
    return False

def _prune_orders_safe(max_orders: int = 500):
    """Trim orders cap by evicting oldest unpaid/expired orders before paid/completed orders."""
    global orders
    if len(orders) <= max_orders:
        return
    drop_needed = len(orders) - max_orders
    remove_indices = []
    # Pass 1: oldest unpaid & non-finalized orders
    for idx in range(len(orders) - 1, -1, -1):
        o = orders[idx]
        if not o.get("paid") and o.get("status") not in ("paid", "completed", "refunded"):
            remove_indices.append(idx)
            if len(remove_indices) >= drop_needed:
                break
    # Pass 2: if still over limit, drop oldest remaining orders
    if len(remove_indices) < drop_needed:
        picked = set(remove_indices)
        for idx in range(len(orders) - 1, -1, -1):
            if idx not in picked:
                remove_indices.append(idx)
                if len(remove_indices) >= drop_needed:
                    break
    drop_set = set(remove_indices)
    orders[:] = [o for i, o in enumerate(orders) if i not in drop_set]

def _record_unpaid_order_attempt(client_ip: str, order_id: str, game_key: str, pkg_id: Any, player_id: str):
    if not client_ip:
        return
    now_ts = time.time()
    bucket = [e for e in _unpaid_order_tracker.get(client_ip, []) if now_ts - e.get("ts", 0) < 900]
    bucket.append({
        "order_id": order_id,
        "ts": now_ts,
        "game": str(game_key or ""),
        "package_id": str(pkg_id or ""),
        "player_id": str(player_id or "").lower().strip()
    })
    _unpaid_order_tracker[client_ip] = bucket[-30:]
    if len(_unpaid_order_tracker) > 5000:
        stale_ips = [k for k, v in _unpaid_order_tracker.items() if not v or (now_ts - v[-1].get("ts", 0)) > 900]
        for k in stale_ips[:2500]:
            _unpaid_order_tracker.pop(k, None)

def _check_unpaid_order_anti_bypass(client_ip: str, game_key: str, pkg_id: Any, player_id: str) -> tuple[bool, str]:
    """Enforce blacklist['rules'] to stop unpaid order flooding and duplicate order spam."""
    rules = blacklist.get("rules") or {}
    try:
        max_unpaid = max(1, int(rules.get("max_unpaid_orders_per_ip", 5) or 5))
    except (ValueError, TypeError):
        max_unpaid = 5
    block_dup = bool(rules.get("block_duplicate_unpaid_orders", True))
    auto_flag = bool(rules.get("auto_flag_suspicious", True))

    now_ts = time.time()
    raw_bucket = [e for e in _unpaid_order_tracker.get(client_ip, []) if now_ts - e.get("ts", 0) < 900]
    order_map = {o.get("order_id"): o for o in orders if o.get("order_id")}
    active_unpaid = []
    for e in raw_bucket:
        ord_obj = order_map.get(e.get("order_id"))
        if ord_obj and not ord_obj.get("paid") and ord_obj.get("status") not in ("paid", "completed", "refunded", "expired", "failed"):
            active_unpaid.append(e)
    _unpaid_order_tracker[client_ip] = active_unpaid

    def _flag_suspicious(reason: str):
        if auto_flag:
            logs = blacklist.setdefault("logs", [])
            logs.insert(0, {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "ip": client_ip,
                "player_id": str(player_id or "")[:60],
                "game": str(game_key or ""),
                "reason": reason
            })
            if len(logs) > 200:
                blacklist["logs"] = logs[:200]
            save_blacklist()

    norm_pid = str(player_id or "").lower().strip()
    if block_dup and norm_pid:
        for e in active_unpaid:
            if (now_ts - e.get("ts", 0)) < 90 and e.get("game") == str(game_key or "") and e.get("package_id") == str(pkg_id or "") and e.get("player_id") == norm_pid:
                _flag_suspicious("Duplicate unpaid order spam within 90s")
                return False, "មានការបញ្ជាទិញដដែលដែលមិនទាន់ទូទាត់រួច។ សូមបង់ប្រាក់លើវិក្កយបត្រចាស់ ឬរង់ចាំ 90 វិនាទី។"

    if len(active_unpaid) >= max_unpaid:
        _flag_suspicious(f"Exceeded max unpaid orders per IP ({len(active_unpaid)}/{max_unpaid})")
        return False, f"អ្នកមានវិក្កយបត្រមិនទាន់បង់ប្រាក់ច្រើនពេក ({len(active_unpaid)}/{max_unpaid})។ សូមបង់ប្រាក់ឬរង់ចាំមុននឹងបង្កើតថ្មី។"

    return True, ""

_ALLOWED_HTTP_METHODS = {"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"}
_HOST_HEADER_RE = re.compile(r"^[A-Za-z0-9.\-:\[\]]{1,253}$")
_HACKER_UA_RE = re.compile(
    r"(?:sqlmap|nikto|nmap|masscan|nuclei|wpscan|dirbuster|gobuster|ffuf|feroxbuster|"
    r"wfuzz|dirsearch|acunetix|nessus|openvas|havij|commix|hydra|medusa|patator|"
    r"zgrab|w3af|skipfish|arachni|netsparker|invicti|dalfox|xsser|appscan|joomscan|"
    r"droopescan|whatweb|zaproxy|owasp\s*zap|burpcollaborator|interactsh|pangolin|jsql)",
    re.IGNORECASE,
)
_HACKER_PROBE_EXACT = {
    "/.htaccess", "/.htpasswd", "/xmlrpc.php", "/wp-login.php", "/wp-cron.php",
    "/readme.html", "/license.txt", "/composer.json", "/composer.lock",
    "/package.json", "/package-lock.json", "/server-status", "/server-info",
    "/eval-stdin.php", "/shell.php", "/c99.php", "/r57.php", "/phpinfo.php",
    "/info.php", "/test.php", "/config.php", "/backup.zip", "/backup.tar.gz", "/dump.sql",
}
_HACKER_PROBE_PREFIXES = (
    "/wp-admin", "/wp-content", "/wp-includes", "/phpmyadmin", "/pma", "/adminer",
    "/cgi-bin", "/boaform", "/actuator", "/swagger", "/api-docs", "/graphql",
    "/telescope", "/autodiscover", "/ecp", "/owa", "/vendor/", "/phpunit",
    "/console", "/.git", "/.svn", "/.hg", "/.aws", "/.ssh", "/.vscode", "/.idea",
)
_WAF_PATTERNS = [
    ("sqli", re.compile(
        r"(?:\bunion\s+(?:all\s+)?select\b|\bselect\b.{1,40}\bfrom\s+information_schema\b|"
        r"\b(?:sleep|benchmark|pg_sleep)\s*\(\s*\d|\bwaitfor\s+delay\b|"
        r"\b(?:extractvalue|updatexml)\s*\(|(?:['\";]\s*(?:or|and)\s+['\"]?\d+['\"]?\s*=\s*['\"]?\d+))",
        re.IGNORECASE | re.DOTALL,
    )),
    ("xss", re.compile(
        r"(?:<\s*script\b|javascript\s*:\s*|<\s*(?:iframe|svg|object|embed)\b[^>]*\bon\w+\s*=|"
        r"\bon(?:error|load|mouseover|focus|click)\s*=\s*['\"]?(?:alert|prompt|confirm|fetch|eval|document\.))",
        re.IGNORECASE | re.DOTALL,
    )),
    ("rce_lfi", re.compile(
        r"(?:;\s*(?:cat|ls|id|whoami|uname|wget|curl|nc|bash|sh|python|perl|php)\b|`[^`]{2,}`|"
        r"\$\([^)]{2,}\)|/etc/passwd|/etc/shadow|/proc/self/environ|cmd\.exe|powershell(?:\.exe)?\s+-)",
        re.IGNORECASE,
    )),
    ("ssti_ssrf", re.compile(
        r"(?:\{\{.*?(?:__class__|__mro__|__subclasses__|config\.items|cycler|joiner).*?\}\}|"
        r"\$\{(?:jndi|env|sys|java)\s*:|169\.254\.169\.254|metadata\.google\.internal|"
        r"oastify\.com|burpcollaborator\.net|interact\.sh)",
        re.IGNORECASE | re.DOTALL,
    )),
    ("proto_pollution", re.compile(
        r"(?:__proto__|constructor\s*\[?\s*['\"]?prototype)",
        re.IGNORECASE,
    )),
]
_WAF_SKIP_SECRET_KEYS = {"password", "old_password", "new_password", "confirm_password", "pin", "token", "receipt_token", "credential"}
_scanner_strikes: Dict[str, List[float]] = {}
_scanner_bans: Dict[str, float] = {}
_scanner_log_cooldown: Dict[str, float] = {}

def _is_hacker_probe_path(norm_path: str) -> bool:
    if norm_path in _HACKER_PROBE_EXACT:
        return True
    return any(norm_path == p.rstrip("/") or norm_path.startswith(p if p.endswith("/") else p + "/") for p in _HACKER_PROBE_PREFIXES)

def _detect_web_attack_payload(raw_text: str) -> Optional[str]:
    if not raw_text:
        return None
    sample = str(raw_text)[:8192]
    # Decode URL-encoded attack vectors up to 2 levels for inspection
    decoded = unquote(sample)
    if "%" in decoded:
        decoded = unquote(decoded)
    for text_variant in (sample, decoded):
        for category, pattern in _WAF_PATTERNS:
            if pattern.search(text_variant):
                return category
    return None

def _scan_payload_tree_waf(obj: Any, parent_key: str = "") -> Optional[str]:
    if isinstance(obj, dict):
        for k, v in obj.items():
            k_low = str(k).lower().strip()
            if k_low in ("__proto__", "prototype"):
                return "proto_pollution"
            if k_low in _WAF_SKIP_SECRET_KEYS:
                continue
            hit = _scan_payload_tree_waf(v, k_low)
            if hit:
                return hit
    elif isinstance(obj, list):
        for item in obj[:100]:
            hit = _scan_payload_tree_waf(item, parent_key)
            if hit:
                return hit
    elif isinstance(obj, str):
        return _detect_web_attack_payload(obj)
    return None

def _sync_waf_bans_from_blacklist():
    now_ts = time.time()
    persisted = blacklist.get("waf_bans") or {}
    if not isinstance(persisted, dict):
        return
    for ip_k, info in list(persisted.items()):
        until = float((info or {}).get("banned_until", 0) or 0)
        if until > now_ts:
            _scanner_bans[ip_k] = until
        else:
            persisted.pop(ip_k, None)

def _is_scanner_temp_banned(ip: str) -> tuple[bool, int]:
    if not ip or ip in ("127.0.0.1", "::1", "unknown"):
        return False, 0
    if not _scanner_bans and blacklist.get("waf_bans"):
        _sync_waf_bans_from_blacklist()
    now_ts = time.time()
    ban_until = _scanner_bans.get(ip, 0)
    if ban_until > now_ts:
        return True, max(1, int(ban_until - now_ts))
    if ban_until:
        _scanner_bans.pop(ip, None)
        if isinstance(blacklist.get("waf_bans"), dict) and ip in blacklist["waf_bans"]:
            blacklist["waf_bans"].pop(ip, None)
            save_blacklist()
    return False, 0

def _record_hacker_strike(ip: str, reason: str, detail: str = ""):
    if not ip or ip == "unknown":
        return
    now_ts = time.time()
    is_loopback = ip in ("127.0.0.1", "::1")
    newly_banned = False
    strike_count = 0
    if not is_loopback:
        strikes = [t for t in _scanner_strikes.get(ip, []) if now_ts - t < 600]
        strikes.append(now_ts)
        strike_count = len(strikes)
        _scanner_strikes[ip] = strikes[-20:]
        if len(_scanner_strikes) > 5000:
            _scanner_strikes.clear()
        if strike_count >= 3:
            ban_until = now_ts + 900  # 15-minute automatic temp ban
            _scanner_bans[ip] = ban_until
            newly_banned = True
            if len(_scanner_bans) > 5000:
                _scanner_bans.clear()
            waf_bans = blacklist.setdefault("waf_bans", {})
            waf_bans[ip] = {
                "ip": ip,
                "banned_until": ban_until,
                "reason": f"{reason}: {detail}"[:140],
                "strikes": strike_count,
                "last_seen": datetime.now(timezone.utc).isoformat()
            }
            if len(waf_bans) > 500:
                expired = [k for k, v in waf_bans.items() if float(v.get("banned_until", 0) or 0) <= now_ts]
                for k in expired:
                    waf_bans.pop(k, None)

    if newly_banned or now_ts - _scanner_log_cooldown.get(ip, 0) > 60:
        _scanner_log_cooldown[ip] = now_ts
        if len(_scanner_log_cooldown) > 5000:
            _scanner_log_cooldown.clear()
        try:
            log_admin_security_event("Blocked Hacker/WAF", ip, "-", "locked", f"{reason}: {detail}"[:140])
            if newly_banned or (blacklist.get("rules") or {}).get("auto_flag_suspicious", True):
                logs = blacklist.setdefault("logs", [])
                logs.insert(0, {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "ip": ip,
                    "player_id": "-",
                    "game": "waf",
                    "reason": f"{reason}: {detail}"[:140]
                })
                if len(logs) > 200:
                    blacklist["logs"] = logs[:200]
                save_blacklist()
        except Exception:
            pass
    elif newly_banned:
        try:
            save_blacklist()
        except Exception:
            pass

class _BodyTooLarge(Exception):
    pass

class MaxBodySizeMiddleware:
    """Pure ASGI body-size limiter & JSON/form WAF scanner (handles chunked bodies safely)."""
    WAF_INSPECT_LIMIT = 256 * 1024

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            return await self.app(scope, receive, send)

        norm_path, _ = _normalize_request_path(scope.get("path", "/"))
        method = str(scope.get("method") or "GET").upper()
        is_upload = norm_path in ("/api/admin/upload-banner", "/api/admin/games/upload-logo")
        max_bytes = MAX_UPLOAD_BODY_BYTES if is_upload else MAX_JSON_BODY_BYTES

        content_type = ""
        for k, v in scope.get("headers", []):
            kl = k.lower()
            if kl == b"content-length":
                try:
                    cl_val = int(v.decode("latin-1").strip())
                except ValueError:
                    return await self._send_json(send, 400, {"ok": False, "error": "Invalid Content-Length"})
                if cl_val < 0 or cl_val > max_bytes:
                    return await self._send_json(send, 413, {"ok": False, "error": "Payload too large"})
            elif kl == b"content-type":
                content_type = v.decode("latin-1", errors="ignore").lower()

        # Inspect small non-admin JSON/form payloads for SQLi/XSS/RCE/SSTI/ProtoPollution before FastAPI runs
        should_waf_body = (
            method in ("POST", "PUT", "PATCH")
            and not is_upload
            and not norm_path.startswith("/api/admin")
            and ("json" in content_type or "x-www-form-urlencoded" in content_type or not content_type)
        )
        if should_waf_body:
            buffered = []
            buf_size = 0
            eof_reached = False
            while True:
                msg = await receive()
                if msg.get("type") != "http.request":
                    buffered.append(msg)
                    if msg.get("type") == "http.disconnect":
                        eof_reached = True
                    break
                chunk = msg.get("body", b"")
                buf_size += len(chunk)
                if buf_size > max_bytes:
                    return await self._send_json(send, 413, {"ok": False, "error": "Payload too large"})
                buffered.append(msg)
                if not msg.get("more_body", False):
                    eof_reached = True
                    break
                if buf_size > self.WAF_INSPECT_LIMIT:
                    break

            if eof_reached:
                raw_bytes = b"".join(m.get("body", b"") for m in buffered if m.get("type") == "http.request")
                if raw_bytes:
                    raw_text = raw_bytes.decode("utf-8", errors="ignore")
                    hit = None
                    if "json" in content_type or raw_text.lstrip().startswith(("{", "[")):
                        try:
                            parsed = json.loads(raw_text)
                            hit = _scan_payload_tree_waf(parsed)
                        except Exception:
                            hit = _detect_web_attack_payload(raw_text)
                    else:
                        hit = _detect_web_attack_payload(raw_text)
                    if hit:
                        from starlette.requests import Request as _StarletteReq
                        eff_ip = get_admin_effective_ip(_StarletteReq(scope)) or "unknown"
                        _record_hacker_strike(eff_ip, f"WAF Body ({hit})", norm_path)
                        return await self._send_json(send, 403, {"ok": False, "error": "Malicious payload blocked by WAF"})

            replay_queue = list(buffered)
            stream_bytes = buf_size
            too_large = False
            sent_413 = False

            async def buffered_receive():
                nonlocal stream_bytes, too_large
                if replay_queue:
                    return replay_queue.pop(0)
                msg = await receive()
                if msg.get("type") == "http.request":
                    stream_bytes += len(msg.get("body", b""))
                    if stream_bytes > max_bytes:
                        too_large = True
                        raise _BodyTooLarge()
                return msg

            async def buffered_send(msg):
                nonlocal sent_413
                if too_large:
                    if not sent_413 and msg.get("type") == "http.response.start":
                        sent_413 = True
                        await self._send_json(send, 413, {"ok": False, "error": "Payload too large"})
                    return
                await send(msg)

            try:
                await self.app(scope, buffered_receive, buffered_send)
            except _BodyTooLarge:
                if not sent_413:
                    await self._send_json(send, 413, {"ok": False, "error": "Payload too large"})
            return

        total_bytes = 0
        too_large = False
        sent_413 = False

        async def wrapped_receive():
            nonlocal total_bytes, too_large
            msg = await receive()
            if msg.get("type") == "http.request":
                chunk = msg.get("body", b"")
                total_bytes += len(chunk)
                if total_bytes > max_bytes:
                    too_large = True
                    raise _BodyTooLarge()
            return msg

        async def wrapped_send(msg):
            nonlocal sent_413
            if too_large:
                if not sent_413 and msg.get("type") == "http.response.start":
                    sent_413 = True
                    await self._send_json(send, 413, {"ok": False, "error": "Payload too large"})
                return
            await send(msg)

        try:
            await self.app(scope, wrapped_receive, wrapped_send)
        except _BodyTooLarge:
            if not sent_413:
                await self._send_json(send, 413, {"ok": False, "error": "Payload too large"})

    @staticmethod
    async def _send_json(send, status: int, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        await send({
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
            ],
        })
        await send({"type": "http.response.body", "body": body, "more_body": False})

# Initialize FastAPI App
app = FastAPI(title="Rolea Topup API", version="2.0.0")

HOME_WIFI_NETWORK = ipaddress.ip_network("192.168.100.0/24", strict=False)
HOME_WIFI_PUBLIC_IPS = {"202.56.3.46"}
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
        if str(ip_obj) in HOME_WIFI_PUBLIC_IPS:
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

def _normalize_ip(raw: str) -> str:
    if not raw:
        return ""
    cand = raw.split(",")[0].strip()
    try:
        ip_obj = ipaddress.ip_address(cand)
        if getattr(ip_obj, "ipv4_mapped", None):
            ip_obj = ip_obj.ipv4_mapped
        return str(ip_obj)
    except ValueError:
        return ""

def _is_trusted_vercel_proxy(request: Request) -> bool:
    vercel_id = (request.headers.get("x-vercel-id") or "").strip()
    if not (_VERCEL_ID_RE.match(vercel_id) and request.headers.get("x-vercel-forwarded-for")):
        return False
    fwd_ip = _normalize_ip(request.headers.get("x-vercel-forwarded-for", ""))
    if not fwd_ip:
        return False
    try:
        ip_obj = ipaddress.ip_address(fwd_ip)
        # Reject spoofed loopback/private client IPs sent over a public connection
        if ip_obj.is_loopback or ip_obj.is_private or ip_obj.is_link_local or ip_obj.is_unspecified or ip_obj.is_reserved:
            return False
    except ValueError:
        return False
    return True

def get_admin_effective_ip(request: Request) -> str:
    peer_ip = _normalize_ip(request.client.host if request.client else "")
    # Only honor forwarded IP headers from a trusted local/private proxy or valid Vercel proxy
    if _is_trusted_proxy_peer(peer_ip):
        for hdr in ("x-vercel-forwarded-for", "cf-connecting-ip", "x-forwarded-for", "x-real-ip"):
            norm = _normalize_ip(request.headers.get(hdr, ""))
            if norm:
                return norm
    elif _is_trusted_vercel_proxy(request):
        return _normalize_ip(request.headers.get("x-vercel-forwarded-for", ""))
    return peer_ip

def is_admin_ip_allowed(request: Request) -> tuple[bool, str]:
    effective_ip = get_admin_effective_ip(request)
    allowed_env = os.environ.get("ADMIN_ALLOWED_IPS", "").strip()
    if allowed_env == "*" or settings.get("admin_ip_restriction") is False:
        return True, effective_ip or "remote"

    peer_ip = _normalize_ip(request.client.host if request.client else "")
    if not (_is_trusted_vercel_proxy(request) or _is_trusted_proxy_peer(peer_ip)):
        if not _is_single_ip_allowed(peer_ip):
            return False, peer_ip or "unknown"

    if not _is_single_ip_allowed(effective_ip):
        return False, effective_ip or "unknown"
    return True, effective_ip

def _is_allowed_origin(raw_url: str, request: Request) -> bool:
    try:
        u = urlparse(str(raw_url or "").strip())
        if u.scheme not in ("http", "https") or not u.netloc:
            return False
        origin = f"{u.scheme.lower()}://{u.netloc.lower()}"
        req_host = (request.headers.get("x-forwarded-host") or request.headers.get("host") or "").split(",")[0].strip().lower()
        if req_host and u.netloc.lower() == req_host:
            return True
        allowed = {o.lower().rstrip("/") for o in (_default_cors_origins + _extra_cors)}
        if origin in allowed:
            return True
        if re.fullmatch(r"https://rolea-topup(-[a-z0-9-]+)?\.vercel\.app", origin):
            return True
        return False
    except Exception:
        return False

@app.middleware("http")
async def security_and_no_cache_middleware(request: Request, call_next):
    if request.method.upper() not in _ALLOWED_HTTP_METHODS:
        return JSONResponse(status_code=405, content={"ok": False, "error": "Method not allowed"})

    # 0. Host header injection check
    host_hdr = (request.headers.get("host") or "").strip()
    xf_host_hdr = (request.headers.get("x-forwarded-host") or "").split(",")[0].strip()
    if (host_hdr and not _HOST_HEADER_RE.match(host_hdr)) or (xf_host_hdr and not _HOST_HEADER_RE.match(xf_host_hdr)):
        return JSONResponse(status_code=400, content={"ok": False, "error": "Invalid Host header"})

    path = request.url.path
    raw_qs = request.url.query or ""
    norm_path, suspicious_path = _normalize_request_path(path)
    eff_ip = get_admin_effective_ip(request) or "unknown"

    # 0b. Temporary auto-ban check for repeat attack/scanner IPs
    banned, ban_left = _is_scanner_temp_banned(eff_ip)
    if banned:
        return JSONResponse(
            status_code=403,
            headers={"Retry-After": str(ban_left)},
            content={"ok": False, "error": f"IP temporarily blocked due to automated attack/scanning activity ({ban_left}s)."}
        )

    # 0c. Automated hacker tool / vulnerability scanner User-Agent guard
    ua_hdr = str(request.headers.get("user-agent") or "")
    ua_match = _HACKER_UA_RE.search(ua_hdr)
    if ua_match:
        _record_hacker_strike(eff_ip, f"Blocked Hacker Tool UA ({ua_match.group(0)})", norm_path)
        return JSONResponse(status_code=403, content={"ok": False, "error": "Automated security scanners are blocked."})

    # 1. Path normalization, traversal, backslash, encoding evasion & null-byte guard
    if suspicious_path or ".." in raw_qs or "\x00" in raw_qs or "%00" in raw_qs.lower():
        _record_hacker_strike(eff_ip, "Path Traversal / Null-Byte Evasion", path[:80])
        return JSONResponse(status_code=400, content={"ok": False, "error": "Invalid request path"})

    # 1b. Block probing of sensitive files / dotfiles & common hacker exploit honeypot paths
    if _is_sensitive_probe_path(norm_path) or _is_hacker_probe_path(norm_path):
        _record_hacker_strike(eff_ip, "Sensitive/Exploit Path Probe", norm_path[:80])
        return JSONResponse(status_code=403, content={"ok": False, "error": "Access denied"})

    # 1c. WAF signature check on URL path, query string, and spoofable headers
    waf_qs = _detect_web_attack_payload(raw_qs) or _detect_web_attack_payload(path) or _detect_web_attack_payload(request.headers.get("referer") or "")
    if waf_qs:
        _record_hacker_strike(eff_ip, f"WAF Signature ({waf_qs})", norm_path[:80])
        return JSONResponse(status_code=403, content={"ok": False, "error": "Attack signature blocked by WAF"})

    # 2. Request payload size guard (Anti-Payload Flood)
    cl_hdr = request.headers.get("content-length")
    if cl_hdr:
        try:
            cl_val = int(cl_hdr)
            is_upload = norm_path in ("/api/admin/upload-banner", "/api/admin/games/upload-logo")
            max_bytes = MAX_UPLOAD_BODY_BYTES if is_upload else MAX_JSON_BODY_BYTES
            if cl_val > max_bytes or cl_val < 0:
                return JSONResponse(status_code=413, content={"ok": False, "error": "Payload too large"})
        except ValueError:
            return JSONResponse(status_code=400, content={"ok": False, "error": "Invalid Content-Length"})

    # 3. Anti-DDoS sliding-window rate limiter per client IP (using canonicalized path)
    ok_rate, retry_after = _check_rate_limit(eff_ip, norm_path)
    if not ok_rate:
        return JSONResponse(
            status_code=429,
            headers={"Retry-After": str(retry_after)},
            content={"ok": False, "error": f"Too many requests. Please wait {retry_after}s and try again."}
        )

    is_admin_route = (
        norm_path == "/admin"
        or norm_path.startswith("/admin/")
        or norm_path.startswith("/api/admin")
        or norm_path in ("/admin.html", "/admin_login.html")
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
                    f"Attempted access to {norm_path} outside Home WiFi (192.168.100.x)"
                )
            if norm_path.startswith("/api/"):
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

    # Strict CSRF Origin / Sec-Fetch-Site check on admin mutating endpoints
    if request.method.upper() in _ADMIN_CSRF_MUTATION_METHODS and norm_path.startswith("/api/admin"):
        sec_fetch_site = (request.headers.get("sec-fetch-site") or "").strip().lower()
        origin_hdr = request.headers.get("origin") or request.headers.get("referer")
        if sec_fetch_site == "cross-site" or (origin_hdr and not _is_allowed_origin(origin_hdr, request)):
            return JSONResponse(status_code=403, content={"ok": False, "error": "CSRF origin validation failed"})

    # Enforce strict server-side session verification for Admin APIs and Admin Console
    if (norm_path == "/api/admin" or norm_path.startswith("/api/admin/")) and norm_path not in ("/api/admin/login", "/api/admin/forgot-password", "/api/admin/verify-reset-code", "/api/admin/reset-password"):
        if not verify_admin_session(request):
            return JSONResponse(
                status_code=401,
                content={"ok": False, "error": "Unauthorized. Admin session required."}
            )
    elif norm_path in ("/admin", "/admin.html"):
        if not verify_admin_session(request):
            return RedirectResponse(url="/admin/login", status_code=302)

    response = await call_next(request)
    if norm_path.startswith("/api/") or norm_path.endswith((".js", ".css", ".html")) or norm_path in ("/", "/spin", "/admin", "/admin/login", "/signin", "/game/roblox", "/my-account", "/check-order") or response.headers.get("content-type", "").startswith("text/html"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
    response.headers["X-DNS-Prefetch-Control"] = "off"
    response.headers["Content-Security-Policy"] = "frame-ancestors 'self'; object-src 'none'; base-uri 'self'"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin-allow-popups"
    if _is_https_request(request):
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

@app.exception_handler(json.JSONDecodeError)
async def json_decode_exception_handler(request: Request, exc: json.JSONDecodeError):
    return JSONResponse(status_code=400, content={"ok": False, "error": "Invalid JSON payload"})

_default_cors_origins = [
    "https://rolea-topup.vercel.app",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://51.81.90.228:35507",
]
_extra_cors = [o.strip() for o in os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_default_cors_origins + _extra_cors,
    allow_origin_regex=r"^https://rolea-topup(-[a-z0-9-]+)?\.vercel\.app$",
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Auth-Token", "X-Requested-With"],
)
app.add_middleware(MaxBodySizeMiddleware)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(telegram_polling_loop())
    asyncio.create_task(robux_balance_auto_sync_loop())

# ==========================================
# PUBLIC STORE APIS
# ==========================================

def _cached_json_response(payload: Any, cache_state: str) -> JSONResponse:
    return JSONResponse(
        content=payload,
        headers={
            "X-Cache": cache_state,
            "X-Cache-Backend": cache_backend_name(),
        },
    )


@app.get("/api/settings")
async def get_public_settings():
    data, state = cache_aside_get(
        "rolea:settings:public",
        300,
        lambda: {
            "ok": True,
            "store_name": settings.get("store_name"),
            "telegram_handle": settings.get("telegram_handle"),
            "khqr_merchant_name": settings.get("khqr_merchant_name"),
            "home_banner": settings.get("home_banner", "/media/banner1.webp"),
            "roblox_banner": settings.get("roblox_banner", "/media/roblox-banner.webp"),
            "google_client_id": settings.get("google_client_id", "220196407393-n5m72vbjquni5g4uuo9bfpdrmmn41c24.apps.googleusercontent.com"),
            "turnstile_site_key": _get_turnstile_config()[0] if _get_turnstile_config()[1] else ""
        },
    )
    return _cached_json_response(data, state)

@app.get("/api/games")
async def get_games():
    data, state = cache_aside_get("rolea:games:all", 300, lambda: {"ok": True, "games": games})
    return _cached_json_response(data, state)

@app.get("/api/packages")
async def get_public_packages(game: Optional[str] = None):
    cache_key = f"rolea:packages:{game or 'all'}"
    data, state = cache_aside_get(
        cache_key,
        300,
        lambda: {"ok": True, "packages": [p for p in packages if (not game or p.get("game", "roblox") == game) and p.get("ok") != 0]},
    )
    return _cached_json_response(data, state)

@app.get("/api/game/{game_id}")
async def get_game_detail(game_id: str):
    cache_key = f"rolea:game:{game_id}"
    cached = cache_get(cache_key)
    if cached is not None:
        return _cached_json_response(cached, "HIT")
    g = games.get(game_id)
    if not g:
        return JSONResponse(status_code=404, content={"ok": False, "error": "Game not found"})
    pkgs = [p for p in packages if p.get("game", "roblox") == game_id and p.get("ok") != 0]
    payload = {"ok": True, "game": g, "packages": pkgs}
    cache_set(cache_key, payload, 300)
    return _cached_json_response(payload, "MISS")

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
        r_key = f"rolea:roblox_user:{query.lower()}"
        cached_u = cache_get(r_key)
        if cached_u is not None:
            return _cached_json_response(cached_u, "HIT")
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
                    payload = {
                        "ok": True,
                        "username": u["name"],
                        "display_name": u.get("displayName") or u["name"],
                        "roblox_id": str(u["id"]),
                        "avatar": avatar or "https://tr.rbxcdn.com/30DAY-AvatarHeadshot-150x150-Png/150/150/AvatarHeadshot/Png/noFilter"
                    }
                    cache_set(r_key, payload, 600)
                    return _cached_json_response(payload, "MISS")
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
    av_key = f"rolea:roblox_avatar:{user_id}"
    cached_av = cache_get(av_key)
    if cached_av is not None:
        return _cached_json_response(cached_av, "HIT")
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            av_res = await client.get(
                f"https://thumbnails.roblox.com/v1/users/avatar-headshot?userIds={user_id}&size=150x150&format=Png&isCircular=false"
            )
            av_data = av_res.json()
            if av_data and av_data.get("data") and len(av_data["data"]) > 0:
                img_url = av_data["data"][0].get("imageUrl")
                if img_url:
                    payload = {"avatar": img_url}
                    cache_set(av_key, payload, 900)
                    return _cached_json_response(payload, "MISS")
    except Exception:
        pass
    return {"avatar": "https://tr.rbxcdn.com/30DAY-AvatarHeadshot-150x150-Png/150/150/AvatarHeadshot/Png/noFilter"}

# ==========================================
# ==========================================
# LUCKY SPIN ROBUX APIS (PUBLIC & ADMIN)
# ==========================================

def _finalize_spin_win_order(username: str, roblox_id: Optional[str], avatar: str, display_name: str, pay_method: str, spin_id: str, slice_obj: Dict[str, Any], user_obj: Optional[Dict[str, Any]], guard_triggered: bool) -> tuple[Optional[str], Optional[str]]:
    robux_won = int(slice_obj.get("robux", 0))
    now_iso = datetime.now(timezone.utc).isoformat()
    order_id = None
    receipt_token = None
    clean_user = (username or "").strip().lstrip("@")
    fallback_buyer = (user_obj["username"] if user_obj else None) or clean_user or "Lucky Player"

    if robux_won > 0:
        order_id = spin_id
        receipt_token = secrets.token_hex(16)
        new_order = {
            "order_id": order_id,
            "token": receipt_token,
            "user_id": user_obj["id"] if user_obj else None,
            "buyer_account": fallback_buyer,
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
            "player_id": clean_user,
            "roblox_username": clean_user,
            "display_name": display_name or fallback_buyer,
            "roblox_id": roblox_id,
            "avatar": avatar or "/media/robux-coin.svg",
            "profile_url": f"https://www.roblox.com/users/{roblox_id}/profile" if roblox_id else "",
            "status": "paid",
            "step": "unclaimed",
            "paid": True,
            "delivered": False,
            "claim_submitted": False,
            "telegram_alerted": False,
            "claim_note": "",
            "created_at": now_iso,
            "label": f"Lucky Spin Winner ({robux_won} R$) — Waiting user claim"
        }
        orders.insert(0, new_order)
        _prune_orders_safe(500)
        save_orders()

    hist_entry = {
        "spin_id": spin_id,
        "username": fallback_buyer,
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
    return order_id, receipt_token

@app.get("/api/spin/config")
async def get_public_spin_config():
    def _build_spin_config():
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

    data, state = cache_aside_get("rolea:spin:config", 120, _build_spin_config)
    return _cached_json_response(data, state)

@app.post("/api/spin/create-ticket")
async def create_spin_ticket(request: Request):
    if not spin_data.get("enabled", True):
        return JSONResponse(status_code=400, content={"ok": False, "error": "Lucky Spin Robux is temporarily disabled by Admin."})

    body = await request.json() if (await request.body()) else {}
    if not isinstance(body, dict):
        return JSONResponse(status_code=400, content={"ok": False, "error": "Invalid JSON payload"})
    current_user = get_user_from_req(request)
    username = _sanitize_plain(body.get("username") or "", 60).lstrip("@")
    pay_method = str(body.get("payment_method") or "wallet").lower().strip()
    roblox_id = _sanitize_plain(body.get("roblox_id") or "", 40) or None
    display_name = _sanitize_plain(body.get("display_name") or username or (current_user["username"] if current_user else "Lucky Player"), 60)
    raw_avatar = str(body.get("avatar") or "").strip()
    avatar = raw_avatar if _is_safe_url(raw_avatar) else "/media/robux-coin.svg"

    if pay_method not in ("wallet", "khqr"):
        return JSONResponse(status_code=400, content={"ok": False, "error": "Invalid payment method"})

    client_ip = get_admin_effective_ip(request)
    blocked, b_reason = is_blacklisted(player_id=username or None, username=username or None, ip=client_ip)
    if blocked:
        return JSONResponse(status_code=403, content={"ok": False, "error": f"Account blocked: {b_reason}"})

    price = round(float(spin_data.get("spin_price_usd", 0.50)), 2)
    if not math.isfinite(price) or price < 0.05:
        return JSONResponse(status_code=400, content={"ok": False, "error": "Invalid spin ticket configuration."})

    spin_id = "SPIN" + secrets.token_hex(4).upper()

    if pay_method == "wallet":
        if not current_user:
            return JSONResponse(status_code=401, content={"ok": False, "error": "Please sign in to spin using your Rolea Wallet balance."})
        async with _tx_lock:
            wg_ok, wg_msg = _check_and_enforce_wallet_guard(current_user, price)
            if not wg_ok:
                return JSONResponse(status_code=403, content={"ok": False, "error": wg_msg})
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
            order_id, receipt_token = _finalize_spin_win_order(username, roblox_id, avatar, display_name, "Rolea Wallet", spin_id, sl, current_user, roll["guard_triggered"])
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
                "receipt_token": receipt_token,
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

    if len(pending_spin_tickets) >= 2000:
        unpaid_keys = [k for k, v in pending_spin_tickets.items() if not v.get("paid") or v.get("spun")]
        for k in unpaid_keys[:500]:
            pending_spin_tickets.pop(k, None)
        while len(pending_spin_tickets) >= 2000:
            oldest_k = next(iter(pending_spin_tickets))
            pending_spin_tickets.pop(oldest_k, None)

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
            verified_paid, v_st = verify_khqr_bank_payment(live, float(tkt.get("amount", 0.50)), expected_order_id=spin_id)
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
                order_id, receipt_token = _finalize_spin_win_order(
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
                    "order_id": order_id,
                    "receipt_token": receipt_token
                }

    return {
        "ok": True,
        "paid": tkt["paid"],
        "spun": tkt["spun"],
        "result": tkt["result"]
    }

@app.post("/api/spin/claim")
async def submit_spin_claim(request: Request):
    body = await request.json() if (await request.body()) else {}
    if not isinstance(body, dict):
        return JSONResponse(status_code=400, content={"ok": False, "error": "Invalid JSON payload"})

    order_id = _sanitize_plain(body.get("order_id"), 48)
    receipt_token = str(body.get("receipt_token") or "").strip()
    roblox_username = _sanitize_plain(body.get("roblox_username"), 60).lstrip("@")
    note = _sanitize_plain(body.get("note"), 180)

    if not order_id or not receipt_token:
        return JSONResponse(status_code=400, content={"ok": False, "error": "Missing spin prize order ID or receipt token."})
    if not roblox_username or len(roblox_username) < 2:
        return JSONResponse(status_code=400, content={"ok": False, "error": "Please enter a valid Roblox username to claim your prize."})

    client_ip = get_admin_effective_ip(request)
    blocked, b_reason = is_blacklisted(player_id=roblox_username, username=roblox_username, ip=client_ip)
    if blocked:
        return JSONResponse(status_code=403, content={"ok": False, "error": f"Account blocked: {b_reason}"})

    async with _tx_lock:
        order = next((o for o in orders if o.get("order_id") == order_id and o.get("package_id") == "spin_reward"), None)
        if not order:
            return JSONResponse(status_code=404, content={"ok": False, "error": "Spin prize order not found."})
        if order.get("paid") is not True:
            return JSONResponse(status_code=403, content={"ok": False, "error": "Spin ticket payment has not been verified."})
        if not hmac.compare_digest(str(order.get("token") or ""), receipt_token):
            return JSONResponse(status_code=403, content={"ok": False, "error": "Invalid claim receipt token."})
        if order.get("delivered") or order.get("status") in ("completed", "refunded"):
            return JSONResponse(status_code=400, content={"ok": False, "error": "This spin prize order has already been finalized."})

        robux_won = int(order.get("robux_amount", 0))
        if robux_won <= 0:
            return JSONResponse(status_code=400, content={"ok": False, "error": "No Robux prize to claim on this spin."})

        was_submitted = bool(order.get("claim_submitted"))
        order["roblox_username"] = roblox_username
        order["player_id"] = roblox_username
        order["display_name"] = roblox_username
        order["claim_submitted"] = True
        order["telegram_alerted"] = True
        order["claim_note"] = note
        order["claimed_at"] = datetime.now(timezone.utc).isoformat()
        order["status"] = "paid"
        order["step"] = "sending"
        order["delivered"] = False
        order["label"] = f"Claim Submitted for @{roblox_username} ({robux_won} R$)" + (f" · {note}" if note else "")
        save_orders()

        hist_updated = False
        for h in spin_data.get("history", []):
            if h.get("order_id") == order_id:
                h["username"] = roblox_username
                hist_updated = True
                break
        if hist_updated:
            save_spin_data()

    alert_header = "[SPIN CLAIM UPDATED]" if was_submitted else "[SPIN CLAIM SUBMITTED]"
    asyncio.create_task(send_telegram_admin_alert(
        f"<b>{alert_header} User Requesting Robux Prize</b>\n"
        f"Order ID: <code>{html.escape(order_id, quote=False)}</code>\n"
        f"Roblox Account: <code>@{html.escape(roblox_username, quote=False)}</code>\n"
        f"Prize: <b>{robux_won:,} Robux</b>\n"
        + (f"Note: <i>{html.escape(note, quote=False)}</i>\n" if note else "")
        + "Please send Robux in Admin Orders Queue!"
    ))

    return {
        "ok": True,
        "order_id": order_id,
        "roblox_username": roblox_username,
        "robux_amount": robux_won,
        "status": "paid",
        "message": f"Claim request submitted to Admin for @{roblox_username}!"
    }


@app.post("/api/spin/unclaimed")
async def get_unclaimed_spin_rewards(request: Request):
    """Return pending Robux spin prizes owned by the signed-in user or verified local tickets."""
    user = get_user_from_req(request)
    body = await request.json() if (await request.body()) else {}
    raw_tickets = body.get("tickets") if isinstance(body, dict) else []
    token_map: Dict[str, str] = {}
    if isinstance(raw_tickets, list):
        for t in raw_tickets[:60]:
            if isinstance(t, dict) and t.get("order_id") and t.get("token"):
                token_map[str(t["order_id"]).strip()] = str(t["token"]).strip()

    rewards = []
    for o in orders:
        if o.get("package_id") != "spin_reward" or not o.get("paid"):
            continue
        if o.get("delivered") or o.get("status") in ("completed", "refunded"):
            continue
        robux_amt = int(o.get("robux_amount", 0))
        if robux_amt <= 0:
            continue

        oid = str(o.get("order_id") or "")
        tok = str(o.get("token") or "")
        owns_by_user = bool(user and o.get("user_id") == user["id"])
        owns_by_tok = bool(oid in token_map and tok and hmac.compare_digest(tok, token_map[oid]))
        if not owns_by_user and not owns_by_tok:
            continue

        rewards.append({
            "order_id": oid,
            "receipt_token": tok,
            "robux_amount": robux_amt,
            "roblox_username": o.get("roblox_username") or "",
            "claim_submitted": bool(o.get("claim_submitted")),
            "claim_note": o.get("claim_note") or "",
            "payment_method": o.get("payment_method") or "KHQR",
            "created_at": o.get("created_at") or "",
        })
        if len(rewards) >= 30:
            break

    return {"ok": True, "rewards": rewards}

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
    if not isinstance(body, dict):
        return JSONResponse(status_code=400, content={"ok": False, "error": "Invalid JSON payload"})
    ts_ok, ts_err = await _verify_turnstile_if_enabled(request, body)
    if not ts_ok:
        return JSONResponse(status_code=403, content={"ok": False, "error": ts_err})
    username = str(body.get("username") or "").strip()
    email = str(body.get("email") or "").strip().lower()
    password = str(body.get("password") or "")

    if not re.fullmatch(r"[A-Za-z0-9_.-]{3,32}", username):
        return JSONResponse(status_code=400, content={"ok": False, "error": "Username must be 3-32 characters (letters, numbers, _, ., - only)"})
    if email and not _is_valid_email(email):
        return JSONResponse(status_code=400, content={"ok": False, "error": "Invalid email address"})
    if len(password) < 6 or len(password) > 128:
        return JSONResponse(status_code=400, content={"ok": False, "error": "Password must be between 6 and 128 characters"})

    clean_username = username
    clean_email = email

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

    resp = JSONResponse(content={
        "ok": True,
        "token": token,
        "user": {
            "id": new_user["id"],
            "username": new_user["username"],
            "email": new_user["email"],
            "balance": new_user["balance"],
            "avatar": new_user["avatar"]
        }
    })
    resp.set_cookie(
        key="rolea_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=_is_https_request(request),
        path="/",
        max_age=30 * 24 * 3600,
    )
    return resp

@app.post("/api/auth/login")
async def login(request: Request):
    body = await request.json() if (await request.body()) else {}
    if not isinstance(body, dict):
        return JSONResponse(status_code=400, content={"ok": False, "error": "Invalid JSON payload"})
    ts_ok, ts_err = await _verify_turnstile_if_enabled(request, body)
    if not ts_ok:
        return JSONResponse(status_code=403, content={"ok": False, "error": ts_err})
    username = str(body.get("username") or "").strip()
    password = str(body.get("password") or "")

    if not username or not password:
        return JSONResponse(status_code=400, content={"ok": False, "error": "Please enter username and password"})

    client_ip = get_admin_effective_ip(request) or "unknown"
    lookup = username.lower()
    lock_key = f"{client_ip}:{lookup}"
    now_ts = time.time()
    if customer_lockouts.get(lock_key, 0) > now_ts:
        wait_s = max(1, int(customer_lockouts[lock_key] - now_ts))
        return JSONResponse(status_code=429, content={"ok": False, "error": f"Too many failed login attempts. Try again in {wait_s}s."})

    user = next((u for u in users if u.get("username", "").lower() == lookup or (u.get("email") and u.get("email", "").lower() == lookup)), None)
    matched, needs_upgrade = verify_password(password, str(user.get("password_hash") or "")) if user else (False, False)
    if not user or not matched:
        hist = [t for t in customer_failed_attempts.get(lock_key, []) if now_ts - t < 900]
        hist.append(now_ts)
        customer_failed_attempts[lock_key] = hist
        if len(hist) >= 6:
            customer_lockouts[lock_key] = now_ts + 300
            customer_failed_attempts[lock_key] = []
            return JSONResponse(status_code=429, content={"ok": False, "error": "Too many failed login attempts. Account sign-in temporarily locked for 5 minutes."})
        return JSONResponse(status_code=400, content={"ok": False, "error": "Invalid username or password"})

    customer_failed_attempts.pop(lock_key, None)
    customer_lockouts.pop(lock_key, None)
    if needs_upgrade or "password_plain" in user:
        user["password_hash"] = hash_password(password)
        user.pop("password_plain", None)
        save_users()

    token = secrets.token_hex(32)
    sessions[token] = {
        "userId": user["id"],
        "expiresAt": int((time.time() + 30 * 24 * 3600) * 1000)
    }

    resp = JSONResponse(content={
        "ok": True,
        "token": token,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "email": user["email"],
            "balance": user["balance"],
            "avatar": user["avatar"]
        }
    })
    resp.set_cookie(
        key="rolea_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=_is_https_request(request),
        path="/",
        max_age=30 * 24 * 3600,
    )
    return resp

# Password Reset OTP Store (in-memory, salted SHA-256)
customer_reset_otps: Dict[str, Dict[str, Any]] = {}
customer_reset_rate: Dict[str, List[float]] = {}

@app.post("/api/auth/forgot-password")
async def customer_forgot_password(request: Request):
    client_ip = get_admin_effective_ip(request) or "unknown"
    now_ts = time.time()
    recent = [t for t in customer_reset_rate.get(client_ip, []) if now_ts - t < 900]
    if len(recent) >= 8:
        return JSONResponse(status_code=429, content={"ok": False, "error": "Too many reset requests. Please try again in 15 minutes."})
    recent.append(now_ts)
    customer_reset_rate[client_ip] = recent

    body = await request.json() if (await request.body()) else {}
    if not isinstance(body, dict):
        return JSONResponse(status_code=400, content={"ok": False, "error": "Invalid JSON payload"})
    ts_ok, ts_err = await _verify_turnstile_if_enabled(request, body)
    if not ts_ok:
        return JSONResponse(status_code=403, content={"ok": False, "error": ts_err})
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
    if not isinstance(body, dict):
        return JSONResponse(status_code=400, content={"ok": False, "error": "Invalid JSON payload"})
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
    if not isinstance(body, dict):
        return JSONResponse(status_code=400, content={"ok": False, "error": "Invalid JSON payload"})
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
                    verified = ui_data.get("email_verified") is True
                    if verified and aud and (not expected_cid or aud == expected_cid):
                        email = str(ui_data.get("email") or "").strip().lower()
                        name = _sanitize_plain(ui_data.get("name") or ui_data.get("given_name") or "", 60)
                        raw_pic = str(ui_data.get("picture") or "").strip()
                        avatar = raw_pic if _is_safe_url(raw_pic, allow_relative=False) else ""
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
    elif "rolea_token" in request.cookies:
        token = request.cookies.get("rolea_token", "").strip()
    if token and token in sessions:
        del sessions[token]
    resp = JSONResponse(content={"ok": True})
    resp.delete_cookie("rolea_token", path="/")
    return resp

@app.post("/api/auth/profile/update")
async def update_customer_profile(request: Request):
    user = get_user_from_req(request)
    if not user:
        return JSONResponse(status_code=401, content={"ok": False, "error": "Not authenticated"})
    body = await request.json() if (await request.body()) else {}
    if not isinstance(body, dict):
        return JSONResponse(status_code=400, content={"ok": False, "error": "Invalid JSON payload"})
    email = body.get("email")
    telegram = body.get("telegram")
    current_password = str(body.get("current_password") or "")
    new_password = str(body.get("new_password") or "")

    if email is not None and str(email).strip():
        clean_email = str(email).strip().lower()
        if not _is_valid_email(clean_email):
            return JSONResponse(status_code=400, content={"ok": False, "error": "Invalid email address"})
        conflict = next((u for u in users if u.get("id") != user.get("id") and (u.get("email") or "").lower() == clean_email), None)
        if conflict:
            return JSONResponse(status_code=400, content={"ok": False, "error": "Email already in use by another account"})
        user["email"] = clean_email
    if telegram is not None:
        user["telegram"] = re.sub(r"[^A-Za-z0-9_]", "", str(telegram).strip().lstrip("@"))[:40]

    if new_password:
        if len(new_password) < 6 or len(new_password) > 128:
            return JSONResponse(status_code=400, content={"ok": False, "error": "New password must be between 6 and 128 characters long"})
        if user.get("password_hash"):
            if not current_password:
                return JSONResponse(status_code=400, content={"ok": False, "error": "Current password is required to change your password"})
            ok_pw, _ = verify_password(current_password, str(user.get("password_hash") or ""))
            if not ok_pw:
                return JSONResponse(status_code=400, content={"ok": False, "error": "Current password is incorrect"})
        user["password_hash"] = hash_password(new_password)
        user.pop("password_plain", None)
        # Revoke other sessions of this user
        auth_hdr = request.headers.get("authorization") or ""
        cur_tok = auth_hdr[7:].strip() if auth_hdr.startswith("Bearer ") else (request.headers.get("x-auth-token") or request.cookies.get("rolea_token") or "").strip()
        stale = [tok for tok, s in sessions.items() if s.get("userId") == user["id"] and tok != cur_tok]
        for tok in stale:
            sessions.pop(tok, None)

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
    # Only return orders owned by this authenticated user_id (never expose guest orders via username match)
    my_orders = [
        o for o in orders
        if o.get("user_id") == user["id"]
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

    if not math.isfinite(order_amount) or order_amount <= 0:
        return JSONResponse(status_code=400, content={"ok": False, "error": "Invalid order amount"})

    cp = next((c for c in coupons if c.get("code", "").upper() == code.strip().upper() and c.get("enabled")), None)
    if not cp:
        return JSONResponse(status_code=404, content={"ok": False, "error": "Invalid or inactive promo code"})

    if cp.get("max_uses") and cp.get("used_count", 0) >= cp["max_uses"]:
        return JSONResponse(status_code=400, content={"ok": False, "error": "Promo code usage limit has been reached"})

    if order_amount < float(cp.get("min_spend", 0)):
        return JSONResponse(status_code=400, content={"ok": False, "error": f"Minimum order of ${float(cp.get('min_spend', 0)):.2f} required for this coupon"})

    val = float(cp.get("value", 0))
    if not math.isfinite(val) or val <= 0:
        return JSONResponse(status_code=400, content={"ok": False, "error": "Invalid promo code configuration"})
    if cp.get("type") == "percentage":
        discount = order_amount * (min(100.0, val) / 100.0)
    else:
        discount = val

    discount = min(discount, max(0.0, order_amount - 0.05))
    discount = round(discount, 2)
    new_amount = round(max(0.05, order_amount - discount), 2)

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
    def _build_reviews():
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

    data, state = cache_aside_get("rolea:reviews:approved", 300, _build_reviews)
    return _cached_json_response(data, state)

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
    def _build_live_proof():
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
        return {"ok": True, "live_proof": live_list}

    data, state = cache_aside_get("rolea:live_proof", 45, _build_live_proof)
    return _cached_json_response(data, state)


@app.get("/api/admin/cache/status")
async def admin_cache_status(request: Request):
    if not verify_admin_session(request):
        return JSONResponse(status_code=401, content={"ok": False, "error": "Unauthorized"})
    hits = int(_cache_stats.get("hits", 0))
    misses = int(_cache_stats.get("misses", 0))
    total = hits + misses
    hit_rate = round((hits / total) * 100.0, 1) if total > 0 else 0.0
    r = _get_redis()
    redis_keys = None
    if r is not None:
        try:
            redis_keys = sum(1 for _ in r.scan_iter(match="rolea:*", count=200))
        except Exception:
            redis_keys = None
    return {
        "ok": True,
        "strategy": "cache-aside",
        "backend": "redis" if r is not None else "memory-fallback",
        "redis_configured": bool(_get_redis_url()),
        "redis_connected": r is not None,
        "cached_keys": redis_keys if redis_keys is not None else len(_mem_cache),
        "hits": hits,
        "misses": misses,
        "hit_rate_pct": hit_rate,
        "writes": int(_cache_stats.get("writes", 0)),
        "invalidations": int(_cache_stats.get("invalidations", 0)),
        "errors": int(_cache_stats.get("errors", 0)),
        "last_error": _cache_stats.get("last_error", ""),
    }


@app.post("/api/admin/cache/flush")
async def admin_cache_flush(request: Request):
    if not verify_admin_session(request):
        return JSONResponse(status_code=401, content={"ok": False, "error": "Unauthorized"})
    cache_delete("rolea:*")
    return {"ok": True, "message": "Cache flushed successfully."}

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
        ts_ok, ts_err = await _verify_turnstile_if_enabled(request, body)
        if not ts_ok:
            return JSONResponse(status_code=403, content={"ok": False, "error": ts_err})

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

        anti_ok, anti_msg = _check_unpaid_order_anti_bypass(client_ip, game_key, pkg.get("id"), body.get("player_id") or "")
        if not anti_ok:
            return JSONResponse(status_code=429, content={"ok": False, "error": anti_msg})

        now = datetime.now(timezone.utc)
        raw_ref = str(body.get("checkout_ref") or "").strip()
        if re.fullmatch(r"PR[A-Za-z0-9_-]{8,38}", raw_ref) and not any(o.get("order_id") == raw_ref for o in orders):
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
            matched_cp = None
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
                        matched_cp = cp

            # 1-Click Wallet Checkout (atomic inside _tx_lock)
            if body.get("payment_method") == "wallet":
                if not current_user:
                    return JSONResponse(status_code=401, content={"ok": False, "error": "Please log in to pay with your Rolea Wallet balance"})
                wg_ok, wg_msg = _check_and_enforce_wallet_guard(current_user, amount)
                if not wg_ok:
                    return JSONResponse(status_code=403, content={"ok": False, "error": wg_msg})
                if float(current_user.get("balance", 0.0)) < amount:
                    return JSONResponse(status_code=400, content={"ok": False, "error": f"Insufficient wallet balance (${float(current_user.get('balance', 0)):.2f} USD). Please top up first."})

                if matched_cp is not None:
                    matched_cp["used_count"] = matched_cp.get("used_count", 0) + 1
                    save_coupons()

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

            if matched_cp is not None:
                matched_cp["used_count"] = matched_cp.get("used_count", 0) + 1
                save_coupons()

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
        t_input = _sanitize_plain(body.get("player_id") or "", 180)
        safe_uname = _sanitize_plain(body.get("username") or t_input, 60)
        tt_link = t_input if (t_input.startswith("http://") or t_input.startswith("https://")) else (f"https://www.tiktok.com/@{t_input.replace('@', '')}" if t_input else "")
        new_order = {
            "order_id": order_id,
            "khqrpay_id": khqrpay_id,
            "token": token,
            "user_id": current_user["id"] if current_user else None,
            "buyer_account": current_user["username"] if current_user else safe_uname,
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
            "player_id": t_input,
            "roblox_username": safe_uname,
            "display_name": _sanitize_plain(safe_uname or "Player", 60) if not is_smm else "TikTok Customer",
            "roblox_id": None if is_smm else str(abs(sum(ord(c) for c in (t_input or "12345678")))),
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
        _record_unpaid_order_attempt(client_ip, new_order["order_id"], game_key, pkg.get("id"), t_input)
        _prune_orders_safe(500)
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

    if order.get("khqrpay_id") and not order.get("paid") and order.get("status") not in ("completed", "expired", "failed", "refunded"):
        live = await check_khqrpay_status(order["khqrpay_id"])
        if live:
            verified_paid, v_st = verify_khqr_bank_payment(live, float(order.get("amount", 0)), expected_order_id=order_id)
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
    if not isinstance(body, dict):
        return JSONResponse(status_code=400, content={"ok": False, "error": "Invalid JSON payload"})
    order_id = str(body.get("order_id") or "").strip()
    username = str(body.get("username") or "").strip()
    receipt_token = str(body.get("receipt_token") or "").strip()

    order = next((o for o in orders if o.get("order_id") == order_id), None)
    if not order:
        return JSONResponse(status_code=404, content={"ok": False, "error": "Order not found. Please verify your Order ID."})

    stored_tok = str(order.get("token") or "")
    token_match = bool(receipt_token and stored_tok and hmac.compare_digest(stored_tok, receipt_token))
    user_match = bool(username and str(order.get("roblox_username") or "").lower() == username.lower())

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
    if not isinstance(body, dict):
        return {"ok": True, "orders": []}
    refs = body.get("orders")
    if not isinstance(refs, list):
        return {"ok": True, "orders": []}

    token_map = {str(r["order_id"]).strip(): str(r["token"]).strip() for r in refs[:60] if isinstance(r, dict) and r.get("order_id") and r.get("token")}
    matched = [
        o for o in orders
        if o.get("order_id") in token_map and o.get("token") and hmac.compare_digest(str(o.get("token")), token_map[o.get("order_id")])
    ]
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
    totp_code = str(body.get("totp_code") or "").strip()

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
            return {"ok": False, "require_pin": True, "require_totp": bool(admin_security.get("totp_enabled")), "message": "Enter your 2FA Security PIN"}
        pin_salt = admin_security.get("pin_salt", "")
        pin_hash = admin_security.get("pin_hash", "")
        if not hmac.compare_digest(hash_admin_secret(pin, pin_salt), pin_hash):
            attempts = [t for t in admin_failed_attempts.get(client_ip, []) if now_ts - t < 900]
            attempts.append(now_ts)
            admin_failed_attempts[client_ip] = attempts
            log_admin_security_event("Failed 2FA PIN", client_ip, username, "failed", "Incorrect Security PIN")
            return JSONResponse(status_code=401, content={"ok": False, "error": "Incorrect 2FA Security PIN."})

    # Optional Google Authenticator (TOTP) 2FA check
    if admin_security.get("totp_enabled"):
        if not totp_code:
            return {"ok": False, "require_totp": True, "require_pin": bool(admin_security.get("pin_enabled")), "message": "Enter your 6-digit Authenticator (TOTP) code"}
        totp_sec = _decrypt_secret(admin_security.get("totp_secret_enc", ""))
        if not _verify_totp_code(totp_sec, totp_code):
            attempts = [t for t in admin_failed_attempts.get(client_ip, []) if now_ts - t < 900]
            attempts.append(now_ts)
            admin_failed_attempts[client_ip] = attempts
            log_admin_security_event("Failed 2FA TOTP", client_ip, username, "failed", "Incorrect Authenticator TOTP code")
            return JSONResponse(status_code=401, content={"ok": False, "error": "Incorrect Authenticator (TOTP) code."})

    # Success: reset failed attempts & create cryptographic session
    admin_failed_attempts.pop(client_ip, None)
    admin_lockouts.pop(client_ip, None)
    cleanup_expired_admin_sessions()

    raw_token = secrets.token_urlsafe(32)
    token_hash = hash_session_token(raw_token)
    timeout_hours = int(admin_security.get("session_timeout_hours", 24))
    expires_ms = int((now_ts + timeout_hours * 3600) * 1000)

    sessions_map = admin_security.setdefault("sessions", {})
    sessions_map[token_hash] = {
        "token_id": token_hash[:10],
        "ip": client_ip,
        "user_agent": str(request.headers.get("user-agent", "Unknown"))[:90],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": expires_ms
    }
    if len(sessions_map) > 20:
        sorted_s = sorted(sessions_map.items(), key=lambda kv: str(kv[1].get("created_at") or ""))
        for old_k, _ in sorted_s[:len(sessions_map) - 20]:
            sessions_map.pop(old_k, None)
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
        secure=_is_https_request(request),
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
    client_ip = get_admin_effective_ip(request) or "unknown"
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
    client_ip = get_admin_effective_ip(request) or "unknown"
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
    client_ip = get_admin_effective_ip(request) or "unknown"
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
        "totp_enabled": bool(admin_security.get("totp_enabled", False)),
        "wallet_daily_limit_usd": float(admin_security.get("wallet_daily_limit_usd", 100.0)),
        "wallet_velocity_max_tx_5m": int(admin_security.get("wallet_velocity_max_tx_5m", 8)),
        "session_timeout_hours": int(admin_security.get("session_timeout_hours", 24)),
        "telegram_login_alert": bool(admin_security.get("telegram_login_alert", True)),
        "active_sessions": sessions_list,
        "login_logs": logs[:20],
        "audit_logs": admin_security.get("audit_logs", [])[:40],
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

    client_ip = get_admin_effective_ip(request) or "unknown"
    log_admin_security_event("Credentials Updated", client_ip, new_user, "success", "Admin password & username updated; other sessions revoked")
    _record_admin_audit(request, "Admin Credentials Changed", new_user, "Username/password rotated; other sessions revoked")
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
    if "wallet_daily_limit_usd" in body and body["wallet_daily_limit_usd"] is not None:
        try:
            admin_security["wallet_daily_limit_usd"] = max(0.0, round(float(body["wallet_daily_limit_usd"]), 2))
        except (ValueError, TypeError):
            pass
    if "wallet_velocity_max_tx_5m" in body and body["wallet_velocity_max_tx_5m"] is not None:
        try:
            admin_security["wallet_velocity_max_tx_5m"] = max(2, min(100, int(body["wallet_velocity_max_tx_5m"])))
        except (ValueError, TypeError):
            pass

    client_ip = get_admin_effective_ip(request) or "unknown"
    log_admin_security_event("Policy Updated", client_ip, admin_security.get("username", "admin"), "success", f"2FA PIN: {'ON' if pin_enabled else 'OFF'}, WalletLimit: ${admin_security['wallet_daily_limit_usd']}")
    _record_admin_audit(request, "Security Policy Updated", "policy", f"PIN={'ON' if pin_enabled else 'OFF'}, DailyWalletLimit=${admin_security['wallet_daily_limit_usd']}")
    save_admin_security()
    return {"ok": True, "message": "Security policies saved!"}

@app.post("/api/admin/security/totp/setup")
async def admin_totp_setup(request: Request):
    secret_b32 = _generate_totp_secret()
    admin_security["totp_pending_secret_enc"] = _encrypt_secret(secret_b32)
    save_admin_security()
    qr_url, uri = _totp_qr_data_url(secret_b32, admin_security.get("username", "admin"))
    return {
        "ok": True,
        "qr_data_url": qr_url,
        "manual_secret": secret_b32,
        "otpauth_uri": uri
    }

@app.post("/api/admin/security/totp/verify")
async def admin_totp_verify(request: Request):
    body = await request.json() if (await request.body()) else {}
    code = str(body.get("code") or "").strip()
    pending_enc = admin_security.get("totp_pending_secret_enc", "")
    secret_b32 = _decrypt_secret(pending_enc)
    if not secret_b32:
        return JSONResponse(status_code=400, content={"ok": False, "error": "Please click Generate Authenticator QR first."})
    if not _verify_totp_code(secret_b32, code):
        return JSONResponse(status_code=400, content={"ok": False, "error": "Invalid 6-digit code. Check phone time & try again."})
    admin_security["totp_secret_enc"] = _encrypt_secret(secret_b32)
    admin_security["totp_pending_secret_enc"] = ""
    admin_security["totp_enabled"] = True
    save_admin_security()
    _record_admin_audit(request, "TOTP 2FA Enabled", admin_security.get("username", "admin"), "Google Authenticator TOTP activated")
    return {"ok": True, "message": "Google Authenticator (TOTP) 2FA enabled!"}

@app.post("/api/admin/security/totp/disable")
async def admin_totp_disable(request: Request):
    body = await request.json() if (await request.body()) else {}
    pw = str(body.get("current_password") or "")
    code = str(body.get("code") or "").strip()
    pw_ok = bool(pw) and hmac.compare_digest(hash_admin_secret(pw, admin_security.get("password_salt", "")), admin_security.get("password_hash", ""))
    totp_sec = _decrypt_secret(admin_security.get("totp_secret_enc", ""))
    code_ok = bool(code) and _verify_totp_code(totp_sec, code)
    if not (pw_ok or code_ok):
        return JSONResponse(status_code=403, content={"ok": False, "error": "Enter your current password or current TOTP code to disable TOTP."})
    admin_security["totp_enabled"] = False
    admin_security["totp_secret_enc"] = ""
    admin_security["totp_pending_secret_enc"] = ""
    save_admin_security()
    _record_admin_audit(request, "TOTP 2FA Disabled", admin_security.get("username", "admin"), "Authenticator 2FA turned off")
    return {"ok": True, "message": "Authenticator (TOTP) 2FA disabled."}

@app.post("/api/admin/security/revoke-sessions")
async def admin_revoke_sessions(request: Request):
    current_hash = verify_admin_session(request)
    if current_hash and current_hash in admin_security.get("sessions", {}):
        curr = admin_security["sessions"][current_hash]
        admin_security["sessions"] = {current_hash: curr}
    else:
        admin_security["sessions"] = {}
    client_ip = get_admin_effective_ip(request) or "unknown"
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
    if not isinstance(body, dict):
        return JSONResponse(status_code=400, content={"ok": False, "error": "Invalid JSON payload"})
    order_id = body.get("order_id")
    action = body.get("action")

    async with _tx_lock:
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
            try:
                deduct_inventory_on_deliver(order)
            except Exception as eInv:
                print("Inventory deduction error:", eInv)
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
        if not _is_safe_url(url):
            return JSONResponse(status_code=400, content={"ok": False, "error": "Invalid image URL"})
        if gid and gid in games:
            games[gid]["logo"] = url
            save_games()
        return {"ok": True, "logo": url}

    if image_base64:
        try:
            m = re.match(r"^data:image/([a-zA-Z0-9+]+);base64,(.+)$", str(image_base64).strip())
            data = m.group(2) if m else str(image_base64).strip()
            buf = base64.b64decode(data, validate=True)
            ext = _validate_image_magic(buf)
            if not ext:
                return JSONResponse(status_code=400, content={"ok": False, "error": "Unsupported or invalid image format (PNG, JPG, WEBP, GIF only)"})
            safe_id = re.sub(r"[^a-zA-Z0-9_-]", "", str(gid or "game"))[:32] or "game"
            filename = f"logo_{safe_id}_{int(time.time() * 1000)}.{ext}"
            with open(MEDIA_DIR / filename, "wb") as f:
                f.write(buf)
            final_logo_url = f"/media/{filename}"
            if gid and gid in games:
                games[gid]["logo"] = final_logo_url
                save_games()
            return {"ok": True, "logo": final_logo_url}
        except Exception:
            return JSONResponse(status_code=400, content={"ok": False, "error": "Invalid image upload payload"})

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
    masked = dict(settings)
    for _sk in _SETTINGS_SECRET_KEYS:
        if masked.get(_sk):
            masked[_sk] = "••••••••"
    return {"ok": True, "settings": masked}

@app.post("/api/admin/settings")
async def admin_save_settings(request: Request):
    body = await request.json() if (await request.body()) else {}
    for key in ["store_name", "telegram_handle", "khqr_merchant_name", "khqr_account", "khqrpay_base_url", "home_banner", "roblox_banner", "google_client_id", "turnstile_site_key"]:
        if key in body and body[key] is not None:
            settings[key] = str(body[key]).strip()
    for sk_key in _SETTINGS_SECRET_KEYS:
        if sk_key in body and body[sk_key] is not None:
            val = str(body[sk_key]).strip()
            if val and val != "••••••••":
                settings[sk_key] = val
    if "telegram_chat_id" in body and body["telegram_chat_id"] is not None:
        settings["telegram_chat_id"] = str(body["telegram_chat_id"]).strip()
    for sm_key in ["smtp_host", "smtp_email", "admin_recovery_email"]:
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
    _record_admin_audit(request, "Store Settings Updated", settings.get("store_name", "store"), "Gateway/Telegram/Turnstile/SMTP settings saved (encrypted at rest)")
    masked = dict(settings)
    for _sk in _SETTINGS_SECRET_KEYS:
        if masked.get(_sk):
            masked[_sk] = "••••••••"
    return {"ok": True, "settings": masked}

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

def _mask_bot_public(b: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(b)
    has_c = bool(out.get("cookie"))
    out["has_cookie"] = has_c
    if has_c:
        out["cookie"] = "••••••••"
    return out

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
        "bots": [_mask_bot_public(b) for b in inventory.get("bots", [])],
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
        "cookie": _encrypt_secret(cookie),
        "group_funds": funds_found,
        "status": status_bot,
        "last_synced": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "notes": notes
    }

    if "bots" not in inventory:
        inventory["bots"] = []
    inventory["bots"].append(new_bot)
    save_inventory()
    _record_admin_audit(request, "Payout Bot Added", name, f"Group #{group_id or '-'} ({funds_found} R$)")

    return {"ok": True, "bot": _mask_bot_public(new_bot), "total_stock": get_total_inventory_stock()}

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
        cookie = _get_bot_cookie(b)
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
        "bots": [_mask_bot_public(b) for b in bots]
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
        "cookie": _encrypt_secret(clean_c),
        "group_funds": funds,
        "status": "active",
        "last_synced": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    inventory["bots"] = [bot_item]
    inventory["manual_stock_enabled"] = False
    save_inventory()
    _record_admin_audit(request, "Roblox Bot Cookie Connected", roblox_username or name, f"Funds: {funds} R$ (cookie encrypted at rest)")

    return {"ok": True, "bot": _mask_bot_public(bot_item), "total_stock": funds}

async def sync_primary_bot_balance() -> Dict[str, Any]:
    global inventory
    bots = inventory.get("bots", [])
    if not bots:
        return {"ok": False, "status_code": 400, "error": "No bot cookie configured to sync"}

    b = bots[0]
    cookie = _get_bot_cookie(b)
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
    return {"ok": True, "bot": _mask_bot_public(res["bot"]), "total_stock": res["total_stock"]}

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
    _record_admin_audit(request, "Blacklist Added", f"{btype}:{clean_target}", reason)
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
    _record_admin_audit(request, "Blacklist Removed", f"{btype}:{clean_target}", "Target unblocked by admin")
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

@app.get("/api/admin/waf")
async def admin_get_waf_status():
    _sync_waf_bans_from_blacklist()
    now_ts = time.time()
    persisted = blacklist.setdefault("waf_bans", {})
    active_bans = []
    dirty = False
    for ip_k, until_ts in list(_scanner_bans.items()):
        if until_ts <= now_ts:
            _scanner_bans.pop(ip_k, None)
            if ip_k in persisted:
                persisted.pop(ip_k, None)
                dirty = True
            continue
        meta = persisted.get(ip_k) or {}
        active_bans.append({
            "ip": ip_k,
            "remaining_sec": max(1, int(until_ts - now_ts)),
            "banned_until": datetime.fromtimestamp(until_ts, tz=timezone.utc).isoformat(),
            "reason": meta.get("reason") or "Automated hacker/WAF scanner detection",
            "strikes": int(meta.get("strikes", 3)),
            "last_seen": meta.get("last_seen", "")
        })
    if dirty:
        save_blacklist()
    active_bans.sort(key=lambda x: x["remaining_sec"], reverse=True)
    waf_logs = [l for l in blacklist.get("logs", []) if l.get("game") == "waf"][:30]
    return {
        "ok": True,
        "active_bans": active_bans,
        "active_ban_count": len(active_bans),
        "tracked_strike_ips": len(_scanner_strikes),
        "recent_waf_logs": waf_logs
    }

@app.post("/api/admin/waf/unban")
async def admin_waf_unban(request: Request):
    body = await request.json() if (await request.body()) else {}
    ip = str(body.get("ip") or "").strip()
    if not ip:
        return JSONResponse(status_code=400, content={"ok": False, "error": "IP address is required"})
    _scanner_bans.pop(ip, None)
    _scanner_strikes.pop(ip, None)
    if isinstance(blacklist.get("waf_bans"), dict):
        blacklist["waf_bans"].pop(ip, None)
        save_blacklist()
    _record_admin_audit(request, "WAF IP Unbanned", ip, "Temporary WAF ban lifted by admin")
    return {"ok": True, "message": f"IP {ip} unbanned from WAF"}

@app.post("/api/admin/waf/ban-permanent")
async def admin_waf_permanent_ban(request: Request):
    body = await request.json() if (await request.body()) else {}
    ip = str(body.get("ip") or "").strip()
    reason = str(body.get("reason") or "Escalated from WAF attack logs").strip()[:140]
    if not ip:
        return JSONResponse(status_code=400, content={"ok": False, "error": "IP address is required"})
    _scanner_bans.pop(ip, None)
    _scanner_strikes.pop(ip, None)
    if isinstance(blacklist.get("waf_bans"), dict):
        blacklist["waf_bans"].pop(ip, None)
    b_ips = blacklist.setdefault("blocked_ips", [])
    if ip not in b_ips:
        b_ips.append(ip)
    blacklist.setdefault("logs", []).insert(0, {
        "id": "blk_" + str(int(time.time() * 1000)),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "target": ip,
        "type": "ip",
        "reason": reason,
        "blocked_by": "Admin (WAF Escalation)"
    })
    save_blacklist()
    _record_admin_audit(request, "WAF IP Permanently Blocked", ip, reason)
    return {"ok": True, "message": f"IP {ip} permanently blacklisted"}

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
            _sanitize_csv_cell(o.get("order_id", "")),
            _sanitize_csv_cell(o.get("created_at") or o.get("date") or ""),
            _sanitize_csv_cell(o.get("player_id") or o.get("roblox_username") or o.get("buyer_account") or ""),
            _sanitize_csv_cell(o.get("product_name") or o.get("game") or "Roblox"),
            _sanitize_csv_cell(o.get("package") or ""),
            o.get("robux_amount") or 0,
            f"{float(o.get('amount') or 0):.2f}",
            _sanitize_csv_cell(o.get("payment_method") or "KHQR"),
            _sanitize_csv_cell(o.get("status") or "pending"),
            _sanitize_csv_cell(o.get("step") or "")
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
    if not isinstance(body, dict):
        return JSONResponse(status_code=400, content={"ok": False, "error": "Invalid JSON payload"})
    btype = body.get("type")
    game_id = body.get("game_id")
    image_base64 = body.get("image_base64")
    image_url = body.get("image_url")
    target_game = game_id or (btype if btype and btype != "home" else None)

    # Home banner
    if not target_game or btype == "home":
        if image_url:
            clean_url = str(image_url).strip()
            if not _is_safe_url(clean_url):
                return JSONResponse(status_code=400, content={"ok": False, "error": "Invalid banner URL"})
            settings["home_banner"] = clean_url
            save_settings()
            return {"ok": True, "banner_url": settings["home_banner"], "type": "home"}
        if image_base64:
            try:
                m = re.match(r"^data:image/([a-zA-Z0-9+]+);base64,(.+)$", str(image_base64).strip())
                data = m.group(2) if m else str(image_base64).strip()
                buf = base64.b64decode(data, validate=True)
                ext = _validate_image_magic(buf)
                if not ext:
                    return JSONResponse(status_code=400, content={"ok": False, "error": "Unsupported or invalid image format (PNG, JPG, WEBP, GIF only)"})
                filename = f"banner_home_{int(time.time() * 1000)}.{ext}"
                with open(MEDIA_DIR / filename, "wb") as f:
                    f.write(buf)
                saved_url = f"/media/{filename}"
                settings["home_banner"] = saved_url
                save_settings()
                return {"ok": True, "banner_url": saved_url, "type": "home"}
            except Exception:
                return JSONResponse(status_code=400, content={"ok": False, "error": "Invalid banner image payload"})
        return JSONResponse(status_code=400, content={"ok": False, "error": "No image data or URL provided"})

    # Game banner
    if target_game not in games:
        return JSONResponse(status_code=404, content={"ok": False, "error": f"Game {target_game} not found"})

    if image_url:
        clean_url = str(image_url).strip()
        if not _is_safe_url(clean_url):
            return JSONResponse(status_code=400, content={"ok": False, "error": "Invalid banner URL"})
        games[target_game]["banner"] = clean_url
        save_games()
        if target_game == "roblox":
            settings["roblox_banner"] = games[target_game]["banner"]
            save_settings()
        return {"ok": True, "banner_url": games[target_game]["banner"], "game_id": target_game}

    if image_base64:
        try:
            m = re.match(r"^data:image/([a-zA-Z0-9+]+);base64,(.+)$", str(image_base64).strip())
            data = m.group(2) if m else str(image_base64).strip()
            buf = base64.b64decode(data, validate=True)
            ext = _validate_image_magic(buf)
            if not ext:
                return JSONResponse(status_code=400, content={"ok": False, "error": "Unsupported or invalid image format (PNG, JPG, WEBP, GIF only)"})
            safe_gid = re.sub(r"[^a-zA-Z0-9_-]", "", str(target_game))[:32] or "game"
            filename = f"banner_{safe_gid}_{int(time.time() * 1000)}.{ext}"
            with open(MEDIA_DIR / filename, "wb") as f:
                f.write(buf)
            saved_url = f"/media/{filename}"
            games[target_game]["banner"] = saved_url
            save_games()
            if target_game == "roblox":
                settings["roblox_banner"] = saved_url
                save_settings()
            return {"ok": True, "banner_url": saved_url, "game_id": target_game}
        except Exception:
            return JSONResponse(status_code=400, content={"ok": False, "error": "Invalid banner image payload"})

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
            "wallet_frozen": bool(u.get("wallet_frozen", False)),
            "wallet_freeze_reason": u.get("wallet_freeze_reason", ""),
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
        if not re.fullmatch(r"[A-Za-z0-9_.-]{3,32}", clean_uname):
            return JSONResponse(status_code=400, content={"ok": False, "error": "Username must be 3-32 characters (letters, numbers, _, ., - only)"})
        conflict = next((u for u in users if u.get("id") != user.get("id") and u.get("username", "").lower() == clean_uname.lower()), None)
        if conflict:
            return JSONResponse(status_code=400, content={"ok": False, "error": "Username already taken by another account"})
        user["username"] = clean_uname

    if "email" in body:
        clean_em = str(body.get("email") or "").strip().lower()
        if clean_em and not _is_valid_email(clean_em):
            return JSONResponse(status_code=400, content={"ok": False, "error": "Invalid email address"})
        user["email"] = clean_em

    password = body.get("password")
    if password and isinstance(password, str) and len(password.strip()) >= 6:
        user["password_hash"] = hash_password(password.strip())
        user.pop("password_plain", None)
        for tok in [t for t, s in sessions.items() if s.get("userId") == user.get("id")]:
            sessions.pop(tok, None)

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
    _record_admin_audit(request, "Customer Account Deleted", str(deleted.get("username") or user_id), f"User ID: {deleted.get('id')}")
    return {"ok": True, "message": f"Account {deleted.get('username')} deleted"}

@app.post("/api/admin/users/toggle-wallet-freeze")
async def admin_toggle_wallet_freeze(request: Request):
    body = await request.json() if (await request.body()) else {}
    user_id = body.get("user_id")
    user = next((u for u in users if u.get("id") == user_id or u.get("username") == user_id), None)
    if not user:
        return JSONResponse(status_code=404, content={"ok": False, "error": "User not found"})
    new_state = not bool(user.get("wallet_frozen", False)) if "frozen" not in body else bool(body["frozen"])
    user["wallet_frozen"] = new_state
    user["wallet_freeze_reason"] = str(body.get("reason") or ("Frozen by Admin" if new_state else "")).strip() if new_state else ""
    save_users()
    _record_admin_audit(request, "Wallet Freeze Toggled", str(user.get("username") or user_id), f"Frozen={new_state}")
    return {"ok": True, "wallet_frozen": new_state, "message": f"Wallet {'frozen' if new_state else 'unfrozen'} for {user.get('username')}"}

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
    _record_admin_audit(request, "Wallet Balance Adjusted", str(user.get("username") or user_id), f"{num:+.2f} USD -> New Bal: ${user['balance']:.2f} ({reason or 'no reason'})")

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
