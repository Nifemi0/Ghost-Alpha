
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import config.constants as C
from ui.security import admin_only, is_admin
import logging
from datetime import datetime

audit_logger = logging.getLogger("AdminAudit")

@admin_only
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    engine = context.bot_data.get('engine')
    status_emoji = "🛑 PAUSED" if engine.paused else "🟢 RUNNING"
    msg = (
        "🛠️ *GHOST CONTROL CENTER*\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"System Status: {status_emoji}\n"
        f"Active Token: `{engine.token_id[:10]}...`\n"
        f"Current Price: `${engine.poly_price:.3f}`\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "Select an action below:"
    )
    keyboard = [
        [InlineKeyboardButton("▶️ Resume", callback_data="admin_resume"), InlineKeyboardButton("⏸️ Pause", callback_data="admin_pause")],
        [InlineKeyboardButton("🔬 Alpha Score", callback_data="admin_alpha"), InlineKeyboardButton("📜 View Logs", callback_data="admin_logs_0")],
        [InlineKeyboardButton("🎯 Market Info", callback_data="admin_market_info")]
    ]
    markup = InlineKeyboardMarkup(keyboard)
    if update.callback_query:
        try: await update.callback_query.edit_message_text(msg, parse_mode='Markdown', reply_markup=markup)
        except: await update.effective_message.reply_text(msg, parse_mode='Markdown', reply_markup=markup)
    else:
        await update.effective_message.reply_text(msg, parse_mode='Markdown', reply_markup=markup)

async def admin_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != C.ADMIN_ID: return
    engine = context.bot_data.get('engine')
    if not context.args or context.args[0] != C.ADMIN_PASSWORD:
        audit_logger.warning(f"FAILED LOGIN|{update.effective_user.id}")
        await update.message.reply_text("❌ *Incorrect Password*")
        return
    await engine.executor_db.update_admin_session()
    await update.message.reply_text("🔓 *Admin Session Unlocked (48 Hours)*")

@admin_only
async def admin_set_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    engine = context.bot_data.get('engine')
    if not context.args:
        await update.message.reply_text("Usage: `/admin_set_token <token_id>`")
        return
    new_token = context.args[0]
    if "--confirm" not in context.args:
        await engine.poly_monitor.init_session()
        url = f"https://clob.polymarket.com/markets/{new_token}"
        try:
            async with engine.poly_monitor.session.get(url) as resp:
                data = await resp.json()
                q = data.get("question", "Unknown Market")
                await update.message.reply_text(f"⚠️ *CONFIRM MARKET CHANGE*\n\nNew: `{q}`\nRun `/admin_set_token {new_token} --confirm` to apply.", parse_mode='Markdown')
                return
        except: return
    
    engine.token_id = new_token
    engine.save_config()
    audit_logger.info(f"ADMIN_SET_TOKEN|{update.effective_user.id}|{new_token}")
    await update.message.reply_text(f"🎯 Market Token Updated: `{new_token}`")

@admin_only
async def logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    engine = context.bot_data.get('engine')
    page = int(context.args[0]) if context.args else 0
    offset = page * 10
    trades = engine.executor_db.get_decrypted_trades(update.effective_user.id, limit=10, offset=offset)
    if not trades:
        await update.message.reply_text("📜 No more trades found.")
        return
    log_text = f"📜 *Recent Trades (Page {page})*\n"
    for t in trades:
        emoji = "💰" if t['profit'] > 0 else "📉"
        log_text += f"{emoji} {t['time'][11:16]} | {t['move']:.4f} | `${t['profit']:.2f}` | {t['reason']}\n"
    await update.message.reply_text(log_text, parse_mode='Markdown')

@admin_only
async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    engine = context.bot_data.get('engine')
    if not context.args: return
    content = " ".join(context.args)
    active_users = engine.executor_db.get_active_users()
    count = 0
    for uid, _ in active_users:
        try:
            await context.bot.send_message(chat_id=uid, text=f"📡 *GHOST UPDATE*\n━━━━━━━━━━━━━━━━━━━━\n\n{content}", parse_mode='Markdown')
            count += 1
        except: pass
    await update.message.reply_text(f"✅ Broadcast sent to {count} users.")

@admin_only
async def admin_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    engine = context.bot_data.get('engine')
    engine.paused = True
    await update.message.reply_text("⏸️ *BOT PAUSED* (Master loop suspended)")

@admin_only
async def admin_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    engine = context.bot_data.get('engine')
    engine.paused = False
    await update.message.reply_text("▶️ *BOT RESUMED*")

@admin_only
async def admin_alpha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    engine = context.bot_data.get('engine')
    exec_data = engine.executor_db.get_user(C.ADMIN_ID)
    obs_data = engine.observer_db.get_user(C.ADMIN_ID)
    
    e_prof = exec_data[0] - C.INITIAL_BALANCE if exec_data else 0
    o_prof = obs_data[0] - C.INITIAL_BALANCE if obs_data else 0
    
    alpha = (e_prof / o_prof * 100) if o_prof > 0 else 0
    msg = (
        "📊 *ALPHA EFFICIENCY*\n\n"
        f"Executor Profit: `${e_prof:.2f}`\n"
        f"Observer Gold Standard: `${o_prof:.2f}`\n\n"
        f"Efficiency Score: `{alpha:.1f}%`"
    )
    await update.message.reply_text(msg, parse_mode='Markdown')

@admin_only
async def admin_compare(update: Update, context: ContextTypes.DEFAULT_TYPE):
    engine = context.bot_data.get('engine')
    exec_data = engine.executor_db.get_user(C.ADMIN_ID)
    obs_data = engine.observer_db.get_user(C.ADMIN_ID)
    
    exec_bal = exec_data[0] if exec_data else C.INITIAL_BALANCE
    obs_bal = obs_data[0] if obs_data else C.INITIAL_BALANCE
    
    msg = (
        "🔬 *ADMIN: OBSERVER VS EXECUTOR*\n\n"
        f"**EXECUTOR**: `${exec_bal:.2f}`\n"
        f"**OBSERVER**: `${obs_bal:.2f}`\n\n"
        f"**Efficiency**: `{(exec_bal/obs_bal*100):.1f}%`"
    )
    await update.message.reply_text(msg, parse_mode='Markdown')

async def token_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    engine = context.bot_data.get('engine')
    msg = (
        f"🎯 *CURRENT MARKET TARGET*\n\n"
        f"Question: `{engine.poly_question}`\n"
        f"Token ID: `{engine.token_id}`\n"
        f"Current Price: `${engine.poly_price:.3f}`"
    )
    await update.message.reply_text(msg, parse_mode='Markdown')
