"""
OddsChad scraper - fetches AI-recommended best bets
Runs daily to identify high-confidence markets
"""
import requests
from bs4 import BeautifulSoup
import sqlite3
from datetime import datetime

DB_PATH = "poly.db"
ODDSCHAD_URL = "https://oddschad.com"

def scrape_oddschad_picks():
    """
    Scrape top picks from OddsChad
    Returns list of market IDs with confidence scores
    """
    try:
        resp = requests.get(ODDSCHAD_URL, timeout=30)
        if resp.status_code != 200:
            print(f"OddsChad returned {resp.status_code}")
            return []
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Parse market picks (structure may vary - adjust selectors as needed)
        picks = []
        
        # Example: look for market cards with data attributes
        for card in soup.select('[data-market-id]'):
            market_id = card.get('data-market-id')
            confidence = card.get('data-confidence', '50')
            
            if market_id:
                picks.append({
                    'market_id': market_id,
                    'confidence': float(confidence),
                    'source': 'oddschad'
                })
        
        return picks
        
    except Exception as e:
        print(f"Error scraping OddsChad: {e}")
        return []

def store_picks(picks):
    """Store OddsChad picks in database"""
    if not picks:
        return 0
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create table if not exists
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
    
    inserted = 0
    for pick in picks:
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO oddschad_picks (market_id, confidence, source)
                VALUES (?, ?, ?)
            """, (pick['market_id'], pick['confidence'], pick['source']))
            
            if cursor.rowcount > 0:
                inserted += 1
        except Exception as e:
            print(f"Error inserting pick: {e}")
            continue
    
    conn.commit()
    conn.close()
    
    return inserted

def get_recent_picks(hours=24):
    """Get OddsChad picks from last N hours"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT market_id, confidence, source, scraped_at
        FROM oddschad_picks
        WHERE scraped_at > datetime('now', ?)
        ORDER BY confidence DESC
    """, (f'-{hours} hours',))
    
    picks = [
        {
            'market_id': row[0],
            'confidence': row[1],
            'source': row[2],
            'scraped_at': row[3]
        }
        for row in cursor.fetchall()
    ]
    
    conn.close()
    return picks

def run_scraper():
    """Main scraper function"""
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Scraping OddsChad...")
    
    picks = scrape_oddschad_picks()
    print(f"Found {len(picks)} picks")
    
    if picks:
        inserted = store_picks(picks)
        print(f"Stored {inserted} new picks")
        
        # Show top 5
        for i, pick in enumerate(picks[:5], 1):
            print(f"  {i}. Market {pick['market_id']} - Confidence: {pick['confidence']:.0f}%")
    
    print("Scraping complete.\n")

if __name__ == "__main__":
    run_scraper()
