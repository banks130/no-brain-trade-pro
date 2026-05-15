from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Integer, Boolean, DateTime, Float, Text, Index
from datetime import datetime
from typing import Optional, List, Dict
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./nobraintrade.db")

if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

engine = create_async_engine(DATABASE_URL, echo=False, pool_size=10, max_overflow=20)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(unique=True, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tier: Mapped[str] = mapped_column(default="free")
    is_active: Mapped[bool] = mapped_column(default=True)
    is_banned: Mapped[bool] = mapped_column(default=False)
    alerts_enabled: Mapped[bool] = mapped_column(default=True)
    subscribed_until: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

class Subscription(Base):
    __tablename__ = "subscriptions"
    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(index=True)
    tx_signature: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    amount_sol: Mapped[float]
    months: Mapped[int]
    status: Mapped[str] = mapped_column(default="pending")
    verified_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

class UserWallet(Base):
    __tablename__ = "user_wallets"
    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(unique=True, index=True)
    public_key: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    encrypted_private_key: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

class AutoTradeConfig(Base):
    __tablename__ = "auto_trade_config"
    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(unique=True, index=True)
    enabled: Mapped[bool] = mapped_column(default=False)
    trade_sol: Mapped[float] = mapped_column(default=0.1)
    slippage_bps: Mapped[int] = mapped_column(default=300)
    take_profit_pct: Mapped[Optional[float]] = mapped_column(nullable=True)
    stop_loss_pct: Mapped[Optional[float]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

class Trade(Base):
    __tablename__ = "trades"
    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(index=True)
    token_mint: Mapped[str] = mapped_column(String(100), index=True)
    token_symbol: Mapped[str] = mapped_column(String(20))
    trade_type: Mapped[str] = mapped_column(String(10))
    amount_sol: Mapped[float]
    token_amount: Mapped[float]
    price_sol: Mapped[float]
    tx_signature: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    status: Mapped[str] = mapped_column(default="pending")
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

class TokenCache(Base):
    __tablename__ = "token_cache"
    id: Mapped[int] = mapped_column(primary_key=True)
    mint: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    symbol: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(200))
    price_sol: Mapped[float] = mapped_column(default=0.0)
    spike_pct: Mapped[float] = mapped_column(default=0.0)
    volume_24h_usd: Mapped[float] = mapped_column(default=0.0)
    liquidity_sol: Mapped[float] = mapped_column(default=0.0)
    holder_count: Mapped[int] = mapped_column(default=0)
    deepnet_score: Mapped[float] = mapped_column(default=0.0)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("[db] Database initialized")

async def get_db():
    async with SessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
