"""
core/spike_detector.py — No-Brain-Trade Pro
150%+ spike detection with filters.
"""

import asyncio
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Callable
from models.token import TokenData
from config import (
    SPIKE_THRESHOLD_PCT, SPIKE_WINDOW_SECONDS,
    MIN_VOLUME_USD, MIN_LIQUIDITY_SOL, MIN_HOLDERS
)
from utils.logger import logger


class SpikeDetector:
    def __init__(self):
        self._callbacks: list[Callable] = []
        self._history: dict[str, deque] = defaultdict(lambda: deque(maxlen=500))
        self._flagged: set[str] = set()

    def on_spike(self, fn: Callable):
        self._callbacks.append(fn)
        return fn

    async def process(self, token: TokenData):
        mint = token.mint
        now = datetime.utcnow()
        self._history[mint].append((now, token.price_sol))

        window_start = now - timedelta(seconds=SPIKE_WINDOW_SECONDS)
        history = [(t, p) for t, p in self._history[mint] if t >= window_start]

        if len(history) < 2 or history[0][1] <= 0:
            return

        spike_pct = ((token.price_sol - history[0][1]) / history[0][1]) * 100
        token.spike_pct = spike_pct

        if spike_pct >= SPIKE_THRESHOLD_PCT and mint not in self._flagged:
            if self._passes(token):
                token.spike_flagged = True
                self._flagged.add(mint)
                for cb in self._callbacks:
                    await self._call(cb, token, spike_pct)
        elif spike_pct < SPIKE_THRESHOLD_PCT * 0.5:
            self._flagged.discard(mint)
            token.spike_flagged = False

    def _passes(self, token: TokenData) -> bool:
        if token.liquidity_sol < MIN_LIQUIDITY_SOL:
            return False
        if token.holder_count > 0 and token.holder_count < MIN_HOLDERS:
            return False
        if token.is_rugpull_risk:
            return False
        return True

    def get_history(self, mint: str) -> list:
        return list(self._history.get(mint, []))

    async def _call(self, fn, *args):
        try:
            r = fn(*args)
            if asyncio.iscoroutine(r):
                await r
        except Exception as e:
            logger.error(f"[spike] cb error: {e}")
