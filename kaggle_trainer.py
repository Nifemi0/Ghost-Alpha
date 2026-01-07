# Kaggle Training Script for PolyBot Neural Brain
# Copy this entire script into a Kaggle Notebook to train with free GPU

import os
import subprocess
import sys

# 1. Install dependencies
print("Installing dependencies...")
subprocess.check_call([sys.executable, "-m", "pip", "install", "sentence-transformers", "SQLAlchemy"])

import torch
import torch.nn as nn
import pandas as pd
import numpy as np
import gc
import joblib
from sqlalchemy import create_engine
from sentence_transformers import SentenceTransformer
from sklearn.model_selection import train_test_split

print(f"PyTorch Version: {torch.__version__}")
print(f"CUDA Available: {torch.cuda.is_available()}")

# --- Configuration ---
# Kaggle input datasets are usually at /kaggle/input/dataset-name/
# We assume you uploaded poly.db as a dataset
DB_PATH = "/kaggle/input/polybot-brain-data/poly.db" 
# Output path for trained model
OUTPUT_DIR = "/kaggle/working/"
MODEL_PATH = os.path.join(OUTPUT_DIR, "brain_v3.pt")
COLUMN_PATH = os.path.join(OUTPUT_DIR, "columns_v3.pkl")

# --- Feature Engineering ---
def engineer_features(db_path):
    if not os.path.exists(db_path):
        # Fallback if user hasn't uploaded dataset yet
        print(f"Dataset not found at {db_path}. Checking common paths...")
        # Check if just in current dir (local run)
        if os.path.exists("poly.db"):
            print("Found poly.db in current directory.")
            db_path = "poly.db"
        else:
             # Check generic input path
            if os.path.exists("/kaggle/input/poly.db"):
                db_path = "/kaggle/input/poly.db"
            else:
                print("Could not find poly.db! Please upload it.")
                return None, None, None

    engine = create_engine(f"sqlite:///{db_path}")
    print("Loading resolved events from database...")
    try:
        query = "SELECT * FROM events WHERE outcome IS NOT NULL"
        df = pd.read_sql(query, engine, parse_dates=['start_time', 'end_time'])
    except Exception as e:
        print(f"Error reading database: {e}")
        return None, None, None

    if df.empty:
        print("No resolved events found.")
        return None, None, None

    print(f"Engineering features for {len(df)} samples...")
    # Basic features
    df['time_to_event_days'] = (df['end_time'] - df['start_time']).dt.days
    
    print("Generating text embeddings (Batch Mode)...")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    st_model = SentenceTransformer('all-MiniLM-L6-v2', device=device)
    
    summaries = df['news_summary'].fillna('').tolist()
    all_embeddings = []
    batch_size = 2000  # Larger batch for GPU
    
    for i in range(0, len(summaries), batch_size):
        batch = summaries[i:i + batch_size]
        batch_emb = st_model.encode(batch, show_progress_bar=True, batch_size=512)
        all_embeddings.append(batch_emb)
        gc.collect()
    
    embeddings = np.vstack(all_embeddings)
    embedding_df = pd.DataFrame(embeddings, index=df.index, columns=[f'emb_{i}' for i in range(embeddings.shape[1])])
    
    category_dummies = pd.get_dummies(df['category'], prefix='cat')
    numerical_features = df[['initial_price', 'volume', 'time_to_event_days']].fillna(0)
    
    features = pd.concat([numerical_features, category_dummies, embedding_df], axis=1)
    
    # Ensure float32
    features = features.apply(pd.to_numeric, errors='coerce').fillna(0).astype('float32')
    
    target = df['outcome'].astype(int)
    feature_columns = features.columns.tolist()
    
    return features, target, feature_columns

# --- Model Arch ---
class NeuralPredictor(nn.Module):
    def __init__(self, input_dim):
        super(NeuralPredictor, self).__init__()
        self.network = nn.Sequential(
            nn.Linear(input_dim, 256),  # Larger for GPU
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, 1),
            nn.Sigmoid()
        )
    def forward(self, x): return self.network(x)

# --- Training ---
def train():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Starting training on {device}...")
    
    features, target, columns = engineer_features(DB_PATH)
    if features is None: return

    print(f"Dataset Shape: {features.shape}")
    joblib.dump(columns, COLUMN_PATH)
    print(f"Feature columns saved to {COLUMN_PATH}")

    X_train_pd, X_test_pd, y_train_pd, y_test_pd = train_test_split(features, target, test_size=0.2, random_state=42, stratify=target)
    
    # Convert to Tensor
    X_train = torch.FloatTensor(X_train_pd.values).to(device)
    y_train = torch.FloatTensor(y_train_pd.values).view(-1, 1).to(device)
    X_test = torch.FloatTensor(X_test_pd.values).to(device)
    y_test = torch.FloatTensor(y_test_pd.values).view(-1, 1).to(device)
    
    del X_train_pd, y_train_pd, X_test_pd, y_test_pd
    gc.collect()

    model = NeuralPredictor(features.shape[1]).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.0005)
    criterion = nn.BCELoss()
    
    best_loss = float('inf')
    patience = 5
    patience_counter = 0
    
    print("Training loop...")
    for epoch in range(50):
        model.train()
        optimizer.zero_grad()
        outputs = model(X_train)
        loss = criterion(outputs, y_train)
        loss.backward()
        optimizer.step()
        
        # Validation
        model.eval()
        with torch.no_grad():
            val_out = model(X_test)
            val_loss = criterion(val_out, y_test)
            preds = (val_out > 0.5).float()
            accuracy = (preds == y_test).float().mean()
        
        print(f"Epoch {epoch+1:2d} | Train Loss: {loss.item():.4f} | Val Loss: {val_loss.item():.4f} | Val Acc: {accuracy.item():.2%}")
        
        if val_loss < best_loss:
            best_loss = val_loss
            torch.save(model.state_dict(), MODEL_PATH)
            patience_counter = 0
        else:
            patience_counter += 1
            if patience_counter >= patience:
                print("Early stopping!")
                break

    print(f"Done! Model saved to {MODEL_PATH}")

if __name__ == "__main__":
    train()
