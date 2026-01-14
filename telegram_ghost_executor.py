import asyncio
import ccxt.pro as ccxtpro
import requests
import time
import os
import random
import sqlite3
import hashlib
from datetime import datetime, timedelta
from telegram import Update, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from dotenv import load_dotenv
from cryptography.fernet import Fernet

load_dotenv()

# --- EXECUTOR CONFIGURATION ---
DB_PATH = "ghost_executor.db"
POLY_TOKEN_ID = "115563279943088574368475763566308524191598627607680105838058505260056381768939"
INITIAL_BALANCE = 1000.00
BUY_PERCENT = 0.25  # Conservative: 25% position size
VOLATILITY_THRESHOLD = 0.0002  # Higher threshold: 0.02% minimum gap
MAX_DRAWDOWN_PCT = 0.05
EXIT_TIMEOUT = 3  # Exit after 3 seconds regardless
TARGET_PROFIT_PCT = 0.005  # Target 0.5% profit
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ENCRYPTION_KEY = os.getenv("GHOST_ENCRYPTION_KEY")

class ExecutorDB:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.cipher = Fernet(ENCRYPTION_KEY.encode()) if ENCRYPTION_KEY else None
        self.init_db()

    def init_db(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                balance REAL,
                peak_balance REAL,
                is_active BOOLEAN DEFAULT 1,
                joined_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                binance_move REAL,
                entry_price REAL,
                exit_price REAL,
                hold_time REAL,
                encrypted_profit BLOB,
                encrypted_balance BLOB,
                exit_reason TEXT,
                status TEXT
            )
        """)
        self.conn.commit()

    def get_user(self, user_id):
        self.cursor.execute("SELECT balance, peak_balance, is_active FROM users WHERE user_id = ?", (user_id,))
        return self.cursor.fetchone()

    def create_user(self, user_id, username):
        self.cursor.execute("INSERT OR IGNORE INTO users (user_id, username, balance, peak_balance) VALUES (?, ?, ?, ?)", 
                           (user_id, username, INITIAL_BALANCE, INITIAL_BALANCE))
        self.conn.commit()

    def update_user_balance(self, user_id, balance, peak):
        self.cursor.execute("UPDATE users SET balance = ?, peak_balance = ? WHERE user_id = ?", (balance, peak, user_id))
        self.conn.commit()

    def encrypt(self, data):
        if not self.cipher: return str(data).encode()
        return self.cipher.encrypt(str(data).encode())

    def log_trade(self, user_id, move, entry, exit, hold_time, profit, balance, exit_reason):
        enc_profit = self.encrypt(profit)
        enc_balance = self.encrypt(balance)
        self.cursor.execute("""
            INSERT INTO trades (user_id, binance_move, entry_price, exit_price, hold_time, encrypted_profit, encrypted_balance, exit_reason, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, move, entry, exit, hold_time, enc_profit, enc_balance, exit_reason, "EXECUTED"))
        self.conn.commit()

class ExecutorEngine:
    def __init__(self, application):
        self.app = application
        self.db = ExecutorDB()
        self.prices = {"binance": 0.0}
        self.poly_price = 0.0
        self.binance_history = []
        self.active_positions = {}

    async def broadcast_alert(self, user_id, text):
        try: await self.app.bot.send_message(chat_id=user_id, text=text, parse_mode='Markdown')
        except Exception as e: print(f"Broadcast error to {user_id}: {e}", flush=True)

    async def binance_monitor(self):
        exchange = ccxtpro.binance()
        print("⚡ [EXECUTOR] Binance WebSocket Connected.", flush=True)
        while True:
            try:
                ticker = await exchange.watch_ticker('BTC/USDT')
                self.prices["binance"] = float(ticker['last'])
                self.binance_history.append((time.time(), self.prices["binance"]))
                if len(self.binance_history) > 50: self.binance_history.pop(0)
            except Exception as e: 
                print(f"❌ [EXECUTOR] Binance Error: {e}", flush=True)
                await asyncio.sleep(1)

    async def polymarket_monitor(self):
        url = f"https://clob.polymarket.com/price?token_id={POLY_TOKEN_ID}&side=buy"
        print("⚡ [EXECUTOR] Polymarket Monitor Active.", flush=True)
        while True:
            try:
                resp = requests.get(url, timeout=5).json()
                self.poly_price = float(resp.get('price', 0.0))
                await asyncio.sleep(0.5)
            except Exception as e: 
                print(f"❌ [EXECUTOR] Polymarket Error: {e}", flush=True)
                await asyncio.sleep(1)

    async def run_master_loop(self):
        print("⚡ [EXECUTOR] Instant Execution Mode Active. Hunting Alpha...", flush=True)
        check_counter = 0
        while True:
            check_counter += 1
            if check_counter % 300 == 0: 
                print(f"⚡ [EXECUTOR HEARTBEAT] Binance: ${self.prices['binance']:.2f} | Poly: ${self.poly_price:.3f}", flush=True)
            
            if len(self.binance_history) > 10:
                now = time.time()
                b_past = [p for t, p in self.binance_history if now - t > 1.5]
                
                if b_past:
                    b_move = (self.prices["binance"] - b_past[-1]) / b_past[-1]
                    
                    if b_move > VOLATILITY_THRESHOLD:
                        self.db.cursor.execute("SELECT user_id, balance, peak_balance FROM users WHERE is_active = 1")
                        users = self.db.cursor.fetchall()
                        
                        for uid, bal, peak in users:
                            if uid not in self.active_positions:
                                asyncio.create_task(self.execute_instant_trade(uid, bal, peak, b_move))
            
            await asyncio.sleep(0.1)

    async def execute_instant_trade(self, user_id, balance, peak, move):
        """INSTANT EXECUTION: Enter immediately, exit based on conditions"""
        invest = balance * BUY_PERCENT
        entry = self.poly_price
        entry_time = time.time()
        
        if entry <= 0: return
        
        shares = invest / entry
        new_bal = balance - invest
        self.active_positions[user_id] = True
        
        await self.broadcast_alert(user_id, f"⚡ *EXECUTOR: INSTANT ENTRY*\n\nBinance Gap: `{move*100:.4f}%`\nEntry: `${entry:.3f}`\nPosition: `{BUY_PERCENT*100:.0f}%` of bankroll\n\n_Monitoring for exit..._")
        
        # DYNAMIC EXIT LOGIC
        exit_reason = "TIMEOUT"
        exit_price = entry
        
        for i in range(30):  # Check every 100ms for 3 seconds
            await asyncio.sleep(0.1)
            current_price = self.poly_price
            hold_time = time.time() - entry_time
            
            # Exit condition 1: Target profit hit
            profit_pct = (current_price - entry) / entry
            if profit_pct >= TARGET_PROFIT_PCT:
                exit_price = current_price
                exit_reason = "TARGET_PROFIT"
                break
            
            # Exit condition 2: Timeout (3 seconds)
            if hold_time >= EXIT_TIMEOUT:
                exit_price = current_price
                exit_reason = "TIMEOUT"
                break
            
            # Exit condition 3: Price moving against us
            if profit_pct < -0.002:  # -0.2% stop loss
                exit_price = current_price
                exit_reason = "STOP_LOSS"
                break
        
        # SETTLE TRADE
        hold_time = time.time() - entry_time
        profit = (shares * exit_price) - (shares * entry)
        final_bal = new_bal + (shares * exit_price)
        new_peak = max(peak, final_bal)
        
        self.db.update_user_balance(user_id, final_bal, new_peak)
        self.db.log_trade(user_id, move, entry, exit_price, hold_time, profit, final_bal, exit_reason)
        
        del self.active_positions[user_id]
        
        if profit > 0:
            emoji = "💰"
            status = "PROFIT"
        elif profit < 0:
            emoji = "📉"
            status = "LOSS"
        else:
            emoji = "⚖️"
            status = "BREAK EVEN"

        await self.broadcast_alert(user_id, 
            f"{emoji} *EXECUTOR: TRADE CLOSED*\n\n"
            f"Status: `{status}`\n"
            f"Exit Reason: `{exit_reason}`\n"
            f"Hold Time: `{hold_time:.2f}s`\n"
            f"Entry: `${entry:.3f}` → Exit: `${exit_price:.3f}`\n"
            f"Net P/L: `${profit:.4f}`\n"
            f"Wallet: `${final_bal:.2f}`"
        )

# --- UI HANDLERS ---
engine = None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    engine.db.create_user(user.id, user.username or user.first_name)
    msg = (
        f"⚡ *EXECUTOR MODE ACTIVATED* ⚡\n\n"
        f"Welcome {user.first_name}!\n\n"
        "You have been credited **$1,000** in virtual funds.\n\n"
        "**EXECUTOR PARAMETERS:**\n"
        f"• Position Size: `{BUY_PERCENT*100:.0f}%`\n"
        f"• Min Gap: `{VOLATILITY_THRESHOLD*100:.3f}%`\n"
        f"• Exit Timeout: `{EXIT_TIMEOUT}s`\n"
        f"• Target Profit: `{TARGET_PROFIT_PCT*100:.2f}%`\n\n"
        "_This bot executes INSTANT trades. Risk is real._"
    )
    await update.message.reply_text(msg, parse_mode='Markdown')

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = engine.db.get_user(user_id)
    if not data:
        await update.message.reply_text("Please run /start first.")
        return
    
    bal, peak, active = data
    
    # Get trade stats
    engine.db.cursor.execute("SELECT COUNT(*) FROM trades WHERE user_id = ?", (user_id,))
    total_trades = engine.db.cursor.fetchone()[0]
    
    msg = (
        "⚡ *EXECUTOR STATS*\n\n"
        f"Wallet: `${bal:.2f}`\n"
        f"Peak: `${peak:.2f}`\n"
        f"Total Trades: `{total_trades}`\n"
        f"Status: `{'⚡ ACTIVE' if active else '🔴 PAUSED'}`\n"
        f"Mode: `INSTANT EXECUTION`"
    )
    await update.message.reply_text(msg, parse_mode='Markdown')

async def post_init(application):
    global engine
    engine = ExecutorEngine(application)
    await application.bot.set_my_commands([
        BotCommand("start", "Join Executor Beta"),
        BotCommand("stats", "Check Performance")
    ])
    asyncio.create_task(engine.binance_monitor())
    asyncio.create_task(engine.polymarket_monitor())
    asyncio.create_task(engine.run_master_loop())

if __name__ == '__main__':
    application = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stats", stats))
    print("⚡ EXECUTOR ENGINE ACTIVE - INSTANT EXECUTION MODE")
    application.run_polling()
