
from telegram import BotCommand, BotCommandScopeDefault
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler, 
    ContextTypes, filters
)
import config.constants as C
from ui.handlers import start, balance, strategy, history, leaderboard, reset_drawdown
from ui.admin import (
    admin_panel, admin_login, admin_set_token, 
    logs, admin_broadcast, admin_pause, admin_resume,
    admin_alpha, admin_compare, token_info
)
from ui.security import is_admin

async def set_commands(application):
    public_commands = [
        BotCommand("start", "Initialize Virtual Wallet"),
        BotCommand("balance", "View Dashboard & ROI"),
        BotCommand("strategy", "Select Risk Level"),
        BotCommand("history", "View Last 10 Trades"),
        BotCommand("leaderboard", "View Top 5 Hunters")
    ]
    await application.bot.set_my_commands(public_commands, scope=BotCommandScopeDefault())

async def handle_callback_router(update, context):
    query = update.callback_query
    engine = context.bot_data.get('engine')
    await query.answer()

    if query.data.startswith("admin_") and not is_admin(query.from_user.id, engine):
        await query.message.reply_text("⛔ Session Expired. Re-login.")
        return

    if query.data == "admin_pause":
        engine.paused = True
        await admin_panel(update, context)
    elif query.data == "admin_resume":
        engine.paused = False
        await admin_panel(update, context)
    elif query.data == "admin_alpha":
        exec_data = engine.executor_db.get_user(C.ADMIN_ID)
        obs_data = engine.observer_db.get_user(C.ADMIN_ID)
        e_prof = (exec_data[0] - C.INITIAL_BALANCE) if exec_data else 0
        o_prof = (obs_data[0] - C.INITIAL_BALANCE) if obs_data else 0
        alpha = (e_prof / o_prof * 100) if o_prof > 0 else 0
        await query.message.reply_text(f"📊 *Alpha Efficiency*: `{alpha:.1f}%`", parse_mode='Markdown')
    elif query.data == "user_stats_refresh":
        await balance(update, context)
    elif query.data.startswith("strategy_"):
        user_id = query.from_user.id
        mode = query.data.replace("strategy_", "")
        engine.executor_db.cursor.execute("UPDATE users SET strategy_mode = ? WHERE user_id = ?", (mode, user_id))
        engine.executor_db.conn.commit()
        await query.message.edit_text(f"✅ *Strategy Updated to {mode.upper()}*", parse_mode='Markdown')

def setup_bot(token):
    app = ApplicationBuilder().token(token).build()
    
    # Public Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("stats", balance))
    app.add_handler(CommandHandler("wallet", balance))
    app.add_handler(CommandHandler("reset", reset_drawdown))
    app.add_handler(CommandHandler("strategy", strategy))
    app.add_handler(CommandHandler("history", history))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    
    # Admin Commands
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("admin_login", admin_login))
    app.add_handler(CommandHandler("admin_set_token", admin_set_token))
    app.add_handler(CommandHandler("admin_broadcast", admin_broadcast))
    app.add_handler(CommandHandler("admin_pause", admin_pause))
    app.add_handler(CommandHandler("admin_resume", admin_resume))
    app.add_handler(CommandHandler("admin_alpha", admin_alpha))
    app.add_handler(CommandHandler("admin_compare", admin_compare))
    app.add_handler(CommandHandler("token_info", token_info))
    app.add_handler(CommandHandler("logs", logs))
    
    # Dispatcher
    app.add_handler(CallbackQueryHandler(handle_callback_router))
    
    return app
