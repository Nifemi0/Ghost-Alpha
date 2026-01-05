"""
Backfill clob_token_id using Polymarket CLOB API
Fixes the issue where only 12/116k events have token IDs
"""
import sqlite3
import requests
import time
import json

DB_PATH = "poly.db"
CLOB_API = "https://clob.polymarket.com"

def get_market_info(market_slug):
    """Fetch market info from CLOB API using the question slug"""
    try:
        # Try the markets endpoint with search
        resp = requests.get(f"{CLOB_API}/markets", params={"slug": market_slug}, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data and len(data) > 0:
                market = data[0]
                # Extract clobTokenIds
                token_ids_str = market.get('clobTokenIds', '[]')
                if isinstance(token_ids_str, str):
                    token_ids = json.loads(token_ids_str)
                else:
                    token_ids = token_ids_str
                
                if token_ids and len(token_ids) > 0:
                    return token_ids[0]
        return None
    except Exception as e:
        print(f"Error fetching market {market_slug}: {e}")
        return None

def create_slug(question):
    """Create a URL slug from question text (simplified)"""
    import re
    slug = question.lower()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[-\s]+', '-', slug)
    return slug[:100]  # Limit length

def backfill_ids():
    print("Starting clob_token_id backfill...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get events without clob_token_id
    cursor.execute("""
        SELECT id, question 
        FROM events 
        WHERE clob_token_id IS NULL 
        AND outcome IS NOT NULL
        LIMIT 1000
    """)
    
    rows = cursor.fetchall()
    print(f"Found {len(rows)} events to backfill")
    
    updated = 0
    failed = 0
    
    for idx, (event_id, question) in enumerate(rows):
        if idx % 10 == 0:
            print(f"Progress: {idx}/{len(rows)} (Updated: {updated}, Failed: {failed})")
        
        slug = create_slug(question)
        token_id = get_market_info(slug)
        
        if token_id:
            cursor.execute("UPDATE events SET clob_token_id = ? WHERE id = ?", (token_id, event_id))
            updated += 1
        else:
            failed += 1
        
        # Rate limiting
        time.sleep(0.1)
        
        # Commit every 50 updates
        if updated % 50 == 0:
            conn.commit()
    
    conn.commit()
    conn.close()
    
    print(f"\nBackfill complete!")
    print(f"Updated: {updated}")
    print(f"Failed: {failed}")
    print(f"Success rate: {updated/(updated+failed)*100:.1f}%")

if __name__ == "__main__":
    backfill_ids()
