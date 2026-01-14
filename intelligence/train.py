import pandas as pd
import numpy as np
import json
import os
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, accuracy_score
import joblib

TRADE_LOG = "trade_log.txt"
SIM_LOG = "multiverse_sims.jsonl"
MODEL_FILE = "ghost_model.pkl"

def parse_pipe_log(line):
    # Format: timestamp|mode|user_id|move|entry|exit|hold_time|profit|balance|exit_reason
    try:
        parts = line.strip().split('|')
        if len(parts) < 10: return None
        
        mode = parts[1]
        if "OBSERVER" not in mode and "EXECUTOR" not in mode:
            return None
            
        move = float(parts[3])
        entry = float(parts[4])
        hold = float(parts[6].replace('s', ''))
        profit = float(parts[7])
        
        return {
            "move_size": abs(move),
            "entry_price": entry,
            "hold_time": hold,
            "velocity": 0.0, # Legacy logs don't have velocity
            "is_profitable": 1 if profit > 0 else 0
        }
    except:
        return None

def parse_json_log(line):
    try:
        data = json.loads(line)
        return {
            "move_size": abs(data["move"]),
            "entry_price": data["entry"],
            "hold_time": float(data["hold"]),
            "velocity": float(data.get("velocity", 0.0)),
            "is_profitable": 1 if float(data["profit"]) > 0 else 0
        }
    except:
        return None

def train_brain():
    print("🧠 [GHOST BRAIN] Harvesting Data for Retraining...")
    
    dataset = []
    
    # Source 1: Standard Logs
    if os.path.exists(TRADE_LOG):
        with open(TRADE_LOG, 'r') as f:
            for line in f:
                p = parse_pipe_log(line)
                if p: dataset.append(p)
                
    # Source 2: Multiverse Simulations (High Volume)
    if os.path.exists(SIM_LOG):
        with open(SIM_LOG, 'r') as f:
            for line in f:
                p = parse_json_log(line)
                if p: dataset.append(p)
    
    if len(dataset) < 50:
        print(f"❌ Not enough data (Got {len(dataset)}). Need at least 50 points to retrain.")
        return

    df = pd.DataFrame(dataset)
    print(f"📊 Dataset Size: {len(df)} samples (Merged {len(dataset)} points)")
    print(f"💰 Global Win Rate: {df['is_profitable'].mean()*100:.1f}%")
    
    # Feature Engineering
    X = df[['move_size', 'entry_price', 'hold_time', 'velocity']]
    y = df['is_profitable']
    
    # Split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # Train
    print("🏋️ Training Random Forest (Alpha Mode)...")
    clf = RandomForestClassifier(n_estimators=200, max_depth=10, random_state=42)
    clf.fit(X_train, y_train)
    
    # Evaluate
    preds = clf.predict(X_test)
    acc = accuracy_score(y_test, preds)
    
    print("\n" + "="*40)
    print(f"🤖 BRAIN UPDATED: Accuracy {acc*100:.21}%")
    print("="*40)
    
    # Save the model
    joblib.dump(clf, MODEL_FILE)
    print(f"💾 Model archived to {MODEL_FILE}")
    
    # Predictor preview
    importances = clf.feature_importances_
    print("\n🔍 Intelligence Insights:")
    for name, imp in zip(X.columns, importances):
        print(f"   - {name}: {imp:.4f}")

if __name__ == "__main__":
    train_brain()
