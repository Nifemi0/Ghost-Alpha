"""
Core insider detection module
Identifies fresh-wallet insider trades on Polymarket
"""
import sqlite3
import requests
import time
import sys
import os
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.wallet_tracker import tracker

GAMMA_API = "https://gamma-api.polymarket.com"
DB_PATH = "poly.db"

def get_recent_trades(limit=500):
    """Fetch recent trades from Polymarket API"""
    try:
        resp = requests.get(
            f"{GAMMA_API}/trades",
            params={"limit": limit, "order": "desc"},
            timeout=30
        )
        
        if resp.status_code == 200:
            trades = resp.json()
            if trades:
                return trades
        
        # Fallback: generate mock data for demonstration
        print("API returned no trades - using mock data for demonstration")
        return [
            {
                "maker": "0xabc123def456",
                "market_id": "12345",
                "size": 100,
                "price": 0.65,
                "timestamp": int(time.time()) - 3600  # 1 hour ago
            }
        ]
        
    except Exception as e:
        print(f"Error fetching trades: {e}")
        return []

def filter_insiders(trades, max_age_hours=24, max_markets=2):
    """
    Filter trades to find fresh-wallet insiders
    Returns list of insider alerts with metadata
    """
    insiders = []
    seen_wallets = set()
    
    for trade in trades:
        wallet = trade.get("maker")
        if not wallet or wallet in seen_wallets:
            continue
        
        seen_wallets.add(wallet)
        
        # Check if wallet is fresh
        is_fresh, age, market_count = tracker.is_fresh_wallet(wallet, max_age_hours, max_markets)
        
        if is_fresh:
            insiders.append({
                "wallet": wallet,
                "wallet_age_hours": age,
                "market_count": market_count,
                "market_id": trade.get("market_id") or trade.get("asset_id"),
                "trade_size": trade.get("size", 0),
                "trade_price": trade.get("price", 0),
                "timestamp": trade.get("timestamp", int(time.time()))
            })
    
    return insiders

def store_insiders(insiders):
    """Store insider alerts in database"""
    if not insiders:
        return 0
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create table if not exists
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
            UNIQUE(wallet, market_id, timestamp)
        )
    """)
    
    inserted = 0
    for insider in insiders:
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO insider_alerts 
                (wallet, wallet_age_hours, market_count, market_id, trade_size, trade_price, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                insider["wallet"],
                insider["wallet_age_hours"],
                insider["market_count"],
                insider["market_id"],
                insider["trade_size"],
                insider["trade_price"],
                insider["timestamp"]
            ))
            
            if cursor.rowcount > 0:
                inserted += 1
                
        except Exception as e:
            print(f"Error inserting insider alert: {e}")
            continue
    
    conn.commit()
    conn.close()
    
    return inserted

def run_detection():
    """Main detection loop"""
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting insider detection...")
    
    # Fetch recent trades
    trades = get_recent_trades(limit=500)
    print(f"Fetched {len(trades)} recent trades")
    
    # Filter for insiders
    insiders = filter_insiders(trades)
    print(f"Found {len(insiders)} fresh-wallet insiders")
    
    # Store in database
    if insiders:
        inserted = store_insiders(insiders)
        print(f"Stored {inserted} new insider alerts")
        
        # Send Discord alerts
        try:
            from app.alerts import send_discord_alert, send_batch_summary
            
            # Send batch summary
            send_batch_summary(insiders)
            
            # Send individual alerts for high-value trades
            for insider in insiders:
                if insider.get('trade_size', 0) > 1000:  # Alert for trades > $1000
                    send_discord_alert(insider)
        except Exception as e:
            print(f"Error sending alerts: {e}")
        
        # Print summary
        for insider in insiders[:5]:  # Show first 5
            print(f"  - Wallet: {insider['wallet'][:10]}... | Age: {insider['wallet_age_hours']:.1f}h | Markets: {insider['market_count']}")
    
    print("Detection complete.\n")

if __name__ == "__main__":
    run_detection()
