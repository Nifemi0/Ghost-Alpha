import sqlite3
import json

DB_PATH = "poly.db"

def fix_token_ids():
    print("Starting Token ID Repair...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Select raw market JSON
    # We need to parse 'clobTokenIds' from it
    cursor.execute("SELECT id, market FROM events WHERE clob_token_id IS NULL AND outcome IS NOT NULL")
    rows = cursor.fetchall()
    
    print(f"Scanning {len(rows)} markets for missing Token IDs...")
    
    updates = []
    
    for row in rows:
        event_id, market_json = row
        if not market_json: continue
        
        try:
            market_data = json.loads(market_json)
            # Depending on how it was saved, look for clobTokenIds
            # It might be in the root or nested
            
            # The collector saves the raw market object from API
            token_ids_str = market_data.get('clobTokenIds', '[]')
            token_ids = json.loads(token_ids_str)
            
            if token_ids and len(token_ids) > 0:
                updates.append((token_ids[0], event_id))
                
        except Exception as e:
            continue
            
    print(f"Found {len(updates)} recoverable Token IDs.")
    
    if updates:
        print("Applying updates...")
        cursor.executemany("UPDATE events SET clob_token_id = ? WHERE id = ?", updates)
        conn.commit()
        print("Success! Database repaired.")
    else:
        print("No IDs found to recover. (Are the market JSONs valid?)")

    conn.close()

if __name__ == "__main__":
    fix_token_ids()
