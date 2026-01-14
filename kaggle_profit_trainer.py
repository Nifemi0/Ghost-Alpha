# Kaggle Profit-Optimization Training Script (Brain v4)
# Optimizes for Sharpe Ratio / PnL instead of just Accuracy.

import os
import subprocess
import sys
import glob

# 1. Install dependencies
print("\n--- INSTALLING DEPENDENCIES ---")
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

print(f"\nPyTorch Version: {torch.__version__}")
print(f"CUDA Available: {torch.cuda.is_available()}")

# --- AUTO-FIND DATABASE ---
print("\n--- LOCATING POLY.DB ---")
found_dbs = glob.glob("/kaggle/input/**/poly.db", recursive=True)
if not found_dbs:
    # Local fallback for testing
    if os.path.exists("poly.db"):
        DB_PATH = "poly.db"
    else:
        raise FileNotFoundError("Please add the Dataset to the notebook!")
else:
    DB_PATH = found_dbs[0]

print(f"✅ Found database at: {DB_PATH}")

OUTPUT_DIR = "/kaggle/working/"
MODEL_PATH = os.path.join(OUTPUT_DIR, "brain_v4_profit.pt")
COLUMN_PATH = os.path.join(OUTPUT_DIR, "columns_v4.pkl")

# --- CUSTOM PROFIT LOSS FUNCTION ---
class SharpeLoss(nn.Module):
    """
    Differentiable approximation of negative Sharpe Ratio.
    Teaches the model to maximize returns while penalizing volatility (risk).
    """
    def __init__(self, trading_fee=0.01):
        super(SharpeLoss, self).__init__()
        self.trading_fee = trading_fee

    def forward(self, predictions, targets, prices):
        """
        predictions: Model output (0 to 1), representing confidence/bet size.
        targets: Actual outcome (1.0 for Yes, 0.0 for No).
        prices: The cost to buy 'Yes' share (0.0 to 1.0).
        """
        # 1. Determine Position: 
        # If Pred > 0.5, we Buy YES. Size = (Pred - 0.5) * 2
        # If Pred < 0.5, we Buy NO.  Size = (0.5 - Pred) * 2
        # This makes it a "Long/Short" strategy where 0.5 is Neutral (Cash).
        
        # Shift predictions to -1 (Strong No) to +1 (Strong Yes)
        signals = (predictions - 0.5) * 2.0 
        
        # 2. Calculate Return of holding YES
        # If Yes Win: Return is (1.0 - Price)
        # If Yes Lose: Return is (0.0 - Price)
        yes_return_if_win = (1.0 - prices)
        yes_return_if_loss = (0.0 - prices)
        
        actual_yes_return = targets * yes_return_if_win + (1 - targets) * yes_return_if_loss
        
        # 3. Calculate Portfolio PnL
        # If Signal > 0 (Long Yes), we get actual_yes_return
        # If Signal < 0 (Short Yes/Long No), we get -1 * actual_yes_return
        
        # Subtract trading fee proportional to trade size magnitude
        trade_pnl = (signals * actual_yes_return) - (torch.abs(signals) * self.trading_fee)
        
        # 4. Sharpe Ratio Calculation (Mean / StdDev)
        expected_return = torch.mean(trade_pnl)
        risk = torch.std(trade_pnl) + 1e-6 # prevent div by zero
        
        sharpe = expected_return / risk
        
        # We want to MAXIMIZE Sharpe, so we MINIMIZE negative Sharpe
        return -sharpe

# --- Model Definition ---
class NeuralPredictor(nn.Module):
    def __init__(self, input_dim):
        super(NeuralPredictor, self).__init__()
        # Matches v3.1 Architecture
        self.layer_1 = nn.Linear(input_dim, 256)
        self.batchnorm1 = nn.BatchNorm1d(256)
        self.layer_2 = nn.Linear(256, 128)
        self.batchnorm2 = nn.BatchNorm1d(128)
        self.layer_3 = nn.Linear(128, 64)
        self.batchnorm3 = nn.BatchNorm1d(64)
        self.layer_out = nn.Linear(64, 1)
        
        self.relu = nn.ReLU()
        self.dropout = nn.Dropout(p=0.3) 

    def forward(self, x):
        x = self.layer_1(x)
        if x.shape[0]>1: x = self.batchnorm1(x)
        x = self.relu(x)
        x = self.dropout(x)
        
        x = self.layer_2(x)
        if x.shape[0]>1: x = self.batchnorm2(x)
        x = self.relu(x)
        x = self.dropout(x)
        
        x = self.layer_3(x)
        if x.shape[0]>1: x = self.batchnorm3(x)
        x = self.relu(x)
        x = self.dropout(x)
        
        x = self.layer_out(x)
        return torch.sigmoid(x)

# --- Feature Engineering ---
def engineer_features(db_path):
    print(f"\n--- READING DATABASE: {db_path} ---")
    engine = create_engine(f"sqlite:///{db_path}")
    
    try:
        with engine.connect() as conn:
            # We NEED 'initial_price' for profit calculation!
            query = "SELECT * FROM events WHERE outcome IS NOT NULL AND initial_price IS NOT NULL"
            df = pd.read_sql(query, conn, parse_dates=['start_time', 'end_time'])
    except:
        import sqlite3
        with sqlite3.connect(db_path) as conn:
            df = pd.read_sql("SELECT * FROM events WHERE outcome IS NOT NULL AND initial_price IS NOT NULL", conn, parse_dates=['start_time', 'end_time'])
            
    if df.empty: return None, None, None, None

    print(f"Engineering features for {len(df)} samples...")
    df['time_to_event_days'] = (df['end_time'] - df['start_time']).dt.days
    
    print("Generating BERT embeddings...")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    st_model = SentenceTransformer('all-MiniLM-L6-v2', device=device)
    
    summaries = df['news_summary'].fillna('').tolist()
    all_embeddings = []
    batch_size = 2048
    
    for i in range(0, len(summaries), batch_size):
        batch = summaries[i:i + batch_size]
        batch_emb = st_model.encode(batch, show_progress_bar=False, batch_size=512)
        all_embeddings.append(batch_emb)
        gc.collect()
    
    embeddings = np.vstack(all_embeddings)
    embedding_df = pd.DataFrame(embeddings, index=df.index, columns=[f'emb_{i}' for i in range(embeddings.shape[1])])
    
    category_dummies = pd.get_dummies(df['category'], prefix='cat')
    numerical_features = df[['initial_price', 'volume', 'time_to_event_days']].fillna(0)
    
    features = pd.concat([numerical_features, category_dummies, embedding_df], axis=1)
    features = features.apply(pd.to_numeric, errors='coerce').fillna(0).astype('float32')
    
    target = df['outcome'].astype(int)
    # We pass PRICES separately for the loss function
    prices = df['initial_price'].fillna(0.5).astype('float32')
    
    return features, target, prices, features.columns.tolist()

# --- Training Loop ---
def train_profit_model():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"\n--- STARTING PROFIT TRAINING ON {device} ---")
    
    features, target, prices, columns = engineer_features(DB_PATH)
    if features is None: return

    joblib.dump(columns, COLUMN_PATH)

    # Split everything including PRICES
    X_train_pd, X_test_pd, y_train_pd, y_test_pd, p_train_pd, p_test_pd = train_test_split(
        features, target, prices, test_size=0.15, random_state=42, stratify=target
    )
    
    X_train = torch.FloatTensor(X_train_pd.values).to(device)
    y_train = torch.FloatTensor(y_train_pd.values).view(-1, 1).to(device)
    p_train = torch.FloatTensor(p_train_pd.values).view(-1, 1).to(device) # Prices
    
    X_test = torch.FloatTensor(X_test_pd.values).to(device)
    y_test = torch.FloatTensor(y_test_pd.values).view(-1, 1).to(device)
    p_test = torch.FloatTensor(p_test_pd.values).view(-1, 1).to(device)
    
    del X_train_pd, y_train_pd
    gc.collect()

    model = NeuralPredictor(len(columns)).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.0005) # Slower/Stable LR
    
    # !!! CUSTOM LOSS !!!
    criterion = SharpeLoss(trading_fee=0.01)
    
    print("\n--- PROFIT OPTIMIZATION LOOP ---")
    best_sharpe = -float('inf')
    
    for epoch in range(150):
        model.train()
        optimizer.zero_grad()
        outputs = model(X_train)
        
        # Loss uses PRICES too!
        loss = criterion(outputs, y_train, p_train)
        loss.backward()
        optimizer.step()
        
        model.eval()
        with torch.no_grad():
            val_out = model(X_test)
            val_loss = criterion(val_out, y_test, p_test)
            
            # Simple Accuracy Metric just for info (model is NOT optimizing this)
            preds_binary = (val_out > 0.5).float()
            accuracy = (preds_binary == y_test).float().mean()
            
            # Convert Neg Sharpe back to Sharpe
            current_sharpe = -val_loss.item()
        
        print(f"Epoch {epoch+1:3d} | Sharpe Ratio: {current_sharpe:.4f} | Acc: {accuracy.item():.2%}")
        
        if current_sharpe > best_sharpe:
            best_sharpe = current_sharpe
            torch.save(model.state_dict(), MODEL_PATH)

    print(f"\n✅ DONE! Best Sharpe: {best_sharpe:.4f}. Model saved to {MODEL_PATH}")

if __name__ == "__main__":
    train_profit_model()
