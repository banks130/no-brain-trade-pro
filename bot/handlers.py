from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from datetime import datetime
from models.token import TokenData
from models.db import User, get_db
from utils.logger import logger
import asyncio

# Your bot token from config
TELEGRAM_BOT_TOKEN = "8487846380:AAH6rY0zH2vxFtJ2M3IuJMVTZ0Z9ghE2L-s"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username
    
    async for db in get_db():
        existing = await db.get(User, user_id)
        if not existing:
            new_user = User(telegram_id=user_id, username=username, tier="free")
            db.add(new_user)
            await db.commit()
    
    await update.message.reply_text(
        "⚡ *NO-BRAIN-TRADE PRO* ⚡\n\n"
        "✅ Bot is ONLINE\n"
        "📊 Real-time pump.fun spike alerts\n"
        "🚀 150%+ spikes detected instantly\n\n"
        "Use /status to check your subscription\n"
        "Use /alerts to enable/disable alerts",
        parse_mode="Markdown"
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    async for db in get_db():
        user = await db.get(User, user_id)
        tier = user.tier if user else "free"
        
    await update.message.reply_text(
        f"📊 *Your Status*\n\n"
        f"👤 User: @{update.effective_user.username}\n"
        f"💎 Tier: *{tier.upper()}*\n"
        f"🔔 Alerts: {'ON' if user and user.alerts_enabled else 'OFF'}\n\n"
        f"Pro features:\n"
        f"• AI analysis\n"
        f"• Auto-trading\n"
        f"• Bundle detection",
        parse_mode="Markdown"
    )

async def alerts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    async for db in get_db():
        user = await db.get(User, user_id)
        if user:
            user.alerts_enabled = not user.alerts_enabled
            await db.commit()
            status = "ON" if user.alerts_enabled else "OFF"
            await update.message.reply_text(f"🔔 Alerts turned *{status}*", parse_mode="Markdown")
        else:
            await update.message.reply_text("Please /start first")

async def broadcast_spike_alert(app, token: TokenData, spike_pct: float, pro_users: list, free_users: list):
    """Broadcast spike alert to ALL users"""
    message = (
        f"🚨 *SPIKE ALERT!* 🚨\n\n"
        f"💰 *{token.symbol}*\n"
        f"📈 Price: `{token.price_sol:.8f} SOL`\n"
        f"⚡ Spike: *+{spike_pct:.0f}%*\n"
        f"🔗 [View Chart](https://dexscreener.com/solana/{token.mint})"
    )
    
    # Send to all users (both free and pro)
    all_users = list(set(free_users + pro_users))
    
    for user_id in all_users:
        try:
            await app.bot.send_message(
                user_id, 
                message, 
                parse_mode="Markdown",
                disable_web_page_preview=True
            )
            logger.info(f"[bot] Sent spike alert to {user_id}")
            await asyncio.sleep(0.1)  # Avoid rate limits
        except Exception as e:
            logger.error(f"[bot] Failed to send to {user_id}: {e}")

def register(app):
    """Register all handlers"""
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("alerts", alerts))p
