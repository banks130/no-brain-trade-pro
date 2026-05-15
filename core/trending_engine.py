from collections import defaultdict, deque
from datetime import datetime, timedelta
from models.token import TokenData
from config import TRENDING_WINDOW_MINUTES, TRENDING_TOP_N
from utils.logger import logger

class TrendingEngine:
    def __init__(self):
        self._scores: dict[str, float] = defaultdict(float)
        self._history: dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self._running = True

    def ingest(self, token: TokenData):
        mint = token.mint
        self._history[mint].append((datetime.utcnow(), token.price_sol, token.volume_24h_usd))
        self._update_score(token)

    def _update_score(self, token: TokenData):
        score = 0.0
        if token.spike_pct > 100:
            score += token.spike_pct / 100
        if token.volume_24h_usd > 10000:
            score += token.volume_24h_usd / 100000
        if token.liquidity_sol > 50:
            score += token.liquidity_sol / 100
        self._scores[token.mint] = score

    def get_trending(self, top_n: int = TRENDING_TOP_N):
        sorted_tokens = sorted(self._scores.items(), key=lambda x: x[1], reverse=True)
        return [mint for mint, score in sorted_tokens[:top_n]]

    async def run_loop(self):
        while self._running:
            await asyncio.sleep(60)
            self._cleanup()

    def _cleanup(self):
        cutoff = datetime.utcnow() - timedelta(minutes=TRENDING_WINDOW_MINUTES)
        to_remove = [mint for mint, history in self._history.items() 
                    if history and history[-1][0] < cutoff]
        for mint in to_remove:
            del self._history[mint]
            self._scores.pop(mint, None)
