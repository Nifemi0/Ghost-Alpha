import requests

def list_all_bitcoin():
    url = "https://gamma-api.polymarket.com/markets?active=true&closed=false&limit=1000"
    resp = requests.get(url).json()
    print(f"Total active markets: {len(resp)}")
    count = 0
    for m in resp:
        if 'Bitcoin' in m.get('question', ''):
            print(f"[{m.get('id')}] {m.get('question')}")
            count += 1
    print(f"Found {count} Bitcoin markets.")

if __name__ == "__main__":
    list_all_bitcoin()
