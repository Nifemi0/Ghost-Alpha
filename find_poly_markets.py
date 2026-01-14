import requests
import json

def find_btc_markets():
    url = "https://gamma-api.polymarket.com/markets"
    params = {
        "query": "Bitcoin",
        "active": "true",
        "closed": "false"
    }
    try:
        resp = requests.get(url, params=params).json()
        print(f"Found {len(resp)} Bitcoin markets.\n")
        for market in resp[:5]:
            title = market.get('question', 'Unknown')
            market_id = market.get('id', 'N/A')
            # Extract the 'yes' price if available
            tokens = market.get('outcomeAssets', [])
            print(f"Title: {title}")
            print(f"ID: {market_id}")
            print(f"Tokens: {tokens}")
            print("-" * 30)
    except Exception as e:
        print(f"Error fetching markets: {e}")

if __name__ == "__main__":
    find_btc_markets()
