import requests
import json

def find_btc_price_markets():
    # Polymarket Gamma API search
    url = "https://gamma-api.polymarket.com/markets"
    params = {
        "query": "Bitcoin price",
        "active": "true",
        "closed": "false",
        "limit": 50
    }
    try:
        resp = requests.get(url, params=params).json()
        print(f"Searching for 'Bitcoin price' targets...")
        for market in resp:
            question = market.get('question', '').lower()
            if 'price' in question or '$' in question:
                print(f"Title: {market.get('question')}")
                print(f"ID: {market.get('id')}")
                # Get more data to find the token IDs
                print(f"Condition ID: {market.get('conditionId')}")
                print("-" * 30)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    find_btc_price_markets()
