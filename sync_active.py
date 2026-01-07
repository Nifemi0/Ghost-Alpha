import requests
import sqlite3
import pandas as pd
from datetime import datetime

DATABASE_URL = "poly.db"
GAMMA_API_URL = "https://gamma-api.polymarket.com/events"

def sync_active_markets():
    print("Syncing active markets for prediction...")
    
    # 1. Fetch active markets from Gamma
    params = {
        "closed": "false",
        "limit": 50,
        "offset": 0
    }
    try:
        resp = requests.get(GAMMA_API_URL, params=params, timeout=10)
        data = resp.json()
    except Exception as e:
        print(f"Error fetching from Gamma: {e}")
        return

    conn = sqlite3.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    count = 0
    for event in data:
        # Extract fields matching our DB schema
        try:
            m_id = str(event.get('id'))
            
            # Use the first market in the event for generic prediction
            markets = event.get('markets', [])
            if not markets: continue
            market = markets[0]
            
            clob_id = market.get('clobTokenIds', [None])[0]
            question = market.get('question', '')
            
            # Simple assumption: Using first market's data for the event
            # In a real system we'd map every market individually
            
            start_date = event.get('startDate')
            end_date = event.get('endDate')
            
            # Insert or Ignore
            cursor.execute("""
                INSERT OR IGNORE INTO events 
                (id, question, start_time, end_time, initial_price, volume, category, news_summary, clob_token_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                m_id,
                question,
                start_date,
                end_date,
                0.5, # Default price since we don't have history here easily
                event.get('volume', 0),
                event.get('cypto', 'generated'), # Placeholder category
                event.get('description', '') or event.get('title', ''), # Use description as news summary
                clob_id
            ))
            count += 1
        except Exception as e:
            print(f"Skipping event {m_id}: {e}")
            
    conn.commit()
    conn.close()
    print(f"✅ Synced {count} active markets to database.")

if __name__ == "__main__":
    sync_active_markets()
