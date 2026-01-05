"""
Confidence scoring system
Combines multiple signals to rank insider alerts
"""
import sqlite3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.polysights_client import polysights
from data.scrape_oddschad import get_recent_picks

DB_PATH = "poly.db"

def calculate_confidence(insider, model_prediction=None):
    """
    Calculate confidence score (0-100) for an insider alert
    
    Scoring breakdown:
    - Fresh wallet (age < 24h): +30 points
    - Low market count (≤ 2): +20 points
    - High radar score (> 70): +25 points
    - OddsChad agreement: +15 points
    - Model prediction (> 0.7): +10 points
    """
    score = 0
    
    # 1. Wallet age (max 30 points)
    age = insider.get('wallet_age_hours', 999)
    if age < 6:
        score += 30
    elif age < 12:
        score += 25
    elif age < 24:
        score += 20
    
    # 2. Market count (max 20 points)
    market_count = insider.get('market_count', 999)
    if market_count == 0:
        score += 20
    elif market_count == 1:
        score += 15
    elif market_count == 2:
        score += 10
    
    # 3. Radar score (max 25 points)
    wallet = insider.get('wallet')
    if wallet:
        radar = polysights.get_radar_score(wallet)
        if radar is not None:
            if radar > 80:
                score += 25
            elif radar > 70:
                score += 20
            elif radar > 60:
                score += 15
    
    # 4. OddsChad agreement (max 15 points)
    market_id = insider.get('market_id')
    if market_id:
        recent_picks = get_recent_picks(hours=24)
        oddschad_markets = {p['market_id']: p['confidence'] for p in recent_picks}
        
        if market_id in oddschad_markets:
            oddschad_conf = oddschad_markets[market_id]
            if oddschad_conf > 80:
                score += 15
            elif oddschad_conf > 60:
                score += 10
            elif oddschad_conf > 40:
                score += 5
    
    # 5. Model prediction (max 10 points)
    if model_prediction is not None:
        if model_prediction > 0.8:
            score += 10
        elif model_prediction > 0.7:
            score += 7
        elif model_prediction > 0.6:
            score += 5
    
    return min(score, 100)

def enrich_insiders_with_scores():
    """
    Enrich existing insider alerts with confidence scores
    Updates the database with calculated scores
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Add confidence_score column if not exists
    try:
        cursor.execute("ALTER TABLE insider_alerts ADD COLUMN confidence_score INTEGER")
        conn.commit()
    except:
        pass  # Column already exists
    
    # Get insiders without scores
    cursor.execute("""
        SELECT id, wallet, wallet_age_hours, market_count, market_id
        FROM insider_alerts
        WHERE confidence_score IS NULL
    """)
    
    rows = cursor.fetchall()
    print(f"Enriching {len(rows)} insider alerts with confidence scores...")
    
    for row in rows:
        insider_id, wallet, age, market_count, market_id = row
        
        insider = {
            'wallet': wallet,
            'wallet_age_hours': age,
            'market_count': market_count,
            'market_id': market_id
        }
        
        score = calculate_confidence(insider)
        
        cursor.execute(
            "UPDATE insider_alerts SET confidence_score = ? WHERE id = ?",
            (score, insider_id)
        )
    
    conn.commit()
    conn.close()
    
    print(f"Enrichment complete!")

if __name__ == "__main__":
    enrich_insiders_with_scores()
