import requests

def get_crypto_markets():
    # Tag 1001 = Crypto
    url = "https://gamma-api.polymarket.com/markets?tag_id=1001&active=true&closed=false&limit=100"
    resp = requests.get(url).json()
    for m in resp:
        if 'Bitcoin' in m.get('question'):
            print(f"Q: {m.get('question')} | ID: {m.get('id')}")
            # Try to get orderbook info or price
            clob_id = m.get('clobTokenIds')
            print(f"  CLOB IDs: {clob_id}")

if __name__ == "__main__":
    get_crypto_markets()
