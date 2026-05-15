"""
utils/subscription.py — No-Brain-Trade Pro
Subscription management: create, verify, expire, check.
"""

import asyncio
import aiohttp
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from models.db import User, Subscription, UserWallet, AutoTradeConfig
from utils.wallet import generate_keypair
from utils.rpc import rpc
from config import (
    TREASURY_WALLET, PRO_PRICE_SOL, PRO_DURATION_DAYS, SOLANA_RPC_URL
)
from utils.logger import logger


async def get_or_create_user(db: AsyncSession, telegram_id: int, username: str = None, first_name: str = None) -> User:
    result = await db.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if not user:
        user = User(telegram_id=telegram_id, username=username, first_name=first_name)
        db.add(user)
        await db.commit()
        await db.refresh(user)
    else:
        user.last_seen = datetime.utcnow()
        if username:
            user.username = username
        await db.commit()
    return user


async def get_or_create_wallet(db: AsyncSession, telegram_id: int) -> UserWallet:
    result = await db.execute(select(UserWallet).where(UserWallet.telegram_id == telegram_id))
    wallet = result.scalar_one_or_none()
    if not wallet:
        kp = generate_keypair()
        wallet = UserWallet(
            telegram_id=telegram_id,
            public_key=kp["public_key"],
            encrypted_secret=kp["encrypted_secret"],
        )
        db.add(wallet)
        await db.commit()
        await db.refresh(wallet)
    return wallet


async def is_pro(db: AsyncSession, telegram_id: int) -> bool:
    result = await db.execute(
        select(Subscription).where(
            Subscription.telegram_id == telegram_id,
            Subscription.is_active == True,
            Subscription.expires_at > datetime.utcnow(),
        )
    )
    return result.scalar_one_or_none() is not None


async def activate_pro(db: AsyncSession, telegram_id: int, tx_sig: str) -> Subscription:
    """Activate Pro subscription after payment verified."""
    sub = Subscription(
        telegram_id=telegram_id,
        tier="pro",
        starts_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(days=PRO_DURATION_DAYS),
        payment_tx=tx_sig,
        payment_sol=PRO_PRICE_SOL,
        is_active=True,
    )
    db.add(sub)
    # Update user tier
    await db.execute(update(User).where(User.telegram_id == telegram_id).values(tier="pro"))
    await db.commit()
    await db.refresh(sub)
    logger.info(f"[sub] Pro activated for {telegram_id} | expires {sub.expires_at.date()}")
    return sub


async def verify_payment(tx_sig: str, from_wallet: str = None) -> bool:
    """
    Verify a Solana transaction sent >= PRO_PRICE_SOL to TREASURY_WALLET.
    Returns True if valid payment found.
    """
    if not TREASURY_WALLET:
        logger.warning("[sub] TREASURY_WALLET not configured")
        return False

    tx = await rpc.get_transaction(tx_sig)
    if not tx:
        logger.warning(f"[sub] Could not fetch tx {tx_sig[:16]}")
        return False

    try:
        meta = tx.get("meta", {})
        if meta.get("err"):
            return False

        accounts = (tx.get("transaction", {})
                      .get("message", {})
                      .get("accountKeys", []))

        pre_balances  = meta.get("preBalances", [])
        post_balances = meta.get("postBalances", [])

        # Find TREASURY_WALLET index
        for i, acct in enumerate(accounts):
            addr = acct if isinstance(acct, str) else acct.get("pubkey", "")
            if addr == TREASURY_WALLET:
                sol_received = (post_balances[i] - pre_balances[i]) / 1e9
                if sol_received >= PRO_PRICE_SOL * 0.98:  # 2% tolerance
                    logger.info(f"[sub] Payment verified: {sol_received:.3f} SOL from tx {tx_sig[:16]}")
                    return True
        return False
    except Exception as e:
        logger.error(f"[sub] Payment verify error: {e}")
        return False


async def expire_subscriptions(db: AsyncSession):
    """Mark expired subscriptions and downgrade users. Run periodically."""
    now = datetime.utcnow()
    result = await db.execute(
        select(Subscription).where(
            Subscription.is_active == True,
            Subscription.expires_at <= now,
        )
    )
    expired = result.scalars().all()
    for sub in expired:
        sub.is_active = False
        await db.execute(
            update(User).where(User.telegram_id == sub.telegram_id).values(tier="free")
        )
        logger.info(f"[sub] Expired: {sub.telegram_id}")
    if expired:
        await db.commit()


async def get_subscription_info(db: AsyncSession, telegram_id: int) -> Optional[Subscription]:
    result = await db.execute(
        select(Subscription).where(
            Subscription.telegram_id == telegram_id,
            Subscription.is_active == True,
        ).order_by(Subscription.expires_at.desc())
    )
    return result.scalar_one_or_none()
