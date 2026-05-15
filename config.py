"""
config.py — No-Brain-Trade Pro
All settings loaded from environment.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# Force fix for Railway proxy issues
os.environ['NO_PROXY'] = 'api.telegram.org,telegram.org'
os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''

# ── Solana ────────────────────────────────────────────────────
SOLANA_RPC_URL   = os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")
SOLANA_WS_URL    = os.getenv("SOLANA_WS_URL",  "wss://api.mainnet-beta.solana.com")
HELIUS_API_KEY   = os.getenv("HELIUS_API_KEY", "")
BIRDEYE_API_KEY  = os.getenv("BIRDEYE_API_KEY", "")

# ── Telegram ──────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ADMIN_CHAT_ID      = os.getenv("ADMIN_CHAT_ID", "")

# ── Treasury ──────────────────────────────────────────────────
TREASURY_WALLET    = os.getenv("TREASURY_WALLET", "")

# ── Database ──────────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://localhost/nbt")

# Force async driver (fixes Railway's sync URL)
if DATABASE_URL and "postgresql://" in DATABASE_URL and "+asyncpg" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
    print("✅ Converted DATABASE_URL to asyncpg format")

# ── Security ──────────────────────────────────────────────────
ENCRYPTION_KEY     = os.getenv("ENCRYPTION_KEY", "")
SECRET_KEY         = os.getenv("SECRET_KEY", "changeme_in_production")

# ── Subscription ──────────────────────────────────────────────
PRO_PRICE_SOL      = float(os.getenv("PRO_PRICE_SOL", 0.5))
PRO_DURATION_DAYS  = int(os.getenv("PRO_DURATION_DAYS", 30))

# ── Trading ───────────────────────────────────────────────────
DEFAULT_SLIPPAGE_BPS = int(os.getenv("DEFAULT_SLIPPAGE_BPS", 300))
DEFAULT_TRADE_SOL    = float(os.getenv("DEFAULT_TRADE_SOL", 0.1))
MAX_TRADE_SOL        = float(os.getenv("MAX_TRADE_SOL", 10.0))

# ── Scanner / Spike ───────────────────────────────────────────
PUMPFUN_WS_URL       = "wss://pumpportal.fun/api/data"
SPIKE_THRESHOLD_PCT  = float(os.getenv("SPIKE_THRESHOLD_PCT", 150))
SPIKE_WINDOW_SECONDS = 60
MIN_VOLUME_USD       = 500
MIN_LIQUIDITY_SOL    = float(os.getenv("MIN_LIQUIDITY_SOL", 5))
MIN_HOLDERS          = int(os.getenv("MIN_HOLDERS", 10))
MAX_DEV_HOLD_PCT     = float(os.getenv("MAX_DEV_HOLD_PCT", 20))
BUNDLE_FLAG_THRESHOLD = int(os.getenv("BUNDLE_FLAG_THRESHOLD", 3))
TRENDING_TOP_N       = 20

# ── Web ───────────────────────────────────────────────────────
WEB_HOST = os.getenv("WEB_HOST", "0.0.0.0")
WEB_PORT = int(os.getenv("WEB_PORT", 8080))

# ── Data ──────────────────────────────────────────────────────
LOG_DIR = "data/logs"
