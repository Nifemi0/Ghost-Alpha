import sys
import os
import requests
import datetime
import json
import time
import subprocess
from sqlalchemy.orm import Session
from dotenv import load_dotenv

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data.database import SessionLocal, Event, init_db

# Load environment variables from .env file
load_dotenv()
NEWS_API_KEY = os.getenv("NEWSAPI_KEY")

POLYMARKET_API_URL = "https://gamma-api.polymarket.com/markets"
NEWS_API_URL = "https://newsapi.org/v2/everything"

def fetch_news_summary(question: str) -> str:
    """Fetches a news summary for a given question using NewsAPI."""
    if not NEWS_API_KEY:
        return ""
    
    search_query = question.replace("?", "").replace("Will ", "").replace("be ", "")
    
    params = {
        "q": search_query,
        "apiKey": NEWS_API_KEY,
        "language": "en",
        "pageSize": 3,
        "sortBy": "relevancy"
    }
    try:
        response = requests.get(NEWS_API_URL, params=params)
        if response.status_code == 429:
            return "RATE_LIMIT"
        response.raise_for_status()
        articles = response.json().get('articles', [])
        summary = ". ".join([article['title'] for article in articles])
        return summary
    except:
        return ""

def update_database_with_real_data(total_limit=None, batch_size=100, news_limit=100):
    """
    Fetches markets from Polymarket in batches, gets news summaries, 
    and upserts them into the database. If total_limit is None, runs until no more items.
    """
    print(f"Starting Harvest | Limit: {total_limit if total_limit else 'INFINITE'} | News Limit: {news_limit}")
    
    db: Session = SessionLocal()
    events_added = 0
    news_fetched_count = 0
    offset = 0
    
    while True:
        if total_limit and offset >= total_limit:
            break
            
        try:
            url = f"{POLYMARKET_API_URL}?limit={batch_size}&offset={offset}&order=id&ascending=false&closed=true"
            result = subprocess.check_output(['curl', '-s', url], timeout=30)
            markets = json.loads(result)
        except Exception as e:
            print(f"Error at offset {offset}: {e}")
            break

        if not markets:
            print("Finished: No more markets found.")
            break

        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Batch offset={offset} | Processing {len(markets)} items...")
        batch_new = 0

        for market in markets:
            # Binary Only
            try:
                outcomes = json.loads(market.get('outcomes', '[]'))
                if outcomes != ['Yes', 'No']:
                    continue
            except:
                continue

            existing_event = db.query(Event).filter(Event.id == int(market['id'])).first()
            
            # Outcome Logic
            final_price = None
            outcome = None
            if market.get('closed'):
                try:
                    prices = json.loads(market.get('outcomePrices', '[]'))
                    if len(prices) == 2:
                        yes_price = float(prices[0])
                        no_price = float(prices[1])
                        outcome = yes_price > no_price
                        final_price = yes_price 
                except:
                    pass
            
            # News Logic
            news_summary = ""
            if existing_event and existing_event.news_summary:
                news_summary = existing_event.news_summary
            
            if not news_summary and news_fetched_count < news_limit:
                summary = fetch_news_summary(market['question'])
                if summary == "RATE_LIMIT":
                    # Skip news for rest of this run if rate limited
                    news_fetched_count = news_limit 
                elif summary:
                    news_summary = summary
                    news_fetched_count += 1
                    time.sleep(1)

            # Date Logic
            created_at = market.get('createdAt')
            start_time = datetime.datetime.fromisoformat(created_at.replace('Z', '+00:00')) if created_at else datetime.datetime.now(datetime.timezone.utc)
            end_at = market.get('closedTime') or market.get('endDate')
            end_time = datetime.datetime.fromisoformat(end_at.replace('Z', '+00:00')) if end_at else start_time + datetime.timedelta(days=30)

            # CLOB Token ID Logic
            clob_token_id = None
            try:
                # clobTokenIds is a stringified JSON list: "[\"id1\", \"id2\"]"
                token_ids_str = market.get('clobTokenIds', '[]')
                token_ids = json.loads(token_ids_str)
                if len(token_ids) >= 1:
                    # Index 0 usually corresponds to "Yes" (or the first outcome)
                    clob_token_id = token_ids[0]
            except Exception as e:
                # Keep silent on parse errors to avoid log spam
                pass

            event_data = {
                "id": int(market['id']),
                "question": market['question'],
                "start_time": start_time,
                "end_time": end_time,
                "initial_price": 0.5,
                "final_price": final_price,
                "outcome": outcome,
                "volume": float(market.get('volumeNum', 0)),
                "category": market.get('category', 'Unknown'),
                "news_summary": news_summary,
                "last_trade_price": float(market.get('lastTradePrice', 0)),
                "clob_token_id": clob_token_id
            }

            if existing_event:
                for key, value in event_data.items():
                    setattr(existing_event, key, value)
            else:
                db.add(Event(**event_data))
                batch_new += 1
                events_added += 1
        
        db.commit()
        if batch_new > 0:
            print(f"  Saved {batch_new} new markets. Total new this run: {events_added}")
        offset += batch_size
        time.sleep(0.3)

    db.close()
    print(f"Harvest complete. Added {events_added} new markets.")

if __name__ == "__main__":
    init_db()
    update_database_with_real_data(total_limit=None, batch_size=100, news_limit=1000)
