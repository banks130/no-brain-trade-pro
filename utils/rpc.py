"""
utils/rpc.py — No-Brain-Trade Pro
Solana RPC + Helius client.
"""

import asyncio
import aiohttp
from typing import Any, Optional
from config import SOLANA_RPC_URL, HELIUS_API_KEY
from utils.logger import logger


class SolanaRPC:
    def __init__(self, rpc_url: str = SOLANA_RPC_URL):
        self.rpc_url = rpc_url
        self._session: Optional[aiohttp.ClientSession] = None
        self._id = 0

    async def _session_(self) -> aiohttp.ClientSession:
        if not self._session or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def call(self, method: str, params: list = None, retries: int = 3) -> Any:
        session = await self._session_()
        self._id += 1
        payload = {"jsonrpc": "2.0", "id": self._id, "method": method, "params": params or []}
        for attempt in range(retries):
            try:
                async with session.post(self.rpc_url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as r:
                    data = await r.json()
                    if "error" in data:
                        logger.warning(f"RPC [{method}]: {data['error']}")
                        return None
                    return data.get("result")
            except Exception as e:
                if attempt == retries - 1:
                    logger.error(f"RPC failed [{method}]: {e}")
                    return None
                await asyncio.sleep(0.5 * (attempt + 1))

    async def get_balance(self, pubkey: str) -> float:
        result = await self.call("getBalance", [pubkey])
        if result:
            return result.get("value", 0) / 1e9
        return 0.0

    async def get_token_supply(self, mint: str) -> Optional[dict]:
        return await self.call("getTokenSupply", [mint])

    async def get_token_largest_accounts(self, mint: str) -> Optional[list]:
        result = await self.call("getTokenLargestAccounts", [mint])
        return result.get("value") if result else None

    async def get_account_info(self, pubkey: str) -> Optional[dict]:
        return await self.call("getAccountInfo", [pubkey, {"encoding": "jsonParsed"}])

    async def get_signatures_for_address(self, pubkey: str, limit: int = 20) -> Optional[list]:
        return await self.call("getSignaturesForAddress", [pubkey, {"limit": limit}])

    async def get_transaction(self, sig: str) -> Optional[dict]:
        return await self.call("getTransaction", [sig, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}])

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()


class HeliusClient:
    BASE = "https://api.helius.xyz/v0"

    def __init__(self, api_key: str = HELIUS_API_KEY):
        self.api_key = api_key

    async def get_token_metadata(self, mint: str) -> Optional[dict]:
        if not self.api_key:
            return None
        url = f"{self.BASE}/token-metadata?api-key={self.api_key}"
        async with aiohttp.ClientSession() as s:
            try:
                async with s.post(url, json={"mintAccounts": [mint]}, timeout=aiohttp.ClientTimeout(total=10)) as r:
                    data = await r.json()
                    return data[0] if data else None
            except Exception as e:
                logger.warning(f"Helius metadata: {e}")
                return None

    async def get_holders(self, mint: str) -> Optional[list]:
        if not self.api_key:
            return None
        url = f"https://mainnet.helius-rpc.com/?api-key={self.api_key}"
        payload = {"jsonrpc": "2.0", "id": 1, "method": "getTokenAccounts", "params": {"mint": mint, "limit": 100}}
        async with aiohttp.ClientSession() as s:
            try:
                async with s.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as r:
                    data = await r.json()
                    return data.get("result", {}).get("token_accounts", [])
            except Exception as e:
                logger.warning(f"Helius holders: {e}")
                return None


rpc = SolanaRPC()
helius = HeliusClient()
