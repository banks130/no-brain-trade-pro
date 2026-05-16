import asyncio
import sys
import os
import traceback

os.chdir(os.path.dirname(os.path.abspath(__file__)))

print("=== NO-BRAIN-TRADE PRO STARTING ===", flush=True)

try:
    from datetime import datetime
    from sqlalchemy import select
    print("[boot] Core imports OK", flush=True)
except Exception as e:
    print(f"[boot] FATAL: {e}", flush=True)
    sys.exit(1)

try:
    from config import TELEGRAM_BOT_TOKEN, WEB_HOST, WEB_PORT, SPIKE_THRESHOLD_PCT
    print(f"[boot] Config OK | spike: +{SPIKE_THRESHOLD_PCT}%", flush=True)
except Exception as e:
    print(f"[boot] Config error: {e}", flush=True)
    TELEGRAM_BOT_TOKEN = "8487846380:AAH6rY0zH2vxFtJ2M3IuJMVTZ0Z9ghE2L-s"
    WEB_HOST = "0.0.0.0"
    WEB_PORT = 8080
    SPIKE_THRESHOLD_PCT = 150

try:
    from models.token import TokenData
    from models.db import init_db, SessionLocal, User
    print("[boot] Models OK", flush=True)
except Exception as e:
    print(f"[boot] Models error: {e}", flush=True)
    sys.exit(1)

try:
    from core.scanner import PumpFunScanner
    from core.spike_detector import SpikeDetector
    from core.trending_engine import TrendingEngine
    print("[boot] Core pipeline OK", flush=True)
except Exception as e:
    print(f"[boot] Core error: {e}", flush=True)
    sys.exit(1)

try:
    from deepnet_ai.analyzer import deepnet
    print("[boot] DeepNet AI OK", flush=True)
except Exception as e:
    print(f"[boot] AI error: {e}", flush=True)
    deepnet = None

try:
    from bot.handlers import register, broadcast_spike_alert
    from telegram.ext import Application
    from telegram.request import HTTPXRequest
    print("[boot] Bot handlers OK", flush=True)
except Exception as e:
    print(f"[boot] Bot error: {e}", flush=True)
    broadcast_spike_alert = None

try:
    from web.app import app as fastapi_app, push_to_web
    import uvicorn
    print("[boot] Web OK", flush=True)
except Exception as e:
    print(f"[boot] Web error: {e}", flush=True)
    sys.exit(1)

try:
    from utils.logger import logger
    print("[boot] Logger OK", flush=True)
except Exception as e:
    print(f"[boot] Logger error: {e}", flush=True)
    import logging
    logger = logging.getLogger(__name__)

scanner = None
spike_detector = None
trending_engine = None
_queue = None
tg_app = None

async def analysis_worker():
    while True:
        job = await _queue.get()
        try:
            if job[0] == "fast":
                token = job[1]
                trending_engine.ingest(token)
                push_to_web(token, "token")
                logger.info(f"[worker] Processed: {token.symbol}")
                
            elif job[0] == "full":
                token = job[1]
                spike_pct = job[2]
                trending_engine.ingest(token)
                push_to_web(token, "spike")
                logger.info(f"[worker] 🚀 SPIKE: {token.symbol} +{spike_pct:.0f}%")
                
                # Send Telegram alerts
                if tg_app and broadcast_spike_alert:
                    # Get users
                    free_users = []
                    pro_users = []
                    async with SessionLocal() as db:
                        result = await db.execute(
                            select(User).where(User.alerts_enabled == True)
                        )
                        for user in result.scalars().all():
                            if user.tier == "pro":
                                pro_users.append(user.telegram_id)
                            else:
                                free_users.append(user.telegram_id)
                    
                    await broadcast_spike_alert(tg_app, token, spike_pct, pro_users, free_users)
                    
        except Exception as e:
            logger.error(f"[worker] {e}")
        finally:
            _queue.task_done()

async def main():
    global scanner, spike_detector, trending_engine, _queue, tg_app

    print("[main] Initializing...", flush=True)
    await init_db()
    
    scanner = PumpFunScanner()
    spike_detector = SpikeDetector()
    trending_engine = TrendingEngine()
    _queue = asyncio.Queue(maxsize=500)
    
    @scanner.on_new_token
    async def on_new_token(token: TokenData):
        logger.info(f"[scanner] 🆕 NEW: {token.symbol} | ${token.price_sol:.8f}")
        trending_engine.ingest(token)
        push_to_web(token, "token")
        await _queue.put(("fast", token))
        
        # Check for spike on new token
        if token.spike_pct >= SPIKE_THRESHOLD_PCT:
            await spike_detector.process(token)

    @scanner.on_trade
    async def on_trade(token: TokenData, msg: dict):
        await spike_detector.process(token)

    @spike_detector.on_spike
    async def on_spike(token: TokenData, spike_pct: float):
        logger.info(f"[spike] ⚡⚡⚡ {token.symbol} +{spike_pct:.0f}% ⚡⚡⚡")
        push_to_web(token, "spike")
        await _queue.put(("full", token, spike_pct))

    # Start Telegram Bot
    if TELEGRAM_BOT_TOKEN:
        print("[main] Starting Telegram bot...", flush=True)
        try:
            # Use HTTPXRequest for better connection
            request = HTTPXRequest(connect_timeout=30, read_timeout=30)
            tg_app = Application.builder().token(TELEGRAM_BOT_TOKEN).request(request).build()
            register(tg_app)
            await tg_app.initialize()
            await tg_app.start()
            await tg_app.updater.start_polling(drop_pending_updates=True)
            print("[main] ✅ Telegram bot running!", flush=True)
            
            # Send startup message to admin
            try:
                await tg_app.bot.send_message(123456789, "✅ No-Brain-Trade Pro Bot Started!")
            except:
                pass
                
        except Exception as e:
            print(f"[main] Bot failed: {e}", flush=True)
            tg_app = None

    # Start web server
    tasks = [
        asyncio.create_task(scanner.run(), name="scanner"),
        asyncio.create_task(analysis_worker(), name="analysis"),
        asyncio.create_task(run_web(), name="web"),
    ]
    
    print("[main] ✅ All systems go!", flush=True)
    
    try:
        await asyncio.gather(*tasks)
    except Exception as e:
        logger.error(f"[main] Fatal: {e}")

async def run_web():
    config = uvicorn.Config(fastapi_app, host=WEB_HOST, port=WEB_PORT, log_level="warning")
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Shutdown.")
        sys.exit(0)
