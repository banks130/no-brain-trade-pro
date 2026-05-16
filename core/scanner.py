import asyncio
import random
from datetime import datetime
from typing import Callable, List
from models.token import TokenData
from utils.logger import logger

class PumpFunScanner:
    def __init__(self):
        self._new_token_cbs: list[Callable] = []
        self._trade_cbs: list[Callable] = []
        self._running = False
        self.registry: dict[str, TokenData] = {}
        self.msg_count = 0

    def on_new_token(self, fn: Callable):
        self._new_token_cbs.append(fn)
        return fn

    def on_trade(self, fn: Callable):
        self._trade_cbs.append(fn)
        return fn

    async def run(self):
        """Generate mock tokens for testing"""
        self._running = True
        logger.info("[scanner] 🟢 Starting mock token generator")
        
        mock_symbols = ['🚀 MOON', '💎 DIAMOND', '🐶 DOGE', '🟣 PEPE', '🔥 FIRE', '🐸 PONKE', '🎮 GAME', '🤖 AI', '⚡ BOLT', '🌟 STAR']
        
        count = 0
        while self._running:
            try:
                # Generate random token
                symbol = random.choice(mock_symbols) + str(random.randint(1, 99))
                price = random.uniform(0.000001, 0.0001)
                spike = random.uniform(50, 500)
                
                token = TokenData(
                    mint=f"mock_{count}_{random.randint(1000,9999)}",
                    name=f"{symbol} Token",
                    symbol=symbol,
                    uri="",
                    price_sol=price,
                    price_at_open=price / (1 + spike/100),
                    price_peak=price * random.uniform(1, 2),
                    dev_wallet="mock_wallet",
                    liquidity_sol=random.uniform(10, 500),
                    volume_24h_usd=random.uniform(1000, 100000),
                    holder_count=random.randint(10, 500),
                    spike_pct=spike,
                    first_seen=datetime.utcnow(),
                    last_updated=datetime.utcnow(),
                )
                
                self.registry[token.mint] = token
                self.msg_count += 1
                logger.info(f"[scanner] 🆕 {token.symbol} | ${token.price_sol:.8f} | +{token.spike_pct:.0f}%")
                
                # Notify callbacks
                for cb in self._new_token_cbs:
                    await self._call(cb, token)
                
                count += 1
                await asyncio.sleep(8)  # New token every 8 seconds
                
            except Exception as e:
                logger.error(f"[scanner] Error: {e}")
                await asyncio.sleep(5)

    async def _call(self, fn, *args):
        try:
            if asyncio.iscoroutinefunction(fn):
                await fn(*args)
            else:
                fn(*args)
        except Exception as e:
            logger.error(f"[scanner] Callback error: {e}")

    def stop(self):
        self._running = False
        logger.info("[scanner] Stopped")
