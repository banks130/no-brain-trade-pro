"""
main.py — No-Brain-Trade Pro
Entry point with improved error handling for Railway deployment
"""

import asyncio
import sys
import os
import traceback

# Set working directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

print("=== NO-BRAIN-TRADE PRO STARTING ===", flush=True)
print(f"Python version: {sys.version}", flush=True)
print(f"Working directory: {os.getcwd()}", flush=True)

# Import with error handling
try:
    from datetime import datetime
    from sqlalchemy import select
    print("[boot] Core imports OK", flush=True)
except Exception as e:
    print(f"[boot] FATAL core import: {e}", flush=True)
    traceback.print_exc()
    sys.exit(1)

try:
    from config import (
        TELEGRAM_BOT_TOKEN, WEB_HOST, WEB_PORT, SPIKE_THRESHOLD_PCT,
        DATABASE_URL
    )
    print(f"[boot] Config OK | spike threshold: +{SPIKE_THRESHOLD_PCT}%", flush=True)
    print(f"[boot] Database URL: {DATABASE_URL[:50]}..." if DATABASE_URL else "[boot] No DB URL", flush=True)
except Exception as e:
    print(f"[boot] FATAL config: {e}", flush=True)
    traceback.print_exc()
    sys.exit(1)

try:
    from models.token import TokenData
    from models.db import init_db, SessionLocal, User
    print("[boot] Models OK", flush=True)
except Exception as e:
    print(f"[boot] FATAL models: {e}", flush=True)
    traceback.print_exc()
    sys.exit(1)

try:
    from core.scanner import PumpFunScanner
    from core.spike_detector import SpikeDetector
    from core.trending_engine import TrendingEngine
    print("[boot] Core pipeline OK", flush=True)
except Exception as e:
    print(f"[boot] FATAL core pipeline: {e}", flush=True)
    traceback.print_exc()
    sys.exit(1)

try:
    from deepnet_ai.analyzer import deepnet
    print("[boot] DeepNet AI OK", flush=True)
except Exception as e:
    print(f"[boot] FATAL deepnet: {e}", flush=True)
    traceback.print_exc()
    sys.exit(1)

try:
    from bot.handlers import register, broadcast_spike_alert
    from telegram.ext import Application
    print("[boot] Bot handlers OK", flush=True)
except Exception as e:
    print(f"[boot] FATAL bot: {e}", flush=True)
    traceback.print_exc()
    # Don't exit - bot is optional
    TELEGRAM_BOT_TOKEN = None

try:
    from web.app import app as fastapi_app, push_to_web
    import uvicorn
    print("[boot] Web OK", flush=True)
except Exception as e:
    print(f"[boot] FATAL web: {e}", flush=True)
    traceback.print_exc()
    sys.exit(1)

try:
    from utils.subscription import expire_subscriptions
    from utils.logger import logger
    print("[boot] Utils OK", flush=True)
except Exception as e:
    print(f"[boot] FATAL utils: {e}", flush=True)
    traceback.print_exc()
    sys.exit(1)

# ── Globals ───────────────────────────────────────────────────
scanner = None
spike_detector = None
trending_engine = None
_queue = None
tg_app = None


# ── Scanner callbacks ─────────────────────────────────────────

def setup_callbacks():
    global scanner, spike_detector, trending_engine, _queue
    
    @scanner.on_new_token
    async def on_new_token(token: TokenData):
        trending_engine.ingest(token)
        push_to_web(token, "token")
        try:
            _queue.put_nowait(("fast", token))
        except asyncio.QueueFull:
            pass

    @scanner.on_trade
    async def on_trade(token: TokenData, msg: dict):
        await spike_detector.process(token)
        trending_engine.ingest(token)


# ── Spike callback ────────────────────────────────────────────

def setup_spike_callback():
    global spike_detector, trending_engine, _queue, tg_app
    
    @spike_detector.on_spike
    async def on_spike(token: TokenData, spike_pct: float):
        logger.info(f"[spike] ⚡ {token.symbol} +{spike_pct:.0f}%")
        push_to_web(token, "spike")
        try:
            _queue.put_nowait(("full", token, spike_pct))
        except asyncio.QueueFull:
            pass


# ── Analysis worker ───────────────────────────────────────────

async def analysis_worker():
    while True:
        job = await _queue.get()
        try:
            if job[0] == "fast":
                token = await deepnet.analyze(job[1], fast=True)
                trending_engine.ingest(token)
                push_to_web(token, "token")

            elif job[0] == "full":
                token: TokenData = job[1]
                spike_pct: float = job[2]
                token = await deepnet.analyze(token, fast=False)
                trending_engine.ingest(token)
                push_to_web(token, "spike")

                free_users, pro_users = await _get_users()
                if tg_app and TELEGRAM_BOT_TOKEN:
                    await broadcast_spike_alert(tg_app, token, spike_pct, pro_users, free_users)

                if pro_users:
                    asyncio.create_task(_autotrades(token, spike_pct, pro_users))

        except Exception as e:
            logger.error(f"[worker] {e}")
            traceback.print_exc()
        finally:
            _queue.task_done()
        await asyncio.sleep(0.01)


async def _get_users() -> tuple[list[int], list[int]]:
    free, pro = [], []
    try:
        async with SessionLocal() as db:
            result = await db.execute(
                select(User).where(
                    User.is_active == True,
                    User.is_banned == False,
                    User.alerts_enabled == True,
                )
            )
            for u in result.scalars().all():
                (pro if u.tier == "pro" else free).append(u.telegram_id)
    except Exception as e:
        logger.error(f"[users] {e}")
    return free, pro


async def _autotrades(token: TokenData, spike_pct: float, pro_ids: list[int]):
    try:
        from core.autotrade import autotrader
        from models.db import AutoTradeConfig
        async with SessionLocal() as db:
            for uid in pro_ids:
                try:
                    should, reason = await autotrader.should_trade(db, uid, token)
                    if not should:
                        continue
                    result = await db.execute(
                        select(AutoTradeConfig).where(AutoTradeConfig.telegram_id == uid)
                    )
                    cfg = result.scalar_one_or_none()
                    sol = cfg.trade_sol if cfg else 0.1
                    slip = cfg.slippage_bps if cfg else 300
                    tx = await autotrader.execute_buy(db, uid, token, sol, slip)
                    if tx and tg_app:
                        await tg_app.bot.send_message(
                            uid,
                            f"🤖 *AUTO-BUY*\n\n`{token.symbol}` | {sol} SOL\n"
                            f"Spike: +{spike_pct:.0f}%\nTX: `{tx[:20]}...`\n"
                            f"[View](https://solscan.io/tx/{tx})",
                            parse_mode="Markdown",
                            disable_web_page_preview=True,
                        )
                except Exception as e:
                    logger.error(f"[autotrade] uid={uid}: {e}")
    except ImportError:
        pass


async def maintenance_loop():
    while True:
        await asyncio.sleep(300)
        try:
            async with SessionLocal() as db:
                await expire_subscriptions(db)
            if spike_detector:
                await spike_detector.cleanup_old_tokens()
        except Exception as e:
            logger.error(f"[maintenance] {e}")


async def run_web():
    config = uvicorn.Config(
        fastapi_app,
        host=WEB_HOST,
        port=WEB_PORT,
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(config)
    await server.serve()


# ── Main ──────────────────────────────────────────────────────

async def main():
    global scanner, spike_detector, trending_engine, _queue, tg_app

    print("[main] Initializing components...", flush=True)
    
    # Initialize database
    print("[main] Initializing DB...", flush=True)
    await init_db()
    print("[main] DB ready", flush=True)
    
    # Initialize core components
    scanner = PumpFunScanner()
    spike_detector = SpikeDetector()
    trending_engine = TrendingEngine()
    _queue = asyncio.Queue(maxsize=500)
    
    # Setup callbacks
    setup_callbacks()
    setup_spike_callback()

    # Initialize Telegram bot if token available
    if TELEGRAM_BOT_TOKEN and TELEGRAM_BOT_TOKEN != "":
        print("[main] Starting Telegram bot...", flush=True)
        try:
            tg_app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
            register(tg_app)
            await tg_app.initialize()
            await tg_app.start()
            await tg_app.updater.start_polling(drop_pending_updates=True)
            print("[main] Telegram bot running ✓", flush=True)
        except Exception as e:
            print(f"[main] WARNING: Telegram bot failed: {e}", flush=True)
            tg_app = None
    else:
        print("[main] WARNING: No TELEGRAM_BOT_TOKEN set", flush=True)
        tg_app = None

    print(f"[main] Starting web on port {WEB_PORT}...", flush=True)
    print(f"[main] Starting scanner...", flush=True)

    tasks = [
        asyncio.create_task(scanner.run(), name="scanner"),
        asyncio.create_task(analysis_worker(), name="analysis"),
        asyncio.create_task(trending_engine.run_loop(), name="trending"),
        asyncio.create_task(maintenance_loop(), name="maintenance"),
        asyncio.create_task(run_web(), name="web"),
    ]

    print("[main] All systems go ✓", flush=True)

    try:
        await asyncio.gather(*tasks)
    except Exception as e:
        logger.error(f"[main] Fatal: {e}")
        traceback.print_exc()
    finally:
        if scanner:
            scanner.stop()
        if tg_app:
            await tg_app.updater.stop()
            await tg_app.stop()
            await tg_app.shutdown()
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Shutdown.")
        sys.exit(0)
    except Exception as e:
        print(f"Fatal error: {e}")
        traceback.print_exc()
        sys.exit(1)
