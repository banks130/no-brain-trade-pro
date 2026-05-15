"""
core/autotrade.py — No-Brain-Trade Pro
Jupiter-powered auto-trade execution for Pro users.
Non-custodial: each user's keypair signs their own transactions.
"""

import asyncio
import aiohttp
import base64
from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models.db import UserWallet, AutoTradeConfig, Trade, User
from models.token import TokenData
from utils.wallet import load_keypair
from utils.rpc import rpc
from utils.logger import logger

JUPITER_QUOTE_URL  = "https://quote-api.jup.ag/v6/quote"
JUPITER_SWAP_URL   = "https://quote-api.jup.ag/v6/swap"
SOL_MINT           = "So11111111111111111111111111111111111111112"
USDC_MINT          = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"


class AutoTrader:

    async def execute_buy(
        self,
        db: AsyncSession,
        telegram_id: int,
        token: TokenData,
        sol_amount: float,
        slippage_bps: int = 300,
    ) -> Optional[str]:
        """
        Buy a token using the user's managed wallet via Jupiter.
        Returns tx signature or None on failure.
        """
        wallet = await self._get_wallet(db, telegram_id)
        if not wallet:
            return None

        lamports = int(sol_amount * 1e9)

        # Step 1: Get Jupiter quote
        quote = await self._get_quote(SOL_MINT, token.mint, lamports, slippage_bps)
        if not quote:
            logger.warning(f"[autotrade] No quote for {token.symbol}")
            return None

        # Step 2: Get swap transaction
        kp = load_keypair(wallet.encrypted_secret)
        swap_tx = await self._get_swap_tx(quote, str(kp.pubkey()))
        if not swap_tx:
            return None

        # Step 3: Sign and send
        tx_sig = await self._sign_and_send(kp, swap_tx)
        if not tx_sig:
            return None

        # Step 4: Record trade
        trade = Trade(
            telegram_id=telegram_id,
            mint=token.mint,
            symbol=token.symbol,
            action="buy",
            sol_amount=sol_amount,
            token_amount=float(quote.get("outAmount", 0)) / 1e6,
            price_sol=token.price_sol,
            tx_signature=tx_sig,
            status="confirmed",
            created_at=datetime.utcnow(),
            confirmed_at=datetime.utcnow(),
        )
        db.add(trade)
        await db.commit()

        logger.info(f"[autotrade] BUY {token.symbol} {sol_amount}SOL | tx: {tx_sig[:16]}...")
        return tx_sig

    async def execute_sell(
        self,
        db: AsyncSession,
        telegram_id: int,
        token: TokenData,
        token_amount: float,
        slippage_bps: int = 300,
    ) -> Optional[str]:
        """Sell a token back to SOL."""
        wallet = await self._get_wallet(db, telegram_id)
        if not wallet:
            return None

        amount_raw = int(token_amount * 1e6)
        quote = await self._get_quote(token.mint, SOL_MINT, amount_raw, slippage_bps)
        if not quote:
            return None

        kp = load_keypair(wallet.encrypted_secret)
        swap_tx = await self._get_swap_tx(quote, str(kp.pubkey()))
        if not swap_tx:
            return None

        tx_sig = await self._sign_and_send(kp, swap_tx)
        if not tx_sig:
            return None

        sol_received = float(quote.get("outAmount", 0)) / 1e9
        trade = Trade(
            telegram_id=telegram_id,
            mint=token.mint,
            symbol=token.symbol,
            action="sell",
            sol_amount=sol_received,
            token_amount=token_amount,
            price_sol=token.price_sol,
            tx_signature=tx_sig,
            status="confirmed",
            created_at=datetime.utcnow(),
            confirmed_at=datetime.utcnow(),
        )
        db.add(trade)
        await db.commit()

        logger.info(f"[autotrade] SELL {token.symbol} → {sol_received:.3f}SOL | tx: {tx_sig[:16]}...")
        return tx_sig

    async def should_trade(self, db: AsyncSession, telegram_id: int, token: TokenData) -> tuple[bool, str]:
        """Check if auto-trade should fire for this user + token."""
        # Check config
        result = await db.execute(
            select(AutoTradeConfig).where(AutoTradeConfig.telegram_id == telegram_id)
        )
        cfg = result.scalar_one_or_none()
        if not cfg or not cfg.enabled:
            return False, "autotrade_disabled"

        if token.spike_pct < cfg.min_spike_pct:
            return False, f"spike {token.spike_pct:.0f}% < threshold {cfg.min_spike_pct:.0f}%"

        if token.safety_score < cfg.min_safety_score:
            return False, f"safety {token.safety_score} < min {cfg.min_safety_score}"

        # Check daily trade limit
        from sqlalchemy import func
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0)
        count_result = await db.execute(
            select(func.count(Trade.id)).where(
                Trade.telegram_id == telegram_id,
                Trade.action == "buy",
                Trade.created_at >= today_start,
            )
        )
        daily_count = count_result.scalar() or 0
        if daily_count >= cfg.max_trades_day:
            return False, f"daily limit reached ({daily_count}/{cfg.max_trades_day})"

        return True, "ok"

    # ── Jupiter helpers ───────────────────────────────────────

    async def _get_quote(self, input_mint: str, output_mint: str, amount: int, slippage_bps: int) -> Optional[dict]:
        params = {
            "inputMint": input_mint,
            "outputMint": output_mint,
            "amount": amount,
            "slippageBps": slippage_bps,
        }
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(JUPITER_QUOTE_URL, params=params, timeout=aiohttp.ClientTimeout(total=10)) as r:
                    if r.status == 200:
                        return await r.json()
        except Exception as e:
            logger.error(f"[autotrade] Quote error: {e}")
        return None

    async def _get_swap_tx(self, quote: dict, user_pubkey: str) -> Optional[str]:
        payload = {
            "quoteResponse": quote,
            "userPublicKey": user_pubkey,
            "wrapAndUnwrapSol": True,
            "dynamicComputeUnitLimit": True,
            "prioritizationFeeLamports": 1000,
        }
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(JUPITER_SWAP_URL, json=payload, timeout=aiohttp.ClientTimeout(total=15)) as r:
                    if r.status == 200:
                        data = await r.json()
                        return data.get("swapTransaction")
        except Exception as e:
            logger.error(f"[autotrade] Swap tx error: {e}")
        return None

    async def _sign_and_send(self, keypair, swap_tx_b64: str) -> Optional[str]:
        """Deserialize, sign, and send the versioned transaction."""
        try:
            from solders.transaction import VersionedTransaction
            from solders.message import to_bytes_versioned
            import base64 as b64

            raw = b64.b64decode(swap_tx_b64)
            tx = VersionedTransaction.from_bytes(raw)
            signed = VersionedTransaction(tx.message, [keypair])
            serialized = bytes(signed)

            result = await rpc.call(
                "sendTransaction",
                [b64.b64encode(serialized).decode(), {"encoding": "base64", "skipPreflight": False}]
            )
            return result
        except Exception as e:
            logger.error(f"[autotrade] Sign/send error: {e}")
            return None

    async def _get_wallet(self, db: AsyncSession, telegram_id: int) -> Optional[UserWallet]:
        result = await db.execute(select(UserWallet).where(UserWallet.telegram_id == telegram_id))
        return result.scalar_one_or_none()


autotrader = AutoTrader()
