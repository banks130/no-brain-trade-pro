from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from datetime import datetime
from models.token import TokenData
from models.db import User, get_db
from utils.logger import logger

TREASURY_WALLET = "9xYzJYqJQh3xLvZ5XrWnMk2PqRt7YbVcNm4LkHgFdWp"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username
    
    async for db in get_db():
        existing = await db.get(User, user_id)
        if not existing:
            new_user = User(telegram_id=user_id, username=username)
            db.add(new_user)
            await db.commit()
    
    await update.message.reply_text(
        "⚡ *NO-BRAIN-TRADE PRO* ⚡\n\n"
        "Real-time pump.fun spike detection\n"
        "Free 150%+ spike alerts\n\n"
        "*/menu* - Main menu\n"
        "*/status* - Bot status\n"
        "*/wallet* - Your wallet\n\n"
        "🚀 Bot is live and watching for spikes!",
        parse_mode="Markdown"
    )

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📊 Status", callback_data="status")],
        [InlineKeyboardButton("👛 Wallet", callback_data="wallet")],
        [InlineKeyboardButton("ℹ️ Info", callback_data="info")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("📱 *Main Menu*", parse_mode="Markdown", reply_markup=reply_markup)

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    tier = "Free"
    
    async for db in get_db():
        user = await db.get(User, user_id)
        if user and user.tier == "pro":
            tier = "Pro ✅"
    
    await update.message.reply_text(
        f"📊 *Your Status*\n\n"
        f"User: @{update.effective_user.username}\n"
        f"Tier: {tier}\n"
        f"Bot: 🟢 Active\n\n"
        f"Spike threshold: 150%\n"
        f"Monitoring: pump.fun",
        parse_mode="Markdown"
    )

async def wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"👛 *Your Wallet Info*\n\n"
        f"Treasury: `{TREASURY_WALLET}`\n\n"
        f"Coming soon: Personal trading wallet",
        parse_mode="Markdown"
    )

async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "ℹ️ *No-Brain-Trade Pro*\n\n"
        "• Free spike alerts at 150%+\n"
        "• Pro tier: AI analysis + auto-trading\n"
        "• Non-custodial - you control keys\n\n"
        "Contact @admin for Pro access",
        parse_mode="Markdown"
    )

async def broadcast_spike_alert(app, token: TokenData, spike_pct: float, pro_users: list, free_users: list):
    """Broadcast spike alert to users"""
    message = (
        f"🚨 *SPIKE ALERT!* 🚨\n\n"
        f"💰 *{token.symbol}* ({token.name})\n"
        f"📈 Price: `{token.price_sol:.8f} SOL`\n"
        f"⚡ Spike: *+{spike_pct:.0f}%*\n"
        f"🔗 [View on DexScreener](https://dexscreener.com/solana/{token.mint})"
    )
    
    # Send to all users (limit to avoid rate limits)
    all_users = list(set(free_users + pro_users))[:100]  # Max 100 per spike
    
    for user_id in all_users:
        try:
            await app.bot.send_message(
                user_id, 
                message, 
                parse_mode="Markdown",
                disable_web_page_preview=True
            )
            await asyncio.sleep(0.05)  # Small delay to avoid rate limits
        except Exception as e:
            logger.error(f"Failed to send to {user_id}: {e}")

def register(app):
    """Register all handlers"""
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("wallet", wallet))
    app.add_handler(CommandHandler("info", info))
    app.add_handler(CallbackQueryHandler(lambda u,c: menu(u,c), pattern="menu"))
    app.add_handler(CallbackQueryHandler(lambda u,c: status(u,c), pattern="status"))
    app.add_handler(CallbackQueryHandler(lambda u,c: wallet(u,c), pattern="wallet"))
    app.add_handler(CallbackQueryHandler(lambda u,c: info(u,c), pattern="info"))
