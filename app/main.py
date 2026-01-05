import sys
import os
import joblib
import pandas as pd
import torch
import torch.nn as nn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import create_engine
import datetime

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy.orm import sessionmaker
from data.database import DATABASE_URL, Event

# --- Application Setup ---
app = FastAPI(
    title="Polymarket Prediction API",
    description="An API to predict the outcome of Polymarket/Kalshi events.",
    version="1.1.0"
)

# --- Neural Engine Architecture ---
from app.neural_arch import NeuralPredictor

# --- Model and Feature Engineering Setup ---
MODEL_PATH = "models/brain_v3.pt"
COLUMN_PATH = "models/columns_v3.pkl"

model = None
model_columns = None

def load_brain():
    global model, model_columns
    if not os.path.exists(MODEL_PATH) or not os.path.exists(COLUMN_PATH):
        print(f"Warning: Neural brain ({MODEL_PATH}) or columns ({COLUMN_PATH}) not found.")
        return False
    
    try:
        model_columns = joblib.load(COLUMN_PATH)
        input_dim = len(model_columns)
        model = NeuralPredictor(input_dim)
        model.load_state_dict(torch.load(MODEL_PATH, map_location=torch.device('cpu')))
        model.eval()
        print(f"Neural brain v3 (dim={input_dim}) loaded successfully.")
        return True
    except Exception as e:
        print(f"Error loading neural brain: {e}")
        return False

load_brain()

# Load the sentence transformer model for embeddings
from sentence_transformers import SentenceTransformer
st_model = SentenceTransformer('all-MiniLM-L6-v2')
print("SentenceTransformer model loaded successfully.")

# --- Database Connection ---
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# --- API Models ---
class PredictionOut(BaseModel):
    market_id: int
    question: str
    predicted_outcome: bool
    prediction_probability: float

# --- Feature Engineering for a single prediction ---
def engineer_prediction_features(event_df: pd.DataFrame):
    """Engineers features for a single event for prediction."""
    event_df['time_to_event_days'] = (pd.to_datetime(event_df['end_time']) - pd.to_datetime(event_df['start_time'])).dt.days
    
    numerical_features = event_df[[
        'initial_price', 'volume', 'time_to_event_days'
    ]].fillna(0)

    category_dummies = pd.get_dummies(event_df['category'], prefix='cat')

    summary = event_df['news_summary'].fillna('').tolist()
    embedding = st_model.encode(summary, show_progress_bar=False)
    embedding_df = pd.DataFrame(embedding, index=event_df.index, columns=[f'emb_{i}' for i in range(embedding.shape[1])])
    
    features = pd.concat([numerical_features, category_dummies, embedding_df], axis=1)
    
    if model_columns:
        features = features.reindex(columns=model_columns, fill_value=0)
    
    # Ensure strict float32 type for PyTorch
    features = features.apply(pd.to_numeric, errors='coerce').fillna(0).astype('float32')
    
    return features

# --- API Endpoints ---
@app.get("/")
def read_root():
    return {"message": "Welcome to the Polymarket Neural Prediction API. Use the /predict endpoint."}

@app.get("/health")
def health_check():
    """Health check endpoint for monitoring"""
    return {
        "status": "healthy",
        "model_loaded": model is not None,
        "timestamp": datetime.datetime.now().isoformat()
    }

@app.get("/metrics")
def metrics():
    """Basic metrics endpoint"""
    conn = sqlite3.connect("poly.db")
    cursor = conn.cursor()
    
    # Get stats
    cursor.execute("SELECT COUNT(*) FROM events")
    total_events = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM events WHERE clob_token_id IS NOT NULL")
    events_with_ids = cursor.fetchone()[0]
    
    try:
        cursor.execute("SELECT COUNT(*) FROM insider_alerts")
        total_alerts = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM insider_alerts WHERE created_at > datetime('now', '-24 hours')")
        alerts_24h = cursor.fetchone()[0]
    except:
        total_alerts = 0
        alerts_24h = 0
    
    conn.close()
    
    return {
        "total_events": total_events,
        "events_with_clob_ids": events_with_ids,
        "clob_id_coverage": f"{events_with_ids/total_events*100:.1f}%" if total_events > 0 else "0%",
        "total_insider_alerts": total_alerts,
        "alerts_last_24h": alerts_24h,
        "model_loaded": model is not None
    }

@app.get("/predict", response_model=PredictionOut)
def predict(market_id: int):
    """Predicts the outcome of a given market using the Neural Engine."""
    if model is None or model_columns is None:
        # Try reloading once
        if not load_brain():
            raise HTTPException(status_code=503, detail="Neural brain is not yet trained or loaded.")

    db = SessionLocal()
    try:
        event = db.query(Event).filter(Event.id == market_id).first()
        if not event:
            raise HTTPException(status_code=404, detail=f"Market with id {market_id} not found.")
        
        event_df = pd.DataFrame([{
            'start_time': event.start_time,
            'end_time': event.end_time,
            'initial_price': event.initial_price,
            'volume': event.volume,
            'category': event.category,
            'news_summary': event.news_summary
        }])
        
        event_df['start_time'] = pd.to_datetime(event_df['start_time'])
        event_df['end_time'] = pd.to_datetime(event_df['end_time'])

        features_df = engineer_prediction_features(event_df)

        # PyTorch Inference
        with torch.no_grad():
            features_tensor = torch.FloatTensor(features_df.values)
            prediction_proba = model(features_tensor).item()
            predicted_class = bool(prediction_proba > 0.5)

        print(f"Prediction for market {market_id}: {'Yes' if predicted_class else 'No'} (Probability: {prediction_proba:.2f})")

        return {
            "market_id": market_id,
            "question": event.question,
            "predicted_outcome": predicted_class,
            "prediction_probability": prediction_proba
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error during prediction: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()
