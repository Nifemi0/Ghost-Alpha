import requests
import datetime
import time

# CLOB API Base URL
CLOB_API_URL = "https://clob.polymarket.com"

def get_price_history(token_id, start_ts, end_ts):
    """
    Fetches price history for a specific token from the CLOB API.
    """
    endpoint = f"{CLOB_API_URL}/prices-history"
    params = {
        "market": token_id,
        # "startTs": int(start_ts * 1000), 
        # "endTs": int(end_ts * 1000),   
        "interval": "max", 
        "fidelity": 60    # 60 minutes fidelity
    }
    
    try:
        response = requests.get(endpoint, params=params)
        response.raise_for_status()
        data = response.json()
        return data
    except Exception as e:
        print(f"Error fetching candles: {e}")
        return None

if __name__ == "__main__":
    # Test with the retrieved valid clobTokenId
    TEST_TOKEN_ID = "115004480493856471532023861752099458478620074016077632405861264483986766893778"
    
    # Range: Last 30 days
    end_time_ts = int(time.time())
    start_time_ts = end_time_ts - (30 * 24 * 60 * 60)
    
    print(f"Fetching candles for Token {TEST_TOKEN_ID[:10]}...")
    data = get_price_history(TEST_TOKEN_ID, start_time_ts, end_time_ts)
    
    if data:
        print(f"Success! Retrieved {len(data['history'])} candles.")
        if len(data['history']) > 0:
            print("Sample Candle:", data['history'][0])
    else:
        print("Failed to retrieve data.")
