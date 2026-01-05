import sqlite3
import os

DB_PATH = "poly.db"

def create_insider_tables():
    print(f"Creating insider tables in {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create insider_alerts table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS insider_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wallet TEXT,
            wallet_age_hours REAL,
            market_count INTEGER,
            market_id TEXT,
            trade_size REAL,
            trade_price REAL,
            timestamp INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            confidence_score INTEGER,
            UNIQUE(wallet, market_id, timestamp)
        )
    """)
    print("Created insider_alerts table")
    
    # Create oddschad_picks table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS oddschad_picks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            market_id TEXT,
            confidence REAL,
            source TEXT,
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(market_id, scraped_at)
        )
    """)
    print("Created oddschad_picks table")
    
    # Create walelt_tracker table if needed (not currently used, we use cache)
    
    conn.commit()
    conn.close()
    print("Done.")

if __name__ == "__main__":
    create_insider_tables()
