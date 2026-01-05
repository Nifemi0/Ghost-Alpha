import sys
import os
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset, WeightedRandomSampler
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
import joblib
import datetime

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.feature_engineer import engineer_features

MODEL_DIR = "models"
MODEL_PATH = os.path.join(MODEL_DIR, "model.pt") # Now saving as PyTorch model
COLUMN_PATH = os.path.join(MODEL_DIR, "columns.pkl")

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

    def forward(self, x):
        return self.network(x)

def train_model():
    """
    Trains a PyTorch Neural Network on the massive engineered dataset.
    """
    features, target = engineer_features()

    if features is None or target is None:
        print("Could not train model because feature engineering returned no data.")
        return

    # Split data
    X_train_pd, X_test_pd, y_train_pd, y_test_pd = train_test_split(
        features, target, test_size=0.2, random_state=42, stratify=target
    )

    input_dim = X_train_pd.shape[1]
    print(f"Input dimension: {input_dim}")

    # Convert to Tensors
    X_train = torch.FloatTensor(X_train_pd.values)
    y_train = torch.FloatTensor(y_train_pd.values).view(-1, 1)
    X_test = torch.FloatTensor(X_test_pd.values)
    y_test = torch.FloatTensor(y_test_pd.values).view(-1, 1)

    import gc
    del X_train_pd, X_test_pd, y_train_pd, y_test_pd
    gc.collect()

    # Calculate Weights for Class Imbalance
    # We redraw from 'target' which is still in memory from engineer_features
    # Actually features and target from line 46 are still there too.
    # Let's clean them up after we have the tensors.
    
    # We'll use np.unique on y_train which is already a tensor
    targets_np = y_train.numpy().flatten()
    unique, counts = np.unique(targets_np, return_counts=True)
    weight = 1. / counts
    samples_weight = torch.from_numpy(np.array([weight[int(t)] for t in targets_np]))
    sampler = WeightedRandomSampler(samples_weight, len(samples_weight))
    
    del targets_np
    gc.collect()

    # DataLoaders
    train_dataset = TensorDataset(X_train, y_train)
    test_dataset = TensorDataset(X_test, y_test)
    
    # 115k samples -> Batch size 256 for CPU efficiency
    train_loader = DataLoader(train_dataset, batch_size=256, sampler=sampler)
    test_loader = DataLoader(test_dataset, batch_size=256, shuffle=False)

    # Initialize Model, Loss, Optimizer
    model = NeuralPredictor(input_dim)
    criterion = nn.BCELoss()
    optimizer = optim.Adam(model.parameters(), lr=0.001)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, 'min', patience=2, factor=0.5)

    print(f"Starting Neural Evolution Training on {len(X_train)} samples...")
    
    epochs = 20
    best_loss = float('inf')
    early_stop_patience = 5
    counter = 0

    for epoch in range(epochs):
        model.train()
        train_loss = 0
        for batch_x, batch_y in train_loader:
            optimizer.zero_grad()
            outputs = model(batch_x)
            loss = criterion(outputs, batch_y)
            loss.backward()
            optimizer.step()
            train_loss += loss.item()
        
        # Validation
        model.eval()
        val_loss = 0
        with torch.no_grad():
            for batch_x, batch_y in test_loader:
                outputs = model(batch_x)
                loss = criterion(outputs, batch_y)
                val_loss += loss.item()
        
        avg_train_loss = train_loss / len(train_loader)
        avg_val_loss = val_loss / len(test_loader)
        
        print(f"Epoch [{epoch+1}/{epochs}] | Train Loss: {avg_train_loss:.4f} | Val Loss: {avg_val_loss:.4f}")
        
        scheduler.step(avg_val_loss)

        # Early Stopping
        if avg_val_loss < best_loss:
            best_loss = avg_val_loss
            # Save the best model
            if not os.path.exists(MODEL_DIR):
                os.makedirs(MODEL_DIR)
            torch.save(model.state_dict(), MODEL_PATH)
            counter = 0
        else:
            counter += 1
            if counter >= early_stop_patience:
                print("Early stopping triggered.")
                break

    # Final Evaluation
    print("\nModel Evaluation (Best Weights):")
    model.load_state_dict(torch.load(MODEL_PATH))
    model.eval()
    with torch.no_grad():
        y_pred_probs = model(X_test)
        y_pred = (y_pred_probs > 0.5).float()
        
        print(f"Accuracy: {accuracy_score(y_test, y_pred):.4f}")
        print(classification_report(y_test, y_pred))

    # Save feature columns
    joblib.dump(list(features.columns), COLUMN_PATH)
    print(f"Neural brain weights saved to {MODEL_PATH}")
    print(f"Feature columns saved to {COLUMN_PATH}")

if __name__ == "__main__":
    train_model()
