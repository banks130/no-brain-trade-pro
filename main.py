"""
main.py — No-Brain-Trade Pro
Production entry point.
Runs: Scanner + Spike Detector + DeepNet AI + Telegram Bot + Web Dashboard
All in a single asyncio event loop.
"""

import asyncio
import sys
from datetime import datetime
from sqlalchemy import select

# ── Core pipeline ─────────────────────────────────────────────
from core.scanner import PumpFunScanner
from core.spike_detector import SpikeDetector
from core.trending_engine import TrendingEngine
from core.autotrade import autotrader

# ── AI ────────────────────────────────────────────────────────
from deepnet_ai.analyzer import deepnet

# ── Models ────────────────────────────────────────────────────
from models.token import TokenData
from models.db import init_db, SessionLocal, User

# ── Bot ───────────────────────────────────────────────────────
from telegram.ext import Application
from bot.handlers import register, broadcast_spike_alert

# ── Web ───────────────────────────────────────────────────────
from web.app import app as fastapi_app, push_to_web
import uvicorn

# ── Utils ─────────────────────────────────────────────────────
from utils.subscription import expire_subscriptions
from utils.logger import logger
from config import (
    TELEGRAM_BOT_TOKEN, WEB_HOST, WEB_PORT,
    SPIKE_THRESHOLD_PCT
)

# ── Globals ───────────────────────────────────────────────────
scanner         = PumpFunScanner()
spike_detector  = SpikeDetector()
trending_engine = TrendingEngine()
_analysis_queue: asyncio.Queue = asyncio.Queue(maxsize=500)
tg_app: Application = None


# ── Scanner callbacks ─────────────────────────────────────────

@scanner.on_new_token
async def on_new_token(token: TokenData):
    trending_engine.ingest(token)
    push_to_web(token, "token")
    try:
        _analysis_queue.put_nowait(("fast", token))
    except asyncio.QueueFull:
        pass


@scanner.on_trade
async def on_trade(token: TokenData, msg: dict):
    await spike_detector.process(token)
    trending_engine.ingest(token)


# ── Spike callback ────────────────────────────────────────────

@spike_detector.on_spike
async def on_spike(token: TokenData, spike_pct: float):
    logger.info(f"[spike] ⚡ {token.symbol} +{spike_pct:.0f}%")
    push_to_web(token, "spike")
    try:
        _analysis_queue.put_nowait(("full", token, spike_pct))
    except asyncio.QueueFull:
        pass


# ── Analysis worker ───────────────────────────────────────────

async def analysis_worker():
    while True:
        job = await _analysis_queue.get()
        try:
            job_type = job[0]

            if job_type == "fast":
                token = await deepnet.analyze(job[1], fast=True)
                trending_engine.ingest(token)
                push_to_web(token, "token")

            elif job_type == "full":
                token: TokenData = job[1]
                spike_pct: float = job[2]

                # Full DeepNet analysis
                token = await deepnet.analyze(token, fast=False)
                trending_engine.ingest(token)
                push_to_web(token, "spike")

                # Get user lists for broadcasting
                free_users, pro_users = await _get_user_lists()

                # Broadcast alert
                if tg_app:
                    await broadcast_spike_alert(tg_app, token, spike_pct, pro_users, free_users)

                # Auto-trade for Pro users who have it enabled
                if pro_users:
                    asyncio.create_task(
                        _run_autotrades(token, spike_pct, pro_users)
                    )

        except Exception as e:
            logger.error(f"[worker] {e}")
        finally:
            _analysis_queue.task_done()
        await asyncio.sleep(0.01)


async def _get_user_lists() -> tuple[list[int], list[int]]:
    """Return (free_user_ids, pro_user_ids) with alerts enabled."""
    free_users, pro_users = [], []
    async with SessionLocal() as db:
        try:
            result = await db.execute(
                select(User).where(User.is_active == True, User.is_banned == False, User.alerts_enabled == True)
            )
            users = result.scalars().all()
            for u in users:
                if u.tier == "pro":
                    pro_users.append(u.telegram_id)
                else:
                    free_users.append(u.telegram_id)
        except Exception as e:
            logger.error(f"[users] {e}")
    return free_users, pro_users


async def _run_autotrades(token: TokenData, spike_pct: float, pro_user_ids: list[int]):
    """Fire auto-trades for all eligible Pro users."""
    async with SessionLocal() as db:
        for uid in pro_user_ids:
            try:
                should, reason = await autotrader.should_trade(db, uid, token)
                if should:
                    from models.db import AutoTradeConfig
                    from sqlalchemy import select as sel
                    cfg_r = await db.execute(sel(AutoTradeConfig).where(AutoTradeConfig.telegram_id == uid))
                    cfg = cfg_r.scalar_one_or_none()
                    trade_sol = cfg.trade_sol if cfg else 0.1
                    slippage  = cfg.slippage_bps if cfg else 300

                    tx = await autotrader.execute_buy(db, uid, token, trade_sol, slippage)
                    if tx and tg_app:
                        await tg_app.bot.send_message(
                            uid,
                            f"🤖 *AUTO-BUY*\n\n"
                            f"`{token.symbol}` | {trade_sol} SOL\n"
                            f"Spike: +{spike_pct:.0f}%\n"
                            f"TX: `{tx[:20]}...`\n"
                            f"[View](https://solscan.io/tx/{tx})",
                            parse_mode="Markdown",
                            disable_web_page_preview=True,
                        )
            except Exception as e:
                logger.error(f"[autotrade] uid={uid}: {e}")


# ── Maintenance tasks ─────────────────────────────────────────

async def maintenance_loop():
    """Expire subs, prune trending, run housekeeping every 5 min."""
    while True:
        await asyncio.sleep(300)
        try:
            async with SessionLocal() as db:
                await expire_subscriptions(db)
        except Exception as e:
            logger.error(f"[maintenance] {e}")


# ── Web server ────────────────────────────────────────────────

async def run_web():
    config = uvicorn.Config(fastapi_app, host=WEB_HOST, port=WEB_PORT,
                            log_level="warning", access_log=False)
    server = uvicorn.Server(config)
    await server.serve()


# ── Main ──────────────────────────────────────────────────────

async def main():
    global tg_app

    logger.info("=" * 50)
    logger.info("  NO-BRAIN-TRADE PRO — Starting")
    logger.info(f"  Spike threshold: +{SPIKE_THRESHOLD_PCT}%")
    logger.info("=" * 50)

    # Init database
    await init_db()
    logger.info("[db] Database ready")

    # Init Telegram bot
    if TELEGRAM_BOT_TOKEN:
        tg_app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        register(tg_app)
        await tg_app.initialize()
        await tg_app.start()
        await tg_app.updater.start_polling(drop_pending_updates=True)
        logger.info("[bot] Telegram bot started")
    else:
        logger.warning("[bot] No TELEGRAM_BOT_TOKEN — bot disabled")

    # Start all tasks
    tasks = [
        asyncio.create_task(scanner.run(),              name="scanner"),
        asyncio.create_task(analysis_worker(),           name="analysis"),
        asyncio.create_task(trending_engine.run_loop(),  name="trending"),
        asyncio.create_task(maintenance_loop(),           name="maintenance"),
        asyncio.create_task(run_web(),                   name="web"),
    ]

    logger.info(f"[web] Dashboard: http://{WEB_HOST}:{WEB_PORT}")
    logger.info("[main] All systems running ✓")

    try:
        await asyncio.gather(*tasks)
    except Exception as e:
        logger.error(f"[main] Fatal: {e}")
    finally:
        logger.info("[main] Shutting down...")
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
        print("\nShutdown.")
        sys.exit(0)
