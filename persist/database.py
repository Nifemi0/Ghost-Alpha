
import sqlite3
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
import os
import logging
from config.constants import INITIAL_BALANCE
from security.crypto import GhostCrypto

logger = logging.getLogger("LatencyGhost")

class UnifiedDB:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.crypto = GhostCrypto()
        self.init_db()

    def init_db(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                balance REAL,
                peak_balance REAL,
                is_active BOOLEAN DEFAULT 1,
                strategy_mode TEXT DEFAULT 'balanced',
                joined_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        try:
            self.cursor.execute("ALTER TABLE users ADD COLUMN strategy_mode TEXT DEFAULT 'balanced'")
        except: pass
            
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
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

    def get_active_users(self):
        self.cursor.execute("SELECT user_id, strategy_mode FROM users WHERE is_active = 1")
        return self.cursor.fetchall()

    async def create_user(self, user_id, username):
        await asyncio.get_event_loop().run_in_executor(self.executor, self._create_user_sync, user_id, username)

    def _create_user_sync(self, user_id, username):
        self.cursor.execute("INSERT OR IGNORE INTO users (user_id, username, balance, peak_balance) VALUES (?, ?, ?, ?)", 
                           (user_id, username, INITIAL_BALANCE, INITIAL_BALANCE))
        self.conn.commit()

    async def update_user_balance(self, user_id, balance, peak):
        await asyncio.get_event_loop().run_in_executor(self.executor, self._update_bal_sync, user_id, balance, peak)

    def _update_bal_sync(self, user_id, balance, peak):
        self.cursor.execute("UPDATE users SET balance = ?, peak_balance = ? WHERE user_id = ?", (balance, peak, user_id))
        self.conn.commit()

    def is_admin_session_valid(self):
        try:
            self.cursor.execute("SELECT value FROM settings WHERE key = 'admin_expiry'")
            res = self.cursor.fetchone()
            if not res: return False
            expiry = datetime.fromisoformat(res[0])
            return datetime.utcnow() < expiry
        except: return False

    async def update_admin_session(self):
        await asyncio.get_event_loop().run_in_executor(self.executor, self._update_admin_session_sync)

    def _update_admin_session_sync(self):
        expiry = (datetime.utcnow() + timedelta(hours=48)).isoformat()
        self.cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('admin_expiry', ?)", (expiry,))
        self.conn.commit()

    async def log_trade(self, user_id, move, entry, exit, hold_time, profit, balance, exit_reason, mode="EXECUTOR"):
        await asyncio.get_event_loop().run_in_executor(self.executor, self._log_trade_sync, user_id, move, entry, exit, hold_time, profit, balance, exit_reason, mode)

    def _log_trade_sync(self, user_id, move, entry, exit, hold_time, profit, balance, exit_reason, mode):
        enc_profit = self.crypto.encrypt(profit)
        enc_balance = self.crypto.encrypt(balance)
        self.cursor.execute("""
            INSERT INTO trades (user_id, binance_move, entry_price, exit_price, hold_time, encrypted_profit, encrypted_balance, exit_reason, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, move, entry, exit, hold_time, enc_profit, enc_balance, exit_reason, "EXECUTED"))
        self.conn.commit()
        
        if not os.path.exists("trade_log.txt"):
            open("trade_log.txt", "a").close()
            os.chmod("trade_log.txt", 0o600)
        
        timestamp = datetime.utcnow().isoformat()
        logger.info(f"{timestamp}|{mode}|{user_id}|{move:.6f}|{entry:.4f}|{exit:.4f}|{hold_time:.2f}s|{profit:.4f}|{balance:.2f}|{exit_reason}")

    def get_decrypted_trades(self, user_id, limit=20, offset=0):
        self.cursor.execute("""
            SELECT timestamp, binance_move, entry_price, exit_price, hold_time, encrypted_profit, exit_reason 
            FROM trades WHERE user_id = ? ORDER BY timestamp DESC LIMIT ? OFFSET ?
        """, (user_id, limit, offset))
        raw = self.cursor.fetchall()
        trades = []
        for r in raw:
            trades.append({
                "time": r[0], "move": r[1], "entry": r[2], "exit": r[3],
                "hold": r[4], "profit": self.crypto.decrypt(r[5]), "reason": r[6]
            })
        return trades
