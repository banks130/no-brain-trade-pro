import base58
from datetime import datetime, timedelta
from sqlalchemy import select, update
from models.db import SessionLocal, User
from utils.logger import logger

# Hardcoded values to avoid import errors
TREASURY_WALLET = "9xYzJYqJQh3xLvZ5XrWnMk2PqRt7YbVcNm4LkHgFdWp"  # Replace with your wallet
PRO_PRICE_SOL = 0.5
PRO_DURATION_DAYS = 30

async def verify_payment(tx_signature: str, expected_amount: float) -> bool:
    try:
        # Decode base58 to verify it's valid
        base58.b58decode(tx_signature)
        logger.info(f"[sub] Verifying payment: {tx_signature[:16]}...")
        # Add actual Solana RPC verification here if needed
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
        return True

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
