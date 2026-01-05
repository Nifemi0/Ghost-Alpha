import sqlite3
import time
import datetime
import requests
import json
from fetch_candles import get_price_history

CLOB_API_URL = "https://clob.polymarket.com"
DB_PATH = "poly.db"

def backfill():
    print("Starting Momentum Backfill...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get markets that need backfill
    # We need clob_token_id to fetch prices
    cursor.execute("SELECT id, clob_token_id, start_time, initial_price FROM events WHERE clob_token_id IS NOT NULL AND momentum_24h IS NULL")
    rows = cursor.fetchall()
    
    print(f"Found {len(rows)} markets to process.")
    
    count = 0
    updated = 0
    
    for row in rows:
        event_id, clob_id, start_time_str, initial_price = row
        
        # Parse start_time
        # Format might be '2023-01-01 12:00:00' or similar
        try:
            # Attempt flexible parsing
            if isinstance(start_time_str, str):
                start_time = datetime.datetime.fromisoformat(start_time_str)
            else:
                continue # Skip if cant parse
                
            # Target time: T + 24h
            target_time = start_time + datetime.timedelta(hours=24)
            target_ts = target_time.timestamp()
            
            # Fetch history
            # We use the defaults from fetch_candles which uses interval="max"
            # We ignored startTs/endTs in the final working version of fetch_candles
            data = get_price_history(clob_id, 0, 0) 
            
            if not data or 'history' not in data:
                print(f"No history for {event_id}")
                time.sleep(0.1) # Rate limit protection
                continue
                
            history = data['history'] # List of {'t': timestamp, 'p': price}
            if not history:
                continue
                
            # Find the price at T+24h
            # Since history might be sparse, we find the closest candle *after* T+24h, 
            # or the last candle if the market closed early.
            
            chosen_price = None
            
            # Sort just in case
            history.sort(key=lambda x: x['t'])
            
            for candle in history:
                if candle['t'] >= target_ts:
                    chosen_price = candle['p']
                    break
            
            # If we didn't find a candle after T+24h, checking if the market started > 24h ago
            # If market is old but no candle after 24h, maybe it hasn't traded yet?
            # Or maybe we take the last known price?
            # For now, let's be strict: if we cant find a price near T+24h, skip.
            
            if chosen_price is not None:
                # Calculate Momentum
                # (Price24h - Initial) / Initial
                # Avoid division by zero
                if initial_price and initial_price > 0:
                    momentum = (chosen_price - initial_price) / initial_price
                else:
                    # Fallback if initial is 0 (unlikely for 0.5 start)
                    momentum = 0.0
                
                cursor.execute("UPDATE events SET momentum_24h = ? WHERE id = ?", (momentum, event_id))
                updated += 1
                if updated % 10 == 0:
                    conn.commit()
                    print(f"Updated {updated} markets...")
            
            count += 1
            if count % 50 == 0:
                print(f"Processed {count}/{len(rows)}...")
                
            time.sleep(0.15) # Respect rate limits (approx 6-7 req/sec)
            
        except Exception as e:
            print(f"Error processing {event_id}: {e}")
            continue

    conn.commit()
    conn.close()
    print(f"Backfill Complete. Updated {updated} markets.")

if __name__ == "__main__":
    backfill()
