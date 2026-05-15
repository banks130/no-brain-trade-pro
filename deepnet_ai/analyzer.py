"""
deepnet_ai/analyzer.py — No-Brain-Trade Pro
DeepNet AI orchestrator. Runs on-chain, bundle, dev, sentiment analysis.
"""

import asyncio
from models.token import TokenData
from utils.rpc import rpc, helius
from utils.birdeye import dexscreener
from utils.logger import logger
from config import MAX_DEV_HOLD_PCT, BUNDLE_FLAG_THRESHOLD
from collections import defaultdict
from datetime import datetime, timedelta


class DeepNetAI:

    async def analyze(self, token: TokenData, fast: bool = False) -> TokenData:
        if fast:
            await asyncio.gather(
                self._enrich_market(token),
                self._check_authorities(token),
                return_exceptions=True,
            )
        else:
            await asyncio.gather(
                self._enrich_market(token),
                self._check_authorities(token),
                self._check_holders(token),
                self._detect_bundles(token),
                return_exceptions=True,
            )
        token.safety_score = self._safety_score(token)
        token.is_rugpull_risk = token.safety_score < 40
        token.tags = self._tags(token)
        return token

    async def _enrich_market(self, token: TokenData):
        pair = await dexscreener.get_best_pair(token.mint)
        if not pair:
            return
        try:
            token.price_usd      = float(pair.get("priceUsd", 0) or 0)
            token.market_cap_usd = float(pair.get("fdv", 0) or 0)
            liq = pair.get("liquidity", {})
            token.liquidity_sol  = float(liq.get("base", 0) or 0)
            vol = pair.get("volume", {})
            token.volume_5m_usd  = float(vol.get("m5", 0) or 0)
            token.volume_1h_usd  = float(vol.get("h1", 0) or 0)
            if token.price_at_open == 0 and token.price_usd > 0:
                token.price_at_open = token.price_usd
        except Exception as e:
            logger.debug(f"[ai] market enrich: {e}")

    async def _check_authorities(self, token: TokenData):
        result = await rpc.get_account_info(token.mint)
        if not result:
            return
        try:
            info = (result.get("value", {})
                         .get("data", {})
                         .get("parsed", {})
                         .get("info", {}))
            token.mint_authority_revoked   = info.get("mintAuthority") is None
            token.freeze_authority_revoked = info.get("freezeAuthority") is None
        except Exception as e:
            logger.debug(f"[ai] authority check: {e}")

    async def _check_holders(self, token: TokenData):
        accounts = await helius.get_holders(token.mint)
        if accounts:
            token.holder_count = len(accounts)
            total = sum(float(a.get("amount", 0)) for a in accounts)
            if total > 0 and accounts:
                top = max(accounts, key=lambda a: float(a.get("amount", 0)))
                token.top_holder_pct = (float(top.get("amount", 0)) / total) * 100
            return
        # RPC fallback
        result = await rpc.get_token_largest_accounts(token.mint)
        if result:
            token.holder_count = len(result)
            total = sum(float(a.get("uiAmount", 0) or 0) for a in result)
            if total > 0:
                token.top_holder_pct = (float(result[0].get("uiAmount", 0) or 0) / total) * 100

    async def _detect_bundles(self, token: TokenData):
        sigs = await rpc.get_signatures_for_address(token.mint, limit=30)
        if not sigs:
            return
        tasks = [rpc.get_transaction(s["signature"]) for s in sigs[:15]]
        txs = await asyncio.gather(*tasks, return_exceptions=True)
        slot_groups: dict[int, int] = defaultdict(int)
        for tx in txs:
            if not tx or isinstance(tx, Exception):
                continue
            try:
                if tx.get("meta", {}).get("err"):
                    continue
                slot = tx.get("slot", 0)
                slot_groups[slot] += 1
            except Exception:
                continue
        token.bundle_count = sum(1 for count in slot_groups.values() if count >= 2)
        if token.bundle_count >= BUNDLE_FLAG_THRESHOLD:
            logger.info(f"[ai] Bundle alert: {token.symbol} ({token.bundle_count} slots)")

    def _safety_score(self, token: TokenData) -> int:
        score = 100
        if not token.mint_authority_revoked:
            score -= 30
        if not token.freeze_authority_revoked:
            score -= 15
        if token.dev_sold:
            score -= 25
        if token.dev_hold_pct > MAX_DEV_HOLD_PCT:
            score -= 20
        if token.top_holder_pct > 50:
            score -= 15
        elif token.top_holder_pct > 30:
            score -= 8
        if token.holder_count < 10:
            score -= 10
        elif token.holder_count < 50:
            score -= 5
        if token.bundle_count >= 5:
            score -= 10
        elif token.bundle_count >= 3:
            score -= 5
        return max(0, min(100, score))

    def _tags(self, token: TokenData) -> list[str]:
        tags = []
        if token.smart_money_flag:
            tags.append("SMART_MONEY")
        if token.whale_flag:
            tags.append("WHALE_BUY")
        if token.bundle_count >= BUNDLE_FLAG_THRESHOLD:
            tags.append("BUNDLED")
        if token.spike_pct >= 500:
            tags.append("MEGA_PUMP")
        elif token.spike_pct >= 150:
            tags.append("SPIKE")
        if token.is_rugpull_risk:
            tags.append("RUG_RISK")
        if token.mint_authority_revoked and token.freeze_authority_revoked:
            tags.append("AUTH_REVOKED")
        return tags

    def summarize(self, token: TokenData) -> str:
        tags = " ".join(token.tags[:3]) if token.tags else ""
        return (
            f"{token.symbol} | {token.spike_label()} | "
            f"safe={token.safety_score} | liq={token.liquidity_sol:.1f}SOL | {tags}"
        )


deepnet = DeepNetAI()
