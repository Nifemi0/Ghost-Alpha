import sqlite3
import os
from datetime import datetime, timedelta
# Import ghost crypto if possible, or just look at raw values if stored plainly in some tables
try:
    from security.crypto import GhostCrypto
    HAS_CRYPTO = True
    crypto = GhostCrypto()
except:
    HAS_CRYPTO = False

def run_audit():
    db_path = "ghost_executor.db"
    if not os.path.exists(db_path):
        print(f"Database {db_path} not found.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Define the 48h window
    now = datetime(2026, 1, 16, 18, 35, 23) # Current Server Time
    forty_eight_hours_ago = (now - timedelta(hours=48)).strftime('%Y-%m-%d %H:%M:%S')

    print(f"--- Ghost Alpha Audit: {forty_eight_hours_ago} to {now.strftime('%Y-%m-%d %H:%M:%S')} ---")

    # 1. Total Trade Count & Outcome distribution
    cursor.execute("""
        SELECT exit_reason, COUNT(*) 
        FROM trades 
        WHERE timestamp >= ? 
        GROUP BY exit_reason
    """, (forty_eight_hours_ago,))
    outcomes = cursor.fetchall()
    print("\n[Audit] Trade Outcomes:")
    for reason, count in outcomes:
        print(f" - {reason}: {count}")

    # 2. Analyzing Entry/Exit prices for TIMEOUTS
    # TIMEOUTS usually imply stagnant price or bad execution
    cursor.execute("""
        SELECT entry_price, exit_price, binance_move, timestamp 
        FROM trades 
        WHERE exit_reason = 'TIMEOUT' AND timestamp >= ?
        LIMIT 10
    """, (forty_eight_hours_ago,))
    timeouts = cursor.fetchall()
    print("\n[Audit] Sample TIMEOUTS (Stagnation Check):")
    for entry, exit_p, move, ts in timeouts:
        diff = exit_p - entry
        print(f" - {ts} | Entry: {entry:.4f} | Exit: {exit_p:.4f} | Diff: {diff:.4f} | Move: {move:.5%}")

    # 3. Profit/Loss Analysis
    cursor.execute("""
        SELECT encrypted_profit FROM trades WHERE timestamp >= ?
    """, (forty_eight_hours_ago,))
    profits_enc = cursor.fetchall()
    
    total_raw_pnl = 0.0
    wins = 0
    losses = 0
    
    if HAS_CRYPTO:
        for (enc_p,) in profits_enc:
            try:
                p = crypto.decrypt(enc_p)
                total_raw_pnl += p
                if p > 0: wins += 1
                elif p < 0: losses += 1
            except:
                pass
    
    print("\n[Audit] Performance Summary:")
    print(f" - Total P&L: ${total_raw_pnl:.2f}")
    print(f" - Win/Loss: {wins}/{losses}")

    # 4. Successor Market Spam check
    # Check logs or engine_config if possible, but let's look at trade counts per question
    cursor.execute("""
        SELECT exit_reason, COUNT(*) 
        FROM trades 
        WHERE timestamp >= ?
        GROUP BY exit_reason
    """, (forty_eight_hours_ago,))
    questions = cursor.fetchall()
    print("\n[Audit] Top Exit Reasons:")
    for q, count in questions:
        print(f" - {q}: {count}")

    conn.close()

if __name__ == "__main__":
    run_audit()
