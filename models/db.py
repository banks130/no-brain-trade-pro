"""
models/db.py — No-Brain-Trade Pro
SQLAlchemy async ORM models: users, subscriptions, wallets, trades.
"""

from datetime import datetime
from sqlalchemy import (
    Column, String, Boolean, Float, Integer,
    DateTime, Text, BigInteger, ForeignKey, Index
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from config import DATABASE_URL

Base = declarative_base()

engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db():
    async with SessionLocal() as session:
        yield session


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# ── Users ─────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    telegram_id     = Column(BigInteger, primary_key=True)
    username        = Column(String(64), nullable=True)
    first_name      = Column(String(128), nullable=True)
    tier            = Column(String(16), default="free")      # free | pro
    is_active       = Column(Boolean, default=True)
    is_banned       = Column(Boolean, default=False)
    joined_at       = Column(DateTime, default=datetime.utcnow)
    last_seen       = Column(DateTime, default=datetime.utcnow)

    # Alert preferences
    alerts_enabled  = Column(Boolean, default=True)
    min_spike_pct   = Column(Float, default=150.0)
    min_safety_score = Column(Integer, default=0)

    subscriptions   = relationship("Subscription", back_populates="user")
    wallet          = relationship("UserWallet", back_populates="user", uselist=False)
    trades          = relationship("Trade", back_populates="user")
    autotrade_config = relationship("AutoTradeConfig", back_populates="user", uselist=False)


# ── Subscriptions ─────────────────────────────────────────────

class Subscription(Base):
    __tablename__ = "subscriptions"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id     = Column(BigInteger, ForeignKey("users.telegram_id"))
    tier            = Column(String(16), default="pro")
    starts_at       = Column(DateTime, default=datetime.utcnow)
    expires_at      = Column(DateTime, nullable=False)
    payment_tx      = Column(String(128), nullable=True)   # Solana tx signature
    payment_sol     = Column(Float, default=0.5)
    is_active       = Column(Boolean, default=True)

    user            = relationship("User", back_populates="subscriptions")

    __table_args__ = (Index("ix_sub_telegram_active", "telegram_id", "is_active"),)


# ── User Wallets (non-custodial managed keypairs) ─────────────

class UserWallet(Base):
    __tablename__ = "user_wallets"

    id                  = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id         = Column(BigInteger, ForeignKey("users.telegram_id"), unique=True)
    public_key          = Column(String(64), nullable=False)
    encrypted_secret    = Column(Text, nullable=False)   # AES-256 encrypted
    created_at          = Column(DateTime, default=datetime.utcnow)

    user                = relationship("User", back_populates="wallet")


# ── Auto-Trade Config ─────────────────────────────────────────

class AutoTradeConfig(Base):
    __tablename__ = "autotrade_configs"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id     = Column(BigInteger, ForeignKey("users.telegram_id"), unique=True)
    enabled         = Column(Boolean, default=False)
    trade_sol       = Column(Float, default=0.1)         # SOL per trade
    slippage_bps    = Column(Integer, default=300)       # 3%
    max_trades_day  = Column(Integer, default=10)
    min_spike_pct   = Column(Float, default=150.0)
    min_safety_score = Column(Integer, default=50)
    take_profit_pct = Column(Float, default=200.0)       # auto sell at +200%
    stop_loss_pct   = Column(Float, default=-30.0)       # auto sell at -30%

    user            = relationship("User", back_populates="autotrade_config")


# ── Trades ────────────────────────────────────────────────────

class Trade(Base):
    __tablename__ = "trades"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id     = Column(BigInteger, ForeignKey("users.telegram_id"))
    mint            = Column(String(64), nullable=False)
    symbol          = Column(String(32), default="???")
    action          = Column(String(8), nullable=False)   # buy | sell
    sol_amount      = Column(Float, nullable=False)
    token_amount    = Column(Float, default=0.0)
    price_sol       = Column(Float, default=0.0)
    tx_signature    = Column(String(128), nullable=True)
    status          = Column(String(16), default="pending")  # pending|confirmed|failed
    created_at      = Column(DateTime, default=datetime.utcnow)
    confirmed_at    = Column(DateTime, nullable=True)
    pnl_pct         = Column(Float, nullable=True)

    user            = relationship("User", back_populates="trades")

    __table_args__ = (Index("ix_trades_telegram_mint", "telegram_id", "mint"),)


# ── Token Cache ───────────────────────────────────────────────

class TokenCache(Base):
    __tablename__ = "token_cache"

    mint            = Column(String(64), primary_key=True)
    symbol          = Column(String(32), default="???")
    name            = Column(String(128), default="Unknown")
    spike_pct       = Column(Float, default=0.0)
    safety_score    = Column(Integer, default=100)
    liquidity_sol   = Column(Float, default=0.0)
    holder_count    = Column(Integer, default=0)
    tags            = Column(Text, default="")          # JSON array as text
    last_updated    = Column(DateTime, default=datetime.utcnow)
