"""
core/scanner.py — No-Brain-Trade Pro
Real-time pump.fun WebSocket scanner.
"""

import asyncio
import json
import websockets
from datetime import datetime
from typing import Callable, Optional
from models.token import TokenData
from config import PUMPFUN_WS_URL
from utils.logger import logger


class PumpFunScanner:
    def __init__(self):
        self._new_token_callbacks: list[Callable] = []
        self._trade_callbacks: list[Callable] = []
        self._running = False
        self.token_registry: dict[str, TokenData] = {}
        self.reconnect_delay = 3

    def on_new_token(self, fn: Callable):
        self._new_token_callbacks.append(fn)
        return fn

    def on_trade(self, fn: Callable):
        self._trade_callbacks.append(fn)
        return fn

    async def _subscribe(self, ws):
        await ws.send(json.dumps({"method": "subscribeNewToken"}))
        await ws.send(json.dumps({"method": "subscribeTokenTrade"}))

    async def _handle(self, raw: str):
        try:
            msg = json.loads(raw)
        except Exception:
            return

        event_type = msg.get("txType") or msg.get("type") or ""

        if event_type == "create" or "initialBuy" in msg:
            token = self._parse_new(msg)
            if token:
                self.token_registry[token.mint] = token
                for cb in self._new_token_callbacks:
                    await self._call(cb, token)

        elif event_type in ("buy", "sell"):
            mint = msg.get("mint", "")
            if mint in self.token_registry:
                self._update_trade(self.token_registry[mint], msg)
                for cb in self._trade_callbacks:
                    await self._call(cb, self.token_registry[mint], msg)

    def _parse_new(self, msg: dict) -> Optional[TokenData]:
        mint = msg.get("mint", "")
        if not mint:
            return None
        sol = float(msg.get("solAmount", 0) or 0)
        tokens = float(msg.get("tokenAmount", 1) or 1)
        price = sol / max(tokens, 1)
        return TokenData(
            mint=mint,
            name=msg.get("name", "Unknown"),
            symbol=msg.get("symbol", "???"),
            uri=msg.get("uri", ""),
            price_sol=price,
            price_at_open=price,
            price_peak=price,
            dev_wallet=msg.get("traderPublicKey", ""),
            first_seen=datetime.utcnow(),
            last_updated=datetime.utcnow(),
        )

    def _update_trade(self, token: TokenData, msg: dict):
        sol = float(msg.get("solAmount", 0) or 0)
        tkn = float(msg.get("tokenAmount", 1) or 1)
        if tkn > 0 and sol > 0:
            price = sol / tkn
            token.price_sol = price
            if token.price_at_open > 0:
                token.spike_pct = ((price - token.price_at_open) / token.price_at_open) * 100
            if price > token.price_peak:
                token.price_peak = price
        token.last_updated = datetime.utcnow()

    async def _call(self, fn, *args):
        try:
            r = fn(*args)
            if asyncio.iscoroutine(r):
                await r
        except Exception as e:
            logger.error(f"[scanner] cb error: {e}")

    async def run(self):
        self._running = True
        while self._running:
            try:
                logger.info(f"[scanner] Connecting to pump.fun WS...")
                async with websockets.connect(PUMPFUN_WS_URL, ping_interval=20, ping_timeout=10) as ws:
                    await self._subscribe(ws)
                    self.reconnect_delay = 3
                    logger.info("[scanner] Connected ✓")
                    async for msg in ws:
                        await self._handle(msg)
            except websockets.ConnectionClosed:
                logger.warning("[scanner] Connection closed")
            except Exception as e:
                logger.error(f"[scanner] {e}")
            if self._running:
                await asyncio.sleep(self.reconnect_delay)
                self.reconnect_delay = min(self.reconnect_delay * 2, 60)

    def stop(self):
        self._running = False
