import base58
from datetime import datetime, timedelta
from sqlalchemy import select, update
from models.db import SessionLocal, User, Subscription
from config import PRO_DURATION_DAYS, TREASURY_WALLET, PRO_PRICE_SOL
from utils.logger import logger

async def verify_payment(tx_signature: str, expected_amount: float) -> bool:
    try:
        base58.b58decode(tx_signature)
        logger.info(f"[sub] Verifying payment: {tx_signature[:16]}...")
        # Add actual Solana RPC verification here
        return True
    except Exception as e:
        logger.error(f"[sub] Verification failed: {e}")
        return False

async def activate_subscription(telegram_id: int, months: int):
    async with SessionLocal() as db:
        expires_at = datetime.utcnow() + timedelta(days=PRO_DURATION_DAYS * months)
        await db.execute(
            update(User)
            .where(User.telegram_id == telegram_id)
            .values(tier="pro", subscribed_until=expires_at)
        )
        await db.commit()
        logger.info(f"[sub] Activated pro for {telegram_id} for {months} months")

async def expire_subscriptions(db):
    result = await db.execute(
        update(User)
        .where(User.subscribed_until < datetime.utcnow())
        .where(User.tier == "pro")
        .values(tier="free")
    )
    await db.commit()
    return result.rowcount

async def check_subscription(telegram_id: int) -> bool:
    async with SessionLocal() as db:
        result = await db.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        if user and user.tier == "pro" and user.subscribed_until:
            return user.subscribed_until > datetime.utcnow()
    return False
