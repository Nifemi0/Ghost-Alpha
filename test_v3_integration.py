from fastapi.testclient import TestClient
from app.main import app
from sqlalchemy import create_engine
import pandas as pd
import random

client = TestClient(app)
DB_PATH = "poly.db"

def test_random_prediction():
    print("--- Testing Neural Brain v3 Integration ---")
    engine = create_engine(f"sqlite:///{DB_PATH}")
    
    # Get a random market ID
    try:
        query = "SELECT id, question, outcome FROM events WHERE outcome IS NOT NULL LIMIT 100"
        df = pd.read_sql(query, engine)
        
        if df.empty:
            print("No resolved events found in DB.")
            return

        random_market = df.sample(1).iloc[0]
        market_id = int(random_market['id'])
        print(f"Selected Market ID: {market_id}")
        print(f"Question: {random_market['question']}")
        print(f"Actual Outcome: {'Yes' if random_market['outcome'] else 'No'}")
        
    except Exception as e:
        print(f"DB Error: {e}")
        return

    # Call API
    try:
        print(f"Sending request to /predict?market_id={market_id} ...")
        response = client.get(f"/predict?market_id={market_id}")
        
        if response.status_code == 200:
            data = response.json()
            prob = data['prediction_probability']
            pred = data['predicted_outcome']
            
            print("\n✅ API Response Received:")
            print(f"   prediction_probability: {prob:.4f}")
            print(f"   predicted_outcome: {pred} ({'Yes' if pred else 'No'})")
            
            # Context
            print(f"\nModel Confidence: {abs(prob - 0.5) * 2 * 100:.1f}%")
            
        else:
            print(f"\n❌ API Error {response.status_code}: {response.text}")

    except Exception as e:
        print(f"Client Error: {e}")

if __name__ == "__main__":
    test_random_prediction()
