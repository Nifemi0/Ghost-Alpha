import requests
import json

def list_clob_btc():
    url = "https://clob.polymarket.com/markets"
    # This might return a long list, we search for BTC
    try:
        resp = requests.get(url).json()
        print(f"Total CLOB markets: {len(resp)}")
        for m in resp:
            if 'BTC' in str(m) or 'Bitcoin' in str(m):
                print(f"Market: {m.get('id') or m.get('condition_id')}")
                print(f"Question: {m.get('question') or m.get('description')}")
                print(f"Tokens: {m.get('tokens')}")
                print("-" * 30)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    list_clob_btc()
