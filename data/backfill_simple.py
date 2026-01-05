"""
Simple backfill using Polymarket's main API
Fetches closed markets and updates clob_token_id
"""
import sqlite3
import requests
import time
import json

DB_PATH = "poly.db"
API_URL = "https://gamma-api.polymarket.com"

def backfill_from_api():
    print("Fetching closed markets from Polymarket API...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    updated = 0
    offset = 0
    limit = 500
    
    while True:
        try:
            print(f"Fetching batch at offset {offset}...")
            resp = requests.get(
                f"{API_URL}/markets", 
                params={"closed": "true", "limit": limit, "offset": offset}, 
                timeout=30
            )
            resp.raise_for_status()
            markets = resp.json()
            
            if not markets or len(markets) == 0:
                print("No more markets to fetch.")
                break
            
            print(f"Processing {len(markets)} markets...")
            
            for market in markets:
                market_id = int(market.get('id', 0))
                if not market_id:
                    continue
                
                # Extract clob_token_id
                try:
                    token_ids_str = market.get('clobTokenIds', '[]')
                    token_ids = json.loads(token_ids_str) if isinstance(token_ids_str, str) else token_ids_str
                    
                    if token_ids and len(token_ids) > 0:
                        clob_token_id = token_ids[0]
                        
                        # Update database
                        cursor.execute(
                            "UPDATE events SET clob_token_id = ? WHERE id = ? AND clob_token_id IS NULL",
                            (clob_token_id, market_id)
                        )
                        
                        if cursor.rowcount > 0:
                            updated += 1
                            
                except Exception as e:
                    continue
            
            # Commit after each batch
            conn.commit()
            
            # Move to next batch
            offset += limit
            
            # Rate limiting
            time.sleep(0.5)
            
        except Exception as e:
            print(f"Error fetching batch: {e}")
            break
    
    print(f"\nBackfill complete! Updated {updated} events.")
    
    # Verify
    cursor.execute("SELECT COUNT(*) FROM events WHERE clob_token_id IS NOT NULL")
    total_with_ids = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM events")
    total_events = cursor.fetchone()[0]
    
    print(f"Total events with clob_token_id: {total_with_ids}/{total_events} ({total_with_ids/total_events*100:.1f}%)")
    
    conn.close()

if __name__ == "__main__":
    backfill_from_api()
