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
        
        # Multiple WebSocket URLs to try
        self.ws_urls = [
            "wss://pumpportal.fun/api/data",
            "wss://frontend-dedicated-ws.pump.fun/ws",
            "wss://pump.fun/ws",
        ]
        self.current_url_index = 0

    def on_new_token(self, fn: Callable):
        self._new_token_cbs.append(fn)
        return fn

    def on_trade(self, fn: Callable):
        self._trade_cbs.append(fn)
        return fn

    async def _subscribe(self, ws):
        try:
            await ws.send(json.dumps({"method": "subscribeNewToken"}))
            await ws.send(json.dumps({"method": "subscribeTokenTrade"}))
            logger.info("[scanner] Subscribed to newToken + tokenTrade")
        except Exception as e:
            logger.error(f"[scanner] Subscribe error: {e}")

    async def _handle(self, raw: str):
        self.msg_count += 1
        if self.msg_count % 10 == 0:
            logger.info(f"[scanner] {self.msg_count} msgs | {len(self.registry)} tokens")
        
        try:
            msg = json.loads(raw)
        except Exception as e:
            return

        # Debug: print first few messages
        if self.msg_count <= 5:
            logger.info(f"[scanner] Sample message: {list(msg.keys())}")

        txtype = msg.get("txType") or msg.get("type") or msg.get("event") or ""

        # Handle different message formats
        if txtype == "create" or "initialBuy" in msg or msg.get("event") == "new_token":
            token = self._parse_new(msg)
            if token:
                self.registry[token.mint] = token
                logger.info(f"[scanner] 🆕 NEW TOKEN: {token.symbol} | ${token.price_sol:.8f}")
                for cb in self._new_token_cbs:
                    await self._call(cb, token)

        elif txtype in ("buy", "sell") or msg.get("event") == "trade":
            mint = msg.get("mint") or msg.get("tokenAddress")
            if mint and mint in self.registry:
                self._update(self.registry[mint], msg)
                for cb in self._trade_cbs:
                    await self._call(cb, self.registry[mint], msg)

    def _parse_new(self, msg: dict) -> Optional[TokenData]:
        mint = msg.get("mint") or msg.get("tokenAddress") or msg.get("address")
        if not mint:
            return None
        
        sol = float(msg.get("solAmount", msg.get("amount", 0)) or 0)
        tkn = float(msg.get("tokenAmount", msg.get("tokenCount", 1)) or 1)
        price = sol / max(tkn, 1)
        
        return TokenData(
            mint=mint,
            name=msg.get("name", msg.get("tokenName", "Unknown")),
            symbol=msg.get("symbol", msg.get("tokenSymbol", "???")),
            uri=msg.get("uri", msg.get("metadata", "")),
            price_sol=price if price > 0 else 0.000001,
            price_at_open=price,
            price_peak=price,
            dev_wallet=msg.get("traderPublicKey", msg.get("creator", "")),
            first_seen=datetime.utcnow(),
            last_updated=datetime.utcnow(),
        )

    def _update(self, token: TokenData, msg: dict):
        sol = float(msg.get("solAmount", msg.get("amount", 0)) or 0)
        tkn = float(msg.get("tokenAmount", msg.get("tokenCount", 1)) or 1)
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
        
        while self._running:
            ws_url = self.ws_urls[self.current_url_index]
            logger.info(f"[scanner] Attempting connection to {ws_url}")
            
            try:
                async with websockets.connect(
                    ws_url,
                    ping_interval=20,
                    ping_timeout=30,
                    open_timeout=30,
                    close_timeout=10,
                    max_size=10**7,
                    extra_headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                        "Origin": "https://pump.fun",
                        "Referer": "https://pump.fun/"
                    }
                ) as ws:
                    logger.info(f"[scanner] ✅ CONNECTED to {ws_url}")
                    await self._subscribe(ws)
                    self.reconnect_delay = 3
                    self.current_url_index = 0  # Reset on success
                    
                    async for msg in ws:
                        await self._handle(msg)
                        
            except websockets.ConnectionClosed as e:
                logger.warning(f"[scanner] Connection closed: {e.code} - {e.reason}")
            except asyncio.TimeoutError:
                logger.warning(f"[scanner] Timeout connecting to {ws_url}")
            except Exception as e:
                logger.error(f"[scanner] Error: {type(e).__name__}: {e}")
            
            if self._running:
                # Try next URL
                self.current_url_index = (self.current_url_index + 1) % len(self.ws_urls)
                logger.info(f"[scanner] Reconnecting in {self.reconnect_delay}s...")
                await asyncio.sleep(self.reconnect_delay)
                self.reconnect_delay = min(self.reconnect_delay * 2, 60)

    def stop(self):
        self._running = False
        logger.info("[scanner] Stopped")
