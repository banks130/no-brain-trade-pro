import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))
TREASURY_WALLET = os.getenv("TREASURY_WALLET", "")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./nobraintrade.db")
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", "")
SECRET_KEY = os.getenv("SECRET_KEY", "")
HELIUS_API_KEY = os.getenv("HELIUS_API_KEY", "")
BIRDEYE_API_KEY = os.getenv("BIRDEYE_API_KEY", "")

WEB_HOST = os.getenv("WEB_HOST", "0.0.0.0")
WEB_PORT = int(os.getenv("PORT", "8080"))

PUMPFUN_WS_URL = os.getenv("PUMPFUN_WS_URL", "wss://pumpportal.fun/api/data")

SPIKE_THRESHOLD_PCT = float(os.getenv("SPIKE_THRESHOLD_PCT", "150"))
SPIKE_WINDOW_SECONDS = int(os.getenv("SPIKE_WINDOW_SECONDS", "60"))

MIN_VOLUME_USD = float(os.getenv("MIN_VOLUME_USD", "1000"))
MIN_LIQUIDITY_SOL = float(os.getenv("MIN_LIQUIDITY_SOL", "10"))
MIN_HOLDERS = int(os.getenv("MIN_HOLDERS", "10"))

PRO_PRICE_SOL = float(os.getenv("PRO_PRICE_SOL", "0.5"))
DEFAULT_TRADE_SOL = float(os.getenv("DEFAULT_TRADE_SOL", "0.1"))
DEFAULT_SLIPPAGE_BPS = int(os.getenv("DEFAULT_SLIPPAGE_BPS", "300"))

SOLANA_RPC_URL = os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")
SOLANA_WSS_URL = os.getenv("SOLANA_WSS_URL", "wss://api.mainnet-beta.solana.com")

TRENDING_WINDOW_MINUTES = int(os.getenv("TRENDING_WINDOW_MINUTES", "15"))
TRENDING_TOP_K = int(os.getenv("TRENDING_TOP_K", "50"))
TRENDING_TOP_N = int(os.getenv("TRENDING_TOP_N", "20"))

DEEPNET_ENABLED = os.getenv("DEEPNET_ENABLED", "true").lower() == "true"
DEEPNET_API_KEY = os.getenv("DEEPNET_API_KEY", "")
