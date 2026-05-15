"""
core/trending_engine.py — No-Brain-Trade Pro
Live token ranking by momentum score.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional
from models.token import TokenData
from config import TRENDING_TOP_N
from utils.logger import logger


class TrendingEngine:
    def __init__(self):
        self._tokens: dict[str, TokenData] = {}
        self._scores: dict[str, float] = {}

    def ingest(self, token: TokenData):
        self._tokens[token.mint] = token
        self._scores[token.mint] = self._score(token)

    def _score(self, token: TokenData) -> float:
        spike  = min(token.spike_pct / 500, 1.0) * 40
        vol    = min(token.volume_5m_usd / 50_000, 1.0) * 25
        sent   = ((token.sentiment_score + 1) / 2) * 15
        safety = (token.safety_score / 100) * 20
        if token.is_rugpull_risk:
            safety = 0
        if token.dev_sold:
            safety *= 0.3
        return spike + vol + sent + safety

    def get_trending(self, n: int = TRENDING_TOP_N) -> list[TokenData]:
        ranked = sorted(self._scores, key=self._scores.get, reverse=True)[:n]
        for i, mint in enumerate(ranked, 1):
            self._tokens[mint].trending_rank = i
        return [self._tokens[m] for m in ranked]

    def get(self, mint: str) -> Optional[TokenData]:
        return self._tokens.get(mint)

    def prune(self, max_age_minutes: int = 30):
        cutoff = datetime.utcnow() - timedelta(minutes=max_age_minutes)
        stale = [m for m, t in self._tokens.items() if t.last_updated < cutoff]
        for m in stale:
            self._tokens.pop(m, None)
            self._scores.pop(m, None)

    async def run_loop(self, interval: int = 10):
        while True:
            await asyncio.sleep(interval)
            for mint, token in self._tokens.items():
                self._scores[mint] = self._score(token)
            self.prune()

    @property
    def total_tracked(self) -> int:
        return len(self._tokens)
