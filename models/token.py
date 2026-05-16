from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class TokenData(BaseModel):
    mint: str
    name: str
    symbol: str
    uri: str = ""
    price_sol: float = 0.0
    price_at_open: float = 0.0
    price_peak: float = 0.0
    dev_wallet: str = ""
    first_seen: datetime = datetime.utcnow()
    last_updated: datetime = datetime.utcnow()
    spike_pct: float = 0.0
    spike_flagged: bool = False
    liquidity_sol: float = 0.0
    volume_24h_usd: float = 0.0  # Add this
    holder_count: int = 0  # Add this
    is_rugpull_risk: bool = False
    deepnet_score: float = 0.0
    bundle_detected: bool = False
    dev_safety_score: int = 0
