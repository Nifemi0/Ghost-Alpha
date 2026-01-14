import requests

def search_btc_specific():
    # Searching for price targets
    queries = ["Bitcoin hit", "Bitcoin above", "Bitcoin reach"]
    for q in queries:
        url = "https://gamma-api.polymarket.com/markets"
        params = {"query": q, "active": "true", "closed": "false"}
        resp = requests.get(url, params=params).json()
        for market in resp:
            print(f"[{q}] {market.get('question')} | ID: {market.get('id')}")

if __name__ == "__main__":
    search_btc_specific()
