"""
models/db.py — Database models for No-Brain-Trade Pro
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, Boolean, DateTime, Float, Text, Index
from datetime import datetime
from typing import Optional
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./nobraintrade.db")

# Convert postgresql:// to postgresql+asyncpg:// for async support
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(unique=True, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tier: Mapped[str] = mapped_column(default="free")  # free/pro
    is_active: Mapped[bool] = mapped_column(default=True)
    is_banned: Mapped[bool] = mapped_column(default=False)
    alerts_enabled: Mapped[bool] = mapped_column(default=True)
    subscribed_until: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    
    # Relationships
    wallet: Mapped[Optional["UserWallet"]] = relationship(back_populates="user", uselist=False)
    auto_config: Mapped[Optional["AutoTradeConfig"]] = relationship(back_populates="user", uselist=False)
    trades: Mapped[list["Trade"]] = relationship(back_populates="user")


class UserWallet(Base):
    __tablename__ = "user_wallets"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(unique=True, index=True)
    public_key: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    encrypted_private_key: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    last_used: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    
    # Relationships
    user: Mapped["User"] = relationship(back_populates="wallet", foreign_keys=[telegram_id])


class AutoTradeConfig(Base):
    __tablename__ = "auto_trade_config"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(unique=True, index=True)
    enabled: Mapped[bool] = mapped_column(default=False)
    trade_sol: Mapped[float] = mapped_column(default=0.1)
    slippage_bps: Mapped[int] = mapped_column(default=300)
    take_profit_pct: Mapped[Optional[float]] = mapped_column(nullable=True)
    stop_loss_pct: Mapped[Optional[float]] = mapped_column(nullable=True)
    max_trades_per_day: Mapped[int] = mapped_column(default=5)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user: Mapped["User"] = relationship(back_populates="auto_config", foreign_keys=[telegram_id])


class Trade(Base):
    __tablename__ = "trades"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(index=True)
    token_mint: Mapped[str] = mapped_column(String(100), index=True)
    token_symbol: Mapped[str] = mapped_column(String(20))
    trade_type: Mapped[str] = mapped_column(String(10))  # buy/sell
    amount_sol: Mapped[float]
    token_amount: Mapped[float]
    price_sol: Mapped[float]
    tx_signature: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    status: Mapped[str] = mapped_column(default="pending")  # pending/success/failed
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    
    # Relationships
    user: Mapped["User"] = relationship(foreign_keys=[telegram_id])
    
    __table_args__ = (
        Index('idx_user_token', 'telegram_id', 'token_mint'),
        Index('idx_created', 'created_at'),
    )


class Subscription(Base):
    __tablename__ = "subscriptions"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(index=True)
    tx_signature: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    amount_sol: Mapped[float]
    months: Mapped[int]
    status: Mapped[str] = mapped_column(default="pending")  # pending/verified/expired
    verified_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


async def init_db():
    """Initialize database tables"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("[db] Database initialized")


async def close_db():
    """Close database connections"""
    await engine.dispose()
