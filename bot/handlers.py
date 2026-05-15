"""
bot/handlers.py — No-Brain-Trade Pro
All Telegram bot handlers: /start, /subscribe, /wallet, /autotrade, alerts.
"""

from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
from telegram.constants import ParseMode
from models.db import SessionLocal, AutoTradeConfig
from models.token import TokenData
from utils.subscription import (
    get_or_create_user, get_or_create_wallet, is_pro,
    activate_pro, verify_payment, get_subscription_info
)
from utils.helpers import shorten_address, format_number
from utils.rpc import rpc
from config import (
    TELEGRAM_BOT_TOKEN, TREASURY_WALLET, PRO_PRICE_SOL,
    PRO_DURATION_DAYS, DEFAULT_TRADE_SOL, DEFAULT_SLIPPAGE_BPS,
    MAX_TRADE_SOL, ADMIN_CHAT_ID
)
from sqlalchemy import select, update
from utils.logger import logger


# ── Error Handler ─────────────────────────────────────────────

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors and notify user"""
    logger.error(f"Update {update} caused error {context.error}")
    print(f"ERROR: {context.error}")
    
    # Try to notify the user
    if update and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "⚠️ An error occurred. Please try again or contact support."
            )
        except:
            pass


# ── Test Command ──────────────────────────────────────────────

async def cmd_test(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Simple test command to verify bot is working"""
    try:
        user = update.effective_user
        logger.info(f"Test command received from {user.id}")
        print(f"Test command from {user.id}")
        await update.message.reply_text(
            "✅ <b>Bot is working!</b>\n\n"
            "Send /menu to get started with No-Brain-Trade Pro.",
            parse_mode=ParseMode.HTML
        )
        print(f"Test command succeeded for {user.id}")
    except Exception as e:
        logger.error(f"Test command failed: {e}")
        print(f"Test command error: {e}")
        await update.message.reply_text("❌ Error processing command. Please try again.")


# ── /start ────────────────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    print(f"Start command from {user.id}")
    async with SessionLocal() as db:
        await get_or_create_user(db, user.id, user.username, user.first_name)

    text = (
        "⚡ <b>NO-BRAIN-TRADE</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "Real-time pump.fun intelligence.\n\n"
        "🆓 <b>Free</b> — Spike alerts (150%+)\n"
        "💎 <b>Pro</b> — Full AI analysis + Auto-trade\n\n"
        "Use /menu to get started."
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


# ── /menu ─────────────────────────────────────────────────────

async def cmd_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    async with SessionLocal() as db:
        pro = await is_pro(db, user.id)

    tier_badge = "💎 PRO" if pro else "🆓 FREE"
    kb = [
        [
            InlineKeyboardButton("💎 Subscribe Pro", callback_data="sub_info"),
            InlineKeyboardButton("👜 My Wallet", callback_data="wallet_info"),
        ],
        [
            InlineKeyboardButton("⚙️ Auto-Trade", callback_data="at_menu"),
            InlineKeyboardButton("📊 My Trades", callback_data="my_trades"),
        ],
        [
            InlineKeyboardButton("🔔 Alert Settings", callback_data="alert_settings"),
            InlineKeyboardButton("ℹ️ Help", callback_data="help"),
        ],
    ]
    await update.message.reply_text(
        f"<b>NO-BRAIN-TRADE</b> | {tier_badge}",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(kb),
    )


# ── Subscription flow ─────────────────────────────────────────

async def cb_sub_info(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user

    async with SessionLocal() as db:
        pro = await is_pro(db, user.id)
        sub = await get_subscription_info(db, user.id)

    if pro and sub:
        days_left = (sub.expires_at - datetime.utcnow()).days
        text = (
            f"💎 <b>PRO ACTIVE</b>\n\n"
            f"Expires: <code>{sub.expires_at.strftime('%Y-%m-%d')}</code>\n"
            f"Days left: <code>{days_left}</code>\n\n"
            f"Auto-trade + full AI analysis enabled."
        )
        kb = [[InlineKeyboardButton("🔄 Renew", callback_data="sub_pay")]]
    else:
        text = (
            f"💎 <b>GO PRO</b>\n\n"
            f"Price: <code>{PRO_PRICE_SOL} SOL / month</code>\n\n"
            f"✅ Full DeepNet AI analysis\n"
            f"✅ Auto-trade on every spike\n"
            f"✅ Bundle + whale detection\n"
            f"✅ Dev safety scoring\n\n"
            f"Tap Subscribe to get your payment address."
        )
        kb = [[InlineKeyboardButton("💳 Subscribe Now", callback_data="sub_pay")]]

    await query.edit_message_text(text, parse_mode=ParseMode.HTML,
                                   reply_markup=InlineKeyboardMarkup(kb))


async def cb_sub_pay(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    text = (
        f"💳 <b>PAYMENT INSTRUCTIONS</b>\n\n"
        f"Send exactly <code>{PRO_PRICE_SOL} SOL</code> to:\n\n"
        f"<code>{TREASURY_WALLET}</code>\n\n"
        f"Then send your transaction signature here with:\n"
        f"<code>/verify &lt;TX_SIGNATURE&gt;</code>\n\n"
        f"⏳ Subscription activates within 1 minute of confirmation."
    )
    kb = [[InlineKeyboardButton("◀️ Back", callback_data="sub_info")]]
    await query.edit_message_text(text, parse_mode=ParseMode.HTML,
                                   reply_markup=InlineKeyboardMarkup(kb))


async def cmd_verify(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """User submits: /verify <TX_SIGNATURE>"""
    user = update.effective_user
    args = ctx.args
    if not args:
        await update.message.reply_text("Usage: <code>/verify &lt;TX_SIGNATURE&gt;</code>", parse_mode=ParseMode.HTML)
        return

    tx_sig = args[0].strip()
    msg = await update.message.reply_text("🔍 Verifying payment...")

    valid = await verify_payment(tx_sig)
    if valid:
        async with SessionLocal() as db:
            await activate_pro(db, user.id, tx_sig)
        await msg.edit_text(
            f"✅ <b>PRO ACTIVATED!</b>\n\n"
            f"Welcome to No-Brain-Trade Pro.\n"
            f"Valid for {PRO_DURATION_DAYS} days.\n\n"
            f"Use /menu → Auto-Trade to configure your bot.",
            parse_mode=ParseMode.HTML,
        )
        # Notify admin
        if ADMIN_CHAT_ID:
            await ctx.bot.send_message(
                ADMIN_CHAT_ID,
                f"💰 New Pro sub: @{user.username or user.id} | tx: {tx_sig[:20]}..."
            )
    else:
        await msg.edit_text(
            "❌ Payment not found or insufficient.\n\n"
            "Make sure you sent the correct amount to the correct address.\n"
            "Try again in a minute if the transaction is still confirming."
        )


# ── Wallet ────────────────────────────────────────────────────

async def cb_wallet_info(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user

    async with SessionLocal() as db:
        wallet = await get_or_create_wallet(db, user.id)

    balance = await rpc.get_balance(wallet.public_key)
    kb = [
        [InlineKeyboardButton("🔑 Export Private Key", callback_data="wallet_export")],
        [InlineKeyboardButton("◀️ Back", callback_data="menu")],
    ]
    await query.edit_message_text(
        f"👜 <b>YOUR WALLET</b>\n\n"
        f"Address:\n<code>{wallet.public_key}</code>\n\n"
        f"Balance: <code>{balance:.4f} SOL</code>\n\n"
        f"ℹ️ Fund this wallet with SOL to enable auto-trading.\n"
        f"You own the private key — funds are always yours.",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(kb),
    )


async def cb_wallet_export(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user

    async with SessionLocal() as db:
        from utils.wallet import load_keypair
        import base58
        wallet = await get_or_create_wallet(db, user.id)
        kp = load_keypair(wallet.encrypted_secret)
        private_b58 = base58.b58encode(bytes(kp)).decode()

    kb = [[InlineKeyboardButton("◀️ Back", callback_data="wallet_info")]]
    await query.edit_message_text(
        f"🔑 <b>PRIVATE KEY</b>\n\n"
        f"<code>{private_b58}</code>\n\n"
        f"⚠️ NEVER share this. Import into Phantom or Solflare.\n"
        f"Delete this message after saving.",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(kb),
    )


# ── Auto-Trade ────────────────────────────────────────────────

async def cb_at_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user

    async with SessionLocal() as db:
        pro = await is_pro(db, user.id)
        if not pro:
            await query.edit_message_text(
                "💎 <b>Pro required</b>\n\nAuto-trade is a Pro feature.",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("Subscribe", callback_data="sub_info")
                ]])
            )
            return

        result = await db.execute(
            select(AutoTradeConfig).where(AutoTradeConfig.telegram_id == user.id)
        )
        cfg = result.scalar_one_or_none()
        if not cfg:
            cfg = AutoTradeConfig(
                telegram_id=user.id,
                enabled=False,
                trade_sol=DEFAULT_TRADE_SOL,
                slippage_bps=DEFAULT_SLIPPAGE_BPS,
            )
            db.add(cfg)
            await db.commit()
            await db.refresh(cfg)

    status = "✅ ON" if cfg.enabled else "❌ OFF"
    toggle_label = "Turn OFF" if cfg.enabled else "Turn ON"
    kb = [
        [InlineKeyboardButton(f"🔄 {toggle_label}", callback_data="at_toggle")],
        [
            InlineKeyboardButton(f"💰 Trade size: {cfg.trade_sol} SOL", callback_data="at_size"),
            InlineKeyboardButton(f"📉 Slippage: {cfg.slippage_bps/100:.1f}%", callback_data="at_slip"),
        ],
        [
            InlineKeyboardButton(f"🎯 Min spike: {cfg.min_spike_pct:.0f}%", callback_data="at_spike"),
            InlineKeyboardButton(f"🛡 Min safety: {cfg.min_safety_score}", callback_data="at_safe"),
        ],
        [
            InlineKeyboardButton(f"🚀 TP: +{cfg.take_profit_pct:.0f}%", callback_data="at_tp"),
            InlineKeyboardButton(f"🛑 SL: {cfg.stop_loss_pct:.0f}%", callback_data="at_sl"),
        ],
        [InlineKeyboardButton("◀️ Back", callback_data="menu")],
    ]
    await query.edit_message_text(
        f"⚙️ <b>AUTO-TRADE</b> | {status}\n\n"
        f"Trade size: <code>{cfg.trade_sol} SOL</code>\n"
        f"Slippage: <code>{cfg.slippage_bps/100:.1f}%</code>\n"
        f"Min spike: <code>{cfg.min_spike_pct:.0f}%</code>\n"
        f"Min safety score: <code>{cfg.min_safety_score}</code>\n"
        f"Take profit: <code>+{cfg.take_profit_pct:.0f}%</code>\n"
        f"Stop loss: <code>{cfg.stop_loss_pct:.0f}%</code>\n"
        f"Daily limit: <code>{cfg.max_trades_day} trades</code>",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(kb),
    )


async def cb_at_toggle(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    async with SessionLocal() as db:
        result = await db.execute(select(AutoTradeConfig).where(AutoTradeConfig.telegram_id == user.id))
        cfg = result.scalar_one_or_none()
        if cfg:
            cfg.enabled = not cfg.enabled
            await db.commit()
    await cb_at_menu(update, ctx)


async def cb_my_trades(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user

    async with SessionLocal() as db:
        from models.db import Trade
        result = await db.execute(
            select(Trade)
            .where(Trade.telegram_id == user.id)
            .order_by(Trade.created_at.desc())
            .limit(10)
        )
        trades = result.scalars().all()

    if not trades:
        text = "📊 <b>MY TRADES</b>\n\nNo trades yet."
    else:
        lines = ["📊 <b>MY TRADES</b> (last 10)\n"]
        for t in trades:
            icon = "🟢" if t.action == "buy" else "🔴"
            pnl = f" | PnL: {t.pnl_pct:+.0f}%" if t.pnl_pct else ""
            lines.append(
                f"{icon} <code>{t.symbol}</code> {t.action.upper()} {t.sol_amount:.3f}SOL"
                f"{pnl}\n<code>{t.created_at.strftime('%m/%d %H:%M')}</code>"
            )
        text = "\n".join(lines)

    kb = [[InlineKeyboardButton("◀️ Back", callback_data="menu")]]
    await query.edit_message_text(text, parse_mode=ParseMode.HTML,
                                   reply_markup=InlineKeyboardMarkup(kb))


# ── Alert settings ────────────────────────────────────────────

async def cb_alert_settings(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user

    async with SessionLocal() as db:
        from models.db import User as DBUser
        result = await db.execute(select(DBUser).where(DBUser.telegram_id == user.id))
        u = result.scalar_one_or_none()

    if not u:
        return

    status = "✅ ON" if u.alerts_enabled else "❌ OFF"
    kb = [
        [InlineKeyboardButton(f"🔔 Alerts: {status}", callback_data="alert_toggle")],
        [InlineKeyboardButton("◀️ Back", callback_data="menu")],
    ]
    await query.edit_message_text(
        f"🔔 <b>ALERT SETTINGS</b>\n\n"
        f"Alerts: {status}\n"
        f"Min spike: <code>{u.min_spike_pct:.0f}%</code>\n"
        f"Min safety: <code>{u.min_safety_score}</code>",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(kb),
    )


async def cb_alert_toggle(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    async with SessionLocal() as db:
        from models.db import User as DBUser
        result = await db.execute(select(DBUser).where(DBUser.telegram_id == user.id))
        u = result.scalar_one_or_none()
        if u:
            u.alerts_enabled = not u.alerts_enabled
            await db.commit()
    await cb_alert_settings(update, ctx)


# ── Help ──────────────────────────────────────────────────────

async def cb_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = (
        "ℹ️ <b>HELP</b>\n\n"
        "<code>/start</code> — Start the bot\n"
        "<code>/menu</code> — Main menu\n"
        "<code>/test</code> — Test if bot is working\n"
        "<code>/verify &lt;TX&gt;</code> — Verify Pro payment\n\n"
        "<b>Free:</b> Spike alerts when tokens pump 150%+\n\n"
        "<b>Pro:</b> Full AI analysis with each alert + "
        "auto-trade using your own wallet.\n\n"
        "Your wallet is non-custodial — only you hold the keys."
    )
    kb = [[InlineKeyboardButton("◀️ Back", callback_data="menu")]]
    await query.edit_message_text(text, parse_mode=ParseMode.HTML,
                                   reply_markup=InlineKeyboardMarkup(kb))


# ── Menu router ───────────────────────────────────────────────

async def _menu_msg(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = update.effective_user
    async with SessionLocal() as db:
        pro = await is_pro(db, user.id)
    tier_badge = "💎 PRO" if pro else "🆓 FREE"
    kb = [
        [
            InlineKeyboardButton("💎 Subscribe Pro", callback_data="sub_info"),
            InlineKeyboardButton("👜 My Wallet", callback_data="wallet_info"),
        ],
        [
            InlineKeyboardButton("⚙️ Auto-Trade", callback_data="at_menu"),
            InlineKeyboardButton("📊 My Trades", callback_data="my_trades"),
        ],
        [
            InlineKeyboardButton("🔔 Alert Settings", callback_data="alert_settings"),
            InlineKeyboardButton("ℹ️ Help", callback_data="help"),
        ],
    ]
    await query.edit_message_text(
        f"<b>NO-BRAIN-TRADE</b> | {tier_badge}",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(kb),
    )


# ── Alert broadcaster (called by main pipeline) ───────────────

async def broadcast_spike_alert(
    app: Application,
    token: TokenData,
    spike_pct: float,
    pro_users: list[int],
    free_users: list[int],
):
    """
    Send free alert to all free users.
    Send full AI alert to all pro users.
    """
    # Free alert
    free_text = (
        f"⚡ <b>SPIKE ALERT</b>\n\n"
        f"<b>{token.name}</b> (<code>{token.symbol}</code>)\n"
        f"<code>{token.mint}</code>\n\n"
        f"📊 Spike: <b>+{spike_pct:.0f}%</b>\n"
        f"💧 Liq: {token.liquidity_sol:.1f} SOL\n\n"
        f"<a href='https://dexscreener.com/solana/{token.mint}'>DexScreener</a> | "
        f"<a href='https://pump.fun/{token.mint}'>Pump.fun</a>\n\n"
        f"<i>💎 Upgrade to Pro for full AI analysis</i>"
    )

    # Pro alert (full DeepNet data)
    risk_emoji = "✅" if token.safety_score >= 70 else "⚠️" if token.safety_score >= 40 else "🚩"
    tags_str = " ".join(f"<code>{t}</code>" for t in token.tags[:4]) if token.tags else "—"
    pro_text = (
        f"⚡ <b>SPIKE ALERT</b> | 🧠 DeepNet\n\n"
        f"<b>{token.name}</b> (<code>{token.symbol}</code>)\n"
        f"<code>{token.mint}</code>\n\n"
        f"📊 Spike: <b>+{spike_pct:.0f}%</b>\n"
        f"💧 Liq: {token.liquidity_sol:.1f} SOL\n"
        f"📦 Vol 5m: ${format_number(token.volume_5m_usd)}\n"
        f"👥 Holders: {token.holder_count}\n"
        f"{risk_emoji} Safety: {token.safety_score}/100\n"
        f"🔍 Bundles: {token.bundle_count}\n"
        f"🐋 Smart Money: {'Yes' if token.smart_money_flag else 'No'}\n"
        f"🔑 Auth Revoked: {'Yes' if token.mint_authority_revoked else 'No'}\n"
        f"🏷 Tags: {tags_str}\n\n"
        f"<a href='https://dexscreener.com/solana/{token.mint}'>DexScreener</a> | "
        f"<a href='https://pump.fun/{token.mint}'>Pump.fun</a>"
    )

    # Send to free users
    for uid in free_users:
        try:
            await app.bot.send_message(
                uid, free_text, parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
        except Exception:
            pass

    # Send to pro users
    for uid in pro_users:
        try:
            await app.bot.send_message(
                uid, pro_text, parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
        except Exception:
            pass


# ── Register all handlers ─────────────────────────────────────

def register(app: Application):
    """Register all bot handlers"""
    # Command handlers
    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("menu",   cmd_menu))
    app.add_handler(CommandHandler("verify", cmd_verify))
    app.add_handler(CommandHandler("test",   cmd_test))
    
    # Callback query handlers
    app.add_handler(CallbackQueryHandler(cb_sub_info,       pattern="^sub_info$"))
    app.add_handler(CallbackQueryHandler(cb_sub_pay,        pattern="^sub_pay$"))
    app.add_handler(CallbackQueryHandler(cb_wallet_info,    pattern="^wallet_info$"))
    app.add_handler(CallbackQueryHandler(cb_wallet_export,  pattern="^wallet_export$"))
    app.add_handler(CallbackQueryHandler(cb_at_menu,        pattern="^at_menu$"))
    app.add_handler(CallbackQueryHandler(cb_at_toggle,      pattern="^at_toggle$"))
    app.add_handler(CallbackQueryHandler(cb_my_trades,      pattern="^my_trades$"))
    app.add_handler(CallbackQueryHandler(cb_alert_settings, pattern="^alert_settings$"))
    app.add_handler(CallbackQueryHandler(cb_alert_toggle,   pattern="^alert_toggle$"))
    app.add_handler(CallbackQueryHandler(cb_help,           pattern="^help$"))
    app.add_handler(CallbackQueryHandler(_menu_msg,         pattern="^menu$"))
    
    # Error handler
    app.add_error_handler(error_handler)
    
    logger.info("✓ Bot handlers registered")
