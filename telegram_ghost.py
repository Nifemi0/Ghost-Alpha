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

# --- CONFIGURATION ---
DB_PATH = "ghost_multi_user.db"
POLY_TOKEN_ID = "115563279943088574368475763566308524191598627607680105838058505260056381768939"
INITIAL_BALANCE = 1000.00
BUY_PERCENT = 0.50 
VOLATILITY_THRESHOLD = 0.0001
MAX_DRAWDOWN_PCT = 0.05
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ENCRYPTION_KEY = os.getenv("GHOST_ENCRYPTION_KEY")

class GhostDB:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.cipher = Fernet(ENCRYPTION_KEY.encode()) if ENCRYPTION_KEY else None
        self.init_db()

    def init_db(self):
        # User Table
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
        # Encrypted Trades Table
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                binance_move REAL,
                entry_price REAL,
                exit_price REAL,
                encrypted_profit BLOB,
                encrypted_balance BLOB,
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

    def log_trade(self, user_id, move, entry, exit, profit, balance):
        enc_profit = self.encrypt(profit)
        enc_balance = self.encrypt(balance)
        self.cursor.execute("""
            INSERT INTO trades (user_id, binance_move, entry_price, exit_price, encrypted_profit, encrypted_balance, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user_id, move, entry, exit, enc_profit, enc_balance, "SUCCESS"))
        self.conn.commit()

class GhostEngine:
    def __init__(self, application):
        self.app = application
        self.db = GhostDB()
        self.prices = {"binance": 0.0, "coinbase": 0.0}
        self.poly_price = 0.0
        self.binance_history = []
        self.coinbase_history = []
        
        # Track In-Position users locally for the 3-5s hold
        self.active_positions = {} # {user_id: {entry, shares, move}}

    async def broadcast_alert(self, user_id, text):
        try: await self.app.bot.send_message(chat_id=user_id, text=text, parse_mode='Markdown')
        except Exception as e: print(f"Broadcast error to {user_id}: {e}")

    async def binance_monitor(self):
        exchange = ccxtpro.binance()
        print("📡 [CORE] Binance WebSocket Connected.", flush=True)
        while True:
            try:
                ticker = await exchange.watch_ticker('BTC/USDT')
                self.prices["binance"] = float(ticker['last'])
                self.binance_history.append((time.time(), self.prices["binance"]))
                if len(self.binance_history) > 50: self.binance_history.pop(0)
            except Exception as e: 
                print(f"❌ [CORE] Binance Error: {e}", flush=True)
                await asyncio.sleep(1)

    async def polymarket_monitor(self):
        url = f"https://clob.polymarket.com/price?token_id={POLY_TOKEN_ID}&side=buy"
        print("🛡️ [CORE] Polymarket Monitor Active.", flush=True)
        while True:
            try:
                resp = requests.get(url, timeout=5).json()
                self.poly_price = float(resp.get('price', 0.0))
                await asyncio.sleep(0.5)
            except Exception as e: 
                print(f"❌ [CORE] Polymarket Error: {e}", flush=True)
                await asyncio.sleep(1)

    async def run_master_loop(self):
        print("🏹 [CORE] Sniper Logic Engaged (Binance Focus). Waiting for Signal...", flush=True)
        check_counter = 0
        while True:
            check_counter += 1
            if check_counter % 300 == 0: 
                print(f"💓 [HEARTBEAT] Scanning... Binance: ${self.prices['binance']:.2f} | Poly: ${self.poly_price:.3f}", flush=True)
            
            if len(self.binance_history) > 10:
                now = time.time()
                b_past = [p for t, p in self.binance_history if now - t > 1.5]
                
                if b_past:
                    b_move = (self.prices["binance"] - b_past[-1]) / b_past[-1]
                    
                    if b_move > VOLATILITY_THRESHOLD:
                        # 🏹 TRIGGER: Signal detected from Binance Lead
                        self.db.cursor.execute("SELECT user_id, balance, peak_balance FROM users WHERE is_active = 1")
                        users = self.db.cursor.fetchall()
                        
                        for uid, bal, peak in users:
                            if uid not in self.active_positions:
                                asyncio.create_task(self.execute_user_snipe(uid, bal, peak, b_move))
            
            await asyncio.sleep(0.1)

    async def execute_user_snipe(self, user_id, balance, peak, move):
        invest = balance * BUY_PERCENT
        # Record the EXACT price at the moment of the 'Snipe'
        entry = self.poly_price
        if entry <= 0: return
        
        shares = invest / entry
        new_bal = balance - invest
        
        # We store the state, but we wait to see what REALLY happens on-chain
        pos_id = f"{user_id}_{int(time.time() * 1000)}"  # Use milliseconds for uniqueness
        self.active_positions[pos_id] = {"user_id": user_id, "entry": entry, "shares": shares, "move": move, "bal": new_bal, "peak": peak}
        
        await self.broadcast_alert(user_id, f"🏹 *REAL-TIME SNIPE INITIATED*\n\nGap detected on Binance: `{move*100:.4f}%`\nPolymarket Entry: `${entry:.3f}`\n\n_Observing market reaction for 5 seconds..._")
        
        # WAITING FOR GROUND TRUTH (The 'Lag' Window)
        await asyncio.sleep(5)
        
        # CAPTURE THE REAL EXIT (What is the price NOW after the lag?)
        exit_p = self.poly_price
        
        # Safety check: ensure position still exists
        if pos_id not in self.active_positions:
            print(f"⚠️ Position {pos_id} already closed or missing. Skipping.", flush=True)
            return
        
        pos = self.active_positions.pop(pos_id)
        
        profit = (pos["shares"] * exit_p) - (pos["shares"] * pos["entry"])
        final_bal = pos["bal"] + (pos["shares"] * exit_p)
        new_peak = max(pos["peak"], final_bal)
        
        # Save REAL data to DB
        self.db.update_user_balance(user_id, final_bal, new_peak)
        self.db.log_trade(user_id, move, pos["entry"], exit_p, profit, final_bal)
        
        if profit > 0:
            emoji = "💰"
            status = "PROFIT"
        elif profit < 0:
            emoji = "📉"
            status = "LOSS"
        else:
            emoji = "⚖️"
            status = "NO CHANGE (Break Even)"

        await self.broadcast_alert(user_id, f"{emoji} *TRADE SETTLED (REAL DATA)*\n\nStatus: `{status}`\nReal Exit: `${exit_p:.3f}`\nNet Profit: `${profit:.4f}`\nWallet: `${final_bal:.2f}`")

# --- UI HANDLERS ---
engine = None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    engine.db.create_user(user.id, user.username or user.first_name)
    msg = (
        f"🏁 *Welcome to Latency Ghost Beta, {user.first_name}!* 🏁\n\n"
        "I have credited your account with **$1,000.00** in virtual test funds.\n\n"
        "I am currently watching Binance + Coinbase + Polymarket. The second a gap opens, I will snipe a virtual position for you."
    )
    await update.message.reply_text(msg, parse_mode='Markdown')

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = engine.db.get_user(user_id)
    if not data:
        await update.message.reply_text("Please run /start first.")
        return
    
    bal, peak, active = data
    msg = (
        "📈 *BETA TESTER STATS*\n\n"
        f"Wallet: `${bal:.2f}`\n"
        f"Peak:   `${peak:.2f}`\n"
        f"Status: `{'🛡️ GUARDED' if active else '🔴 KILLED'}`\n"
        f"Secure ID: `{hashlib.sha256(str(user_id).encode()).hexdigest()[:8]}`"
    )
    await update.message.reply_text(msg, parse_mode='Markdown')

async def post_init(application):
    global engine
    engine = GhostEngine(application)
    await application.bot.set_my_commands([
        BotCommand("start", "Join the Beta"),
        BotCommand("stats", "Check PnL & Balance")
    ])
    asyncio.create_task(engine.binance_monitor())
    asyncio.create_task(engine.polymarket_monitor())
    asyncio.create_task(engine.run_master_loop())

if __name__ == '__main__':
    application = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stats", stats))
    print("🤖 Multi-User Ghost Engine active.")
    application.run_polling()
