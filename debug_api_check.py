import requests
import json

def check_one_market():
    url = "https://gamma-api.polymarket.com/events?limit=1&closed=true"
    try:
        response = requests.get(url)
        data = response.json()
        if data and 'markets' in data[0]:
            print("First Market Object Keys:")
            # specifically print the first market in the list
            print(json.dumps(data[0]['markets'][0], indent=2))
        else:
            print("No markets found in event.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_one_market()
