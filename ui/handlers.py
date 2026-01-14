
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import config.constants as C
from core.engine import system_status

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    engine = context.bot_data.get('engine')
    user = update.effective_user
    await engine.executor_db.create_user(user.id, user.username or "GhostUser")
    
    # Auto-activate
    engine.executor_db.cursor.execute("UPDATE users SET is_active=1 WHERE user_id=?", (user.id,))
    engine.executor_db.conn.commit()

    msg = (
        f"👻 *LATENCY GHOST TESTNET*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Welcome, `{user.first_name}`!\n\n"
        f"💵 **Balance Credited:** `$1,000.00` (Paper)\n"
        f"📡 **Status:** Connected to Master Signal\n"
        f"🎯 **Strategy:** 5-Second Latency Arb\n\n"
        f"You will now automatically receive trade alerts when the bot detects a gap.\n"
        f"Use /balance to track your PnL."
    )
    await update.effective_message.reply_text(msg, parse_mode='Markdown')

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    engine = context.bot_data.get('engine')
    user_id = update.effective_user.id
    data = engine.executor_db.get_user(user_id)
    if not data:
        await update.effective_message.reply_text("Please run /start first.")
        return
    
    bal, peak, _ = data
    drawdown = (1 - (bal / peak)) * 100 if peak > 0 else 0
    progress = "▓" * int(drawdown / 10) + "░" * (10 - int(drawdown / 10))
    status_label = "🟢 ACTIVE" if system_status == "STABLE" else "⚠️ FROZEN (Noise)"
    
    engine.executor_db.cursor.execute("SELECT COUNT(*) FROM trades WHERE user_id = ?", (user_id,))
    total_trades = engine.executor_db.cursor.fetchone()[0]

    msg = (
        "👻 *ALPHA CAPTURE DASHBOARD*\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"👤 User: `{update.effective_user.first_name}`\n"
        f"🚦 Status: {status_label}\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Wallet: `${bal:.2f}`\n"
        f"📈 Peak:   `${peak:.2f}`\n"
        f"📉 Drawdown: `[{progress}] {drawdown:.1f}%`\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"🏆 ROI: `{((bal/C.INITIAL_BALANCE - 1)*100):.2f}%`\n"
        f"📦 Trades: `{total_trades}`\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 Watching: `{engine.poly_question[:30]}...`"
    )
    
    # Generate Chart
    try:
        from ui.charts import generate_equity_curve
        trades = engine.executor_db.get_decrypted_trades(user_id, limit=50) # Get last 50
        chart_buf = generate_equity_curve(trades, bal, update.effective_user.first_name)
        
        keyboard = [[InlineKeyboardButton("🔄 Refresh Balance", callback_data="user_stats_refresh")]]
        await update.effective_message.reply_photo(
            photo=chart_buf,
            caption=msg,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        # Fallback to text if chart fails
        print(f"Chart Error: {e}")
        await update.effective_message.reply_text(msg, parse_mode='Markdown')

async def strategy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    engine = context.bot_data.get('engine')
    user_id = update.effective_user.id
    data = engine.executor_db.get_user(user_id)
    if not data:
        await update.effective_message.reply_text("Please run /start first.")
        return
    
    engine.executor_db.cursor.execute("SELECT strategy_mode FROM users WHERE user_id = ?", (user_id,))
    res = engine.executor_db.cursor.fetchone()
    current_strategy = res[0] if res else 'balanced'
    
    msg = (
        "🎚️ *SELECT YOUR STRATEGY*\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"Current Mode: `{current_strategy.upper()}`\n\n"
        "🐢 **Conservative** - 15% position, 0.5% profit target\n"
        "⚖️ **Balanced** - 35% position, 0.5% profit target\n"
        "🚀 **Aggressive** - 50% position, 1% profit target\n\n"
        "Choose your risk level below:"
    )
    keyboard = [
        [InlineKeyboardButton("🐢 Conservative", callback_data="strategy_conservative")],
        [InlineKeyboardButton("⚖️ Balanced", callback_data="strategy_balanced")],
        [InlineKeyboardButton("🚀 Aggressive", callback_data="strategy_aggressive")]
    ]
    await update.effective_message.reply_text(msg, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    engine = context.bot_data.get('engine')
    user_id = update.effective_user.id
    trades = engine.executor_db.get_decrypted_trades(user_id, limit=10)
    if not trades:
        await update.effective_message.reply_text("No trade history yet.")
        return
    
    msg = "📜 *TRADE HISTORY (Last 10)*\n━━━━━━━━━━━━━━━━━━━\n\n"
    for i, t in enumerate(trades, 1):
        emoji = "💰" if t['profit'] > 0 else ("📉" if t['profit'] < 0 else "⚖️")
        msg += f"{i}. {emoji} `${t['profit']:+.4f}` | {t['hold']:.1f}s | {t['reason']}\n"
    await update.effective_message.reply_text(msg, parse_mode='Markdown')

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    engine = context.bot_data.get('engine')
    engine.executor_db.cursor.execute("SELECT username, balance FROM users ORDER BY balance DESC LIMIT 5")
    top = engine.executor_db.cursor.fetchall()
    msg = "🏆 *GHOST LEADERBOARD*\n━━━━━━━━━━━━━━━━━━━\n\n"
    for i, (name, bal) in enumerate(top, 1):
        roi = ((bal / C.INITIAL_BALANCE) - 1) * 100
        medal = "🥇🥈🥉🏅" [min(i-1, 3)]
        msg += f"{medal} `{name}`: *{roi:+.2f}%* (${bal:.2f})\n"
    await update.effective_message.reply_text(msg, parse_mode='Markdown')

async def reset_drawdown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    engine = context.bot_data.get('engine')
    user_id = update.effective_user.id
    
    data = engine.executor_db.get_user(user_id)
    if not data: return
    bal, peak, _ = data
    
    # Only allow reset if actually in drawdown > 5%
    if bal >= peak * (1 - C.MAX_DRAWDOWN_PCT):
         await update.effective_message.reply_text("✅ *System Healthy*\nYou are not in drawdown lockout.", parse_mode='Markdown')
         return

    # Reset Peak to Current Balance (Accepting the Loss)
    engine.executor_db.cursor.execute("UPDATE users SET peak_balance = ?, is_active = 1 WHERE user_id = ?", (bal, user_id))
    engine.executor_db.conn.commit()
    
    msg = (
        "🔄 *DRAWDOWN RESET CONFIRMED*\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "You have acknowledged the loss and reset your High Water Mark.\n"
        "Trading has been **reactivated** on your account.\n\n"
        "⚠️ *Trade safely.*"
    )
    await update.effective_message.reply_text(msg, parse_mode='Markdown')
