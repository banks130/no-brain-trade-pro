"""
utils/birdeye.py — No-Brain-Trade Pro
Birdeye + DexScreener price/volume/liquidity data.
"""

import aiohttp
from typing import Optional
from config import BIRDEYE_API_KEY
from utils.logger import logger


class BirdeyeClient:
    BASE = "https://public-api.birdeye.so"

    def __init__(self):
        self.headers = {"X-API-KEY": BIRDEYE_API_KEY, "x-chain": "solana"}

    async def get_token_overview(self, mint: str) -> Optional[dict]:
        url = f"{self.BASE}/defi/token_overview?address={mint}"
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(url, headers=self.headers, timeout=aiohttp.ClientTimeout(total=8)) as r:
                    data = await r.json()
                    return data.get("data")
        except Exception as e:
            logger.warning(f"Birdeye overview [{mint[:8]}]: {e}")
            return None


class DexScreenerClient:
    async def get_best_pair(self, mint: str) -> Optional[dict]:
        url = f"https://api.dexscreener.com/latest/dex/tokens/{mint}"
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(url, timeout=aiohttp.ClientTimeout(total=8)) as r:
                    data = await r.json()
                    pairs = data.get("pairs", [])
                    if not pairs:
                        return None
                    return sorted(pairs, key=lambda p: float(p.get("liquidity", {}).get("usd", 0) or 0), reverse=True)[0]
        except Exception as e:
            logger.warning(f"DexScreener [{mint[:8]}]: {e}")
            return None

    async def search(self, query: str) -> Optional[list]:
        url = f"https://api.dexscreener.com/latest/dex/search/?q={query}"
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(url, timeout=aiohttp.ClientTimeout(total=8)) as r:
                    data = await r.json()
                    return data.get("pairs", [])
        except Exception as e:
            logger.warning(f"DexScreener search: {e}")
            return None


birdeye = BirdeyeClient()
dexscreener = DexScreenerClient()
