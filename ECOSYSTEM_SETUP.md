# Ecosystem Integration Setup

## OddsChad Scraper

**Purpose**: Fetch AI-recommended best bets daily

**Usage**:
```bash
# Run manually
python3 data/scrape_oddschad.py

# Schedule daily (8am)
crontab -e
# Add: 0 8 * * * cd /root/.gemini/antigravity/scratch/poly && python3 data/scrape_oddschad.py >> /var/log/oddschad.log 2>&1
```

## Polysights Radar Scores

**Purpose**: Get wallet risk/quality metrics

**Setup**:
```bash
# Optional: set API key if Polysights requires authentication
export POLYSIGHTS_API_KEY="your_key_here"
```

**Usage**:
```python
from app.polysights_client import polysights

score = polysights.get_radar_score("0xwallet...")
print(f"Radar score: {score}")  # 0-100, higher = more suspicious
```

## Confidence Scoring

**Purpose**: Rank insider alerts by multiple signals

**Scoring Breakdown** (0-100):
- Fresh wallet (< 24h): +30 points
- Low market count (≤ 2): +20 points  
- High radar score (> 70): +25 points
- OddsChad agreement: +15 points
- Model prediction (> 0.7): +10 points

**Usage**:
```bash
# Enrich existing alerts with scores
python3 app/confidence_scoring.py

# Or integrate into detection loop (automatic)
```

**Alert Thresholds**:
- **High confidence** (> 80): Immediate Discord alert
- **Medium confidence** (60-80): Batch summary only
- **Low confidence** (< 60): Database only, no alert

## Complete Workflow

1. **Daily** (8am): Run OddsChad scraper
2. **Every 5 min**: Run insider detection
3. **Automatic**: Calculate confidence scores
4. **Automatic**: Send Discord alerts for high-confidence signals
