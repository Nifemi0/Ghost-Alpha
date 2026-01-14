import requests
import json

def find_event_detailed():
    url = "https://gamma-api.polymarket.com/events?active=true&closed=false&limit=1000"
    resp = requests.get(url).json()
    for e in resp:
        if 'Bitcoin' in e.get('title', ''):
            print(f"EVENT: {e.get('title')} | ID: {e.get('id')}")
            for m in e.get('markets', []):
                print(f"  MARKET: {m.get('question')} | CLOB IDs: {m.get('clobTokenIds')}")
            print("-" * 30)

if __name__ == "__main__":
    find_event_detailed()
