from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from datetime import datetime
from models.token import TokenData
from models.db import User, UserWallet, AutoTradeConfig, get_db
from utils.subscription import verify_payment, activate_subscription, check_subscription
from utils.wallet import generate_keypair, encrypt_private_key
from utils.logger import logger

# Hardcoded values
TREASURY_WALLET = "9xYzJYqJQh3xLvZ5XrWnMk2PqRt7YbVcNm4LkHgFdWp"
PRO_PRICE_SOL = 0.5

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
        "⚡ *NO-BRAIN-TRADE PRO*\n\n"
        "Free spike alerts (150%+) + Pro AI analysis\n\n"
        "/menu - Main menu\n"
        "/subscribe - Upgrade to Pro\n"
        "/wallet - Your trading wallet\n"
        "/verify <TX> - Verify payment",
        parse_mode="Markdown"
    )

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📊 Pro Status", callback_data="status")],
        [InlineKeyboardButton("💳 Subscribe Pro", callback_data="subscribe")],
        [InlineKeyboardButton("👛 My Wallet", callback_data="wallet")],
        [InlineKeyboardButton("🤖 Auto-Trade", callback_data="autotrade")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Main Menu:", reply_markup=reply_markup)

async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton(f"1 Month - {PRO_PRICE_SOL} SOL", callback_data="sub_1")],
        [InlineKeyboardButton(f"3 Months - {PRO_PRICE_SOL * 2.4} SOL", callback_data="sub_3")],
        [InlineKeyboardButton(f"6 Months - {PRO_PRICE_SOL * 4} SOL", callback_data="sub_6")],
        [InlineKeyboardButton("🔙 Back", callback_data="menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"💰 *Pro Subscription*\n\n"
        f"Price: {PRO_PRICE_SOL} SOL/month\n\n"
        f"Send SOL to:\n`{TREASURY_WALLET}`\n\n"
        f"Then /verify <TX_SIGNATURE>",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

async def wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    async for db in get_db():
        wallet = await db.get(UserWallet, user_id)
        
        if not wallet:
            priv_key, pub_key = generate_keypair()
            if priv_key:
                encrypted = encrypt_private_key(priv_key)
                new_wallet = UserWallet(
                    telegram_id=user_id,
                    public_key=pub_key,
                    encrypted_private_key=encrypted
                )
                db.add(new_wallet)
                await db.commit()
                wallet = new_wallet
        
        if wallet:
            await update.message.reply_text(
                f"👛 *Your Wallet*\n\n"
                f"Public Key:\n`{wallet.public_key}`\n\n"
                f"Send SOL here to fund auto-trading.",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text("Failed to create wallet. Please try again.")

async def verify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("Usage: /verify <TX_SIGNATURE>")
        return
    
    tx_signature = context.args[0]
    
    if await verify_payment(tx_signature, PRO_PRICE_SOL):
        await activate_subscription(user_id, 1)
        await update.message.reply_text("✅ Pro activated! You now have full access.")
    else:
        await update.message.reply_text("❌ Verification failed. Please check transaction.")

async def autotrade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    async for db in get_db():
        config = await db.get(AutoTradeConfig, user_id)
        
        if not config:
            config = AutoTradeConfig(telegram_id=user_id)
            db.add(config)
            await db.commit()
        
        status = "✅ ENABLED" if config.enabled else "❌ DISABLED"
        await update.message.reply_text(
            f"🤖 *Auto-Trade Config*\n\n"
            f"Status: {status}\n"
            f"Trade amount: {config.trade_sol} SOL\n"
            f"Slippage: {config.slippage_bps/100}%\n",
            parse_mode="Markdown"
        )

async def broadcast_spike_alert(app, token: TokenData, spike_pct: float, pro_users: list, free_users: list):
    """Broadcast spike alert to users"""
    message = (
        f"🚨 *SPIKE ALERT!*\n\n"
        f"Token: *{token.symbol}*\n"
        f"Price: {token.price_sol:.8f} SOL\n"
        f"Spike: +{spike_pct:.1f}%\n"
    )
    
    for user_id in free_users + pro_users:
        try:
            await app.bot.send_message(user_id, message, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Failed to send to {user_id}: {e}")

def register(app):
    """Register all handlers"""
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CommandHandler("subscribe", subscribe))
    app.add_handler(CommandHandler("wallet", wallet))
    app.add_handler(CommandHandler("verify", verify))
    app.add_handler(CommandHandler("autotrade", autotrade))
    app.add_handler(CallbackQueryHandler(menu, pattern="menu"))
    app.add_handler(CallbackQueryHandler(subscribe, pattern="subscribe"))
