"""
models/token.py — No-Brain-Trade Pro
Pydantic token data model shared across all modules.
"""

from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class TokenData(BaseModel):
    mint: str
    name: str = "Unknown"
    symbol: str = "???"
    uri: str = ""

    price_usd: float = 0.0
    price_sol: float = 0.0
    market_cap_usd: float = 0.0
    liquidity_sol: float = 0.0
    volume_5m_usd: float = 0.0
    volume_1h_usd: float = 0.0

    price_at_open: float = 0.0
    price_peak: float = 0.0
    spike_pct: float = 0.0
    spike_flagged: bool = False

    holder_count: int = 0
    top_holder_pct: float = 0.0
    dev_hold_pct: float = 0.0

    bundle_count: int = 0
    smart_money_flag: bool = False
    whale_flag: bool = False

    dev_wallet: str = ""
    dev_sold: bool = False
    mint_authority_revoked: bool = False
    freeze_authority_revoked: bool = False
    is_rugpull_risk: bool = False
    safety_score: int = 100

    sentiment_score: float = 0.0
    tweet_count: int = 0
    tg_mention_count: int = 0

    first_seen: datetime = Field(default_factory=datetime.utcnow)
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    trending_rank: Optional[int] = None
    tags: list[str] = Field(default_factory=list)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}

    def risk_label(self) -> str:
        if self.safety_score >= 80:
            return "SAFE"
        elif self.safety_score >= 50:
            return "CAUTION"
        return "RISKY"

    def spike_label(self) -> str:
        if self.spike_pct >= 500:
            return f"+{self.spike_pct:.0f}% 🔥"
        elif self.spike_pct >= 150:
            return f"+{self.spike_pct:.0f}% ⚡"
        elif self.spike_pct > 0:
            return f"+{self.spike_pct:.0f}%"
        return f"{self.spike_pct:.0f}%"
