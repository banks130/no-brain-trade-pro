import asyncio
import json
import websockets
from datetime import datetime
from typing import Callable, Optional
from models.token import TokenData
from utils.logger import logger

class PumpFunScanner:
    def __init__(self):
        self._new_token_cbs: list[Callable] = []
        self._trade_cbs: list[Callable] = []
        self._running = False
        self.registry: dict[str, TokenData] = {}
        self.reconnect_delay = 3
        self.msg_count = 0

    def on_new_token(self, fn: Callable):
        self._new_token_cbs.append(fn)
        return fn

    def on_trade(self, fn: Callable):
        self._trade_cbs.append(fn)
        return fn

    async def _subscribe(self, ws):
        await ws.send(json.dumps({"method": "subscribeNewToken"}))
        await ws.send(json.dumps({"method": "subscribeTokenTrade"}))
        logger.info("[scanner] Subscribed to newToken + tokenTrade")

    async def _handle(self, raw: str):
        self.msg_count += 1
        if self.msg_count % 10 == 0:
            logger.info(f"[scanner] {self.msg_count} msgs | {len(self.registry)} tokens tracked")
        try:
            msg = json.loads(raw)
        except Exception:
            return

        txtype = msg.get("txType") or msg.get("type") or ""

        if txtype == "create" or "initialBuy" in msg:
            token = self._parse_new(msg)
            if token:
                self.registry[token.mint] = token
                logger.info(f"[scanner] 🆕 NEW: {token.symbol} | {token.mint[:8]} | ${token.price_sol:.8f}")
                for cb in self._new_token_cbs:
                    await self._call(cb, token)

        elif txtype in ("buy", "sell"):
            mint = msg.get("mint", "")
            if mint in self.registry:
                self._update(self.registry[mint], msg)
                for cb in self._trade_cbs:
                    await self._call(cb, self.registry[mint], msg)

    def _parse_new(self, msg: dict) -> Optional[TokenData]:
        mint = msg.get("mint", "")
        if not mint:
            return None
        sol = float(msg.get("solAmount", 0) or 0)
        tkn = float(msg.get("tokenAmount", 1) or 1)
        price = sol / max(tkn, 1)
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

    def _update(self, token: TokenData, msg: dict):
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
            if asyncio.iscoroutinefunction(fn):
                await fn(*args)
            else:
                fn(*args)
        except Exception as e:
            logger.error(f"[scanner] cb error: {e}")

    async def run(self):
        self._running = True
        ws_url = "wss://pumpportal.fun/api/data"
        logger.info(f"[scanner] Starting - connecting to {ws_url}")
        
        while self._running:
            try:
                logger.info("[scanner] Connecting to pump.fun WebSocket...")
                async with websockets.connect(
                    ws_url,
                    ping_interval=20,
                    ping_timeout=10,
                    open_timeout=15,
                    extra_headers={"User-Agent": "Mozilla/5.0"},
                ) as ws:
                    logger.info("[scanner] ✅ CONNECTED TO PUMP.FUN!")
                    await self._subscribe(ws)
                    self.reconnect_delay = 3
                    async for msg in ws:
                        await self._handle(msg)
            except websockets.ConnectionClosed as e:
                logger.warning(f"[scanner] Connection closed: {e}")
            except Exception as e:
                logger.error(f"[scanner] Error: {type(e).__name__}: {e}")
            
            if self._running:
                logger.info(f"[scanner] Reconnecting in {self.reconnect_delay}s...")
                await asyncio.sleep(self.reconnect_delay)
                self.reconnect_delay = min(self.reconnect_delay * 2, 60)

    def stop(self):
        self._running = False
