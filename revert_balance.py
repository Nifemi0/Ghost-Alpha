
import sqlite3
import os
import sys
from security.crypto import GhostCrypto
from config.constants import INITIAL_BALANCE

DB_PATH = "ghost_executor.db"
ADMIN_ID = 6898955949

def revert_admin_balance():
    if not os.path.exists(DB_PATH):
        print("❌ Database not found.")
        return

    try:
        crypto = GhostCrypto()
    except Exception as e:
        print(f"❌ Crypto Init Failed: {e}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print(f"🔍 Analyzing Trade History for Admin ({ADMIN_ID})...")

    # Get all encrypted profits
    cursor.execute("SELECT encrypted_profit FROM trades WHERE user_id = ? ORDER BY timestamp ASC", (ADMIN_ID,))
    rows = cursor.fetchall()

    if not rows:
        print("⚠️ No trades found. Resetting to Initial Balance.")
        real_balance = INITIAL_BALANCE
        real_peak = INITIAL_BALANCE
    else:
        current_bal = INITIAL_BALANCE
        peak_bal = INITIAL_BALANCE
        
        for row in rows:
            enc_profit = row[0]
            profit = crypto.decrypt(enc_profit)
            current_bal += profit
            if current_bal > peak_bal:
                peak_bal = current_bal
        
        real_balance = current_bal
        real_peak = peak_bal

    print(f"📉 Calculated Real Balance: ${real_balance:.2f}")
    print(f"📈 Calculated Real Peak:    ${real_peak:.2f}")

    # Update DB
    cursor.execute("""
        UPDATE users 
        SET balance = ?, peak_balance = ? 
        WHERE user_id = ?
    """, (real_balance, real_peak, ADMIN_ID))
    
    conn.commit()
    conn.close()
    print("✅ Balance Reverted Successfully.")

if __name__ == "__main__":
    revert_admin_balance()
