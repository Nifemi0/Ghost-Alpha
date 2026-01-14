
from telegram import Update
from telegram.ext import ContextTypes
import config.constants as C

def is_admin(user_id, engine):
    # 1. Strict ID Check
    if user_id != C.ADMIN_ID:
        return False
    
    # 2. Session Check
    if C.ADMIN_PASSWORD:
        if not engine: return False
        return engine.executor_db.is_admin_session_valid()
            
    return True

def admin_only(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        from core.engine import DualEngine
        # We assume engine is globally accessible or passed in context
        # In our refactor, engine will be at core.engine.instance or similar
        # For simplicity, we'll access it through context.bot_data if we set it there
        engine = context.bot_data.get('engine')
        
        if not is_admin(update.effective_user.id, engine):
            if update.effective_user.id == C.ADMIN_ID:
                await update.message.reply_text("🔐 *Admin Session Required (48h)*\nUse `/admin_login <password>` to unlock.")
            else:
                await update.message.reply_text("⛔ *Access Denied*")
            return
        return await func(update, context)
    return wrapper
