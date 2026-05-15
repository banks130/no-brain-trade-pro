import asyncio
import aiohttp
from datetime import datetime
from typing import Callable, Optional, List
from models.token import TokenData
from utils.logger import logger

class PumpFunScanner:
    def __init__(self):
        self._new_token_cbs: list[Callable] = []
        self._trade_cbs: list[Callable] = []
        self._running = False
        self.registry: dict[str, TokenData] = {}
        self.seen_tokens: set[str] = set()
        self.msg_count = 0

    def on_new_token(self, fn: Callable):
        self._new_token_cbs.append(fn)
        return fn

    def on_trade(self, fn: Callable):
        self._trade_cbs.append(fn)
        return fn

    async def fetch_new_tokens(self) -> List[TokenData]:
        """Fetch new tokens from pump.fun API"""
        tokens = []
        
        try:
            # Try multiple API endpoints
            apis = [
                "https://frontend-api.pump.fun/tokens?limit=20&sort=createdAt&order=DESC",
                "https://pump.fun/coins?offset=0&limit=20&sort=created&order=desc",
            ]
            
            async with aiohttp.ClientSession() as session:
                for api_url in apis:
                    try:
                        async with session.get(api_url, timeout=10, headers={
                            "User-Agent": "Mozilla/5.0",
                            "Accept": "application/json"
                        }) as response:
                            if response.status == 200:
                                data = await response.json()
                                parsed = self._parse_api_response(data)
                                if parsed:
                                    tokens = parsed
                                    logger.info(f"[scanner] Fetched {len(tokens)} tokens")
                                    break
                    except Exception as e:
                        logger.debug(f"[scanner] API failed: {api_url}")
                        continue
                        
        except Exception as e:
            logger.error(f"[scanner] Fetch error: {e}")
        
        return tokens

    def _parse_api_response(self, data) -> List[TokenData]:
        """Parse different API response formats"""
        tokens = []
        
        try:
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                items = data.get("tokens", data.get("results", data.get("data", [])))
            else:
                return []
            
            for item in items[:20]:
                mint = item.get("mint", item.get("address", item.get("id")))
                if not mint or mint in self.seen_tokens:
                    continue
                
                self.seen_tokens.add(mint)
                
                price = float(item.get("price", item.get("priceSol", 0.000001)))
                liquidity = float(item.get("liquidity", item.get("liquiditySol", 0)))
                volume = float(item.get("volume24h", item.get("volume", 0)))
                holders = int(item.get("holderCount", item.get("holders", 0)))
                
                token = TokenData(
                    mint=mint,
                    name=item.get("name", "Unknown"),
                    symbol=item.get("symbol", "???"),
                    uri=item.get("uri", item.get("metadata", "")),
                    price_sol=price,
                    price_at_open=price,
                    price_peak=price,
                    dev_wallet=item.get("creator", item.get("dev", "")),
                    liquidity_sol=liquidity,
                    volume_24h_usd=volume,
                    holder_count=holders,
                    first_seen=datetime.utcnow(),
                    last_updated=datetime.utcnow(),
                )
                tokens.append(token)
                
        except Exception as e:
            logger.error(f"[scanner] Parse error: {e}")
        
        return tokens

    async def run(self):
        """Main scanner loop - polls every 5 seconds"""
        self._running = True
        logger.info("[scanner] Starting HTTP poller - checking every 5 seconds")
        
        while self._running:
            try:
                new_tokens = await self.fetch_new_tokens()
                
                for token in new_tokens:
                    self.msg_count += 1
                    self.registry[token.mint] = token
                    logger.info(f"[scanner] 🆕 NEW: {token.symbol} | ${token.price_sol:.8f}")
                    
                    for cb in self._new_token_cbs:
                        await self._call(cb, token)
                
                await asyncio.sleep(5)
                
            except Exception as e:
                logger.error(f"[scanner] Loop error: {e}")
                await asyncio.sleep(10)

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
