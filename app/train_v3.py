import torch
import torch.nn as nn
import pandas as pd
import numpy as np
import gc
import os
from sqlalchemy import create_engine
from sentence_transformers import SentenceTransformer
from sklearn.model_selection import train_test_split

# --- configuration ---
DB_PATH = "poly.db"
MODEL_PATH = "models/brain_v3.pt"

# --- device ---
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Using device: {device}")

# --- feature engineering ---
def custom_engineer_features(db_path=DB_PATH):
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return None, None
        
    engine = create_engine(f"sqlite:///{db_path}")
    print("Loading resolved events from database...")
    query = "SELECT * FROM events WHERE outcome IS NOT NULL"
    df = pd.read_sql(query, engine, parse_dates=['start_time', 'end_time'])

    if df.empty:
        print("No resolved events found.")
        return None, None

    print(f"Engineering features for {len(df)} samples...")
    df['time_to_event_days'] = (df['end_time'] - df['start_time']).dt.days
    
    print("Generating text embeddings (Batch Mode)...")
    st_model = SentenceTransformer('all-MiniLM-L6-v2')
    
    summaries = df['news_summary'].fillna('').tolist()
    all_embeddings = []
    batch_size = 1000
    
    for i in range(0, len(summaries), batch_size):
        batch = summaries[i:i + batch_size]
        batch_emb = st_model.encode(batch, show_progress_bar=False)
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
    return features, target

# --- model ---
class NeuralPredictor(nn.Module):
    def __init__(self, input_dim):
        super(NeuralPredictor, self).__init__()
        self.network = nn.Sequential(
            nn.Linear(input_dim, 128),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, 1),
            nn.Sigmoid()
        )
    def forward(self, x): return self.network(x)

# --- training loop ---
def train():
    features, target = custom_engineer_features()
    if features is None: return

    print(f"Dataset Shape: {features.shape}")

    X_train_pd, X_test_pd, y_train_pd, y_test_pd = train_test_split(features, target, test_size=0.2, random_state=42, stratify=target)
    
    # Convert to Tensor
    X_train = torch.FloatTensor(X_train_pd.values).to(device)
    y_train = torch.FloatTensor(y_train_pd.values).view(-1, 1).to(device)
    # Clear RAM
    del X_train_pd, y_train_pd
    gc.collect()

    model = NeuralPredictor(features.shape[1]).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    criterion = nn.BCELoss()
    
    print("Starting Training...")
    for epoch in range(20):
        model.train()
        optimizer.zero_grad()
        outputs = model(X_train)
        loss = criterion(outputs, y_train)
        loss.backward()
        optimizer.step()
        
        if (epoch+1) % 5 == 0: 
            print(f"Epoch {epoch+1} | Loss: {loss.item():.4f}")

    os.makedirs("models", exist_ok=True)
    torch.save(model.state_dict(), MODEL_PATH)
    print(f"Model saved to {MODEL_PATH}")

if __name__ == "__main__":
    train()
