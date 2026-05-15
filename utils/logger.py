"""
utils/logger.py — Logging configuration for No-Brain-Trade Pro
"""

import logging
import sys
from datetime import datetime

# Create formatter
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Console handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)

# File handler (optional)
file_handler = logging.FileHandler('nobraintrade.log')
file_handler.setFormatter(formatter)

# Configure root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(console_handler)
root_logger.addHandler(file_handler)

# Create module logger
logger = logging.getLogger("nobraintrade")

# Suppress noisy libraries
logging.getLogger("websockets").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)

# Custom log functions
def log_spike(token_symbol: str, spike_pct: float, mint: str):
    logger.info(f"🚀 SPIKE DETECTED: {token_symbol} +{spike_pct:.1f}% | {mint[:8]}")

def log_trade(trade_type: str, token_symbol: str, amount_sol: float, tx: str):
    logger.info(f"💰 {trade_type.upper()}: {token_symbol} | {amount_sol} SOL | {tx[:16]}...")

def log_error(context: str, error: Exception):
    logger.error(f"❌ {context}: {type(error).__name__} - {str(error)}", exc_info=True)

print("[logger] Logging configured")
