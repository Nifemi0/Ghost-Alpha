import sys
import os
import pandas as pd
from sqlalchemy import create_engine

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data.database import DATABASE_URL

import gc
from sentence_transformers import SentenceTransformer
import numpy as np

def engineer_features():
    """
    Loads data from the database, filters for resolved markets,
    and engineers features for the prediction model.
    Optimized for low-memory VPS environments.
    """
    engine = create_engine(DATABASE_URL)
    
    print("Loading resolved events from database...")
    query = "SELECT * FROM events WHERE outcome IS NOT NULL"
    df = pd.read_sql(query, engine, parse_dates=['start_time', 'end_time'])

    if df.empty:
        print("No resolved events found.")
        return None, None

    print(f"Engineering features for {len(df)} samples...")
    
    # 1. Date-based features
    df['time_to_event_days'] = (df['end_time'] - df['start_time']).dt.days
    
    # 2. Text features (Iterative Batch Processing)
    print("Generating text embeddings (Batch Mode)...")
    st_model = SentenceTransformer('all-MiniLM-L6-v2')
    
    summaries = df['news_summary'].fillna('').tolist()
    all_embeddings = []
    batch_size = 1000
    
    for i in range(0, len(summaries), batch_size):
        batch = summaries[i:i + batch_size]
        print(f"  Embedding batch {i//batch_size + 1}/{(len(summaries)-1)//batch_size + 1}...")
        batch_emb = st_model.encode(batch, show_progress_bar=False)
        all_embeddings.append(batch_emb)
        gc.collect() # Force cleanup
    
    embeddings = np.vstack(all_embeddings)
    embedding_df = pd.DataFrame(embeddings, index=df.index, columns=[f'emb_{i}' for i in range(embeddings.shape[1])])
    
    # Cleanup raw lists
    del summaries
    del all_embeddings
    gc.collect()

    # 3. Categorical features
    category_dummies = pd.get_dummies(df['category'], prefix='cat')
    
    # 4. Numerical features
    numerical_features = df[[
        'initial_price',
        'volume',
        'time_to_event_days'
    ]].fillna(0)
    
    # Combine (Ensure numeric types for PyTorch)
    features = pd.concat([numerical_features, category_dummies, embedding_df], axis=1)
    features = features.apply(pd.to_numeric, errors='coerce').fillna(0).astype('float32')
    
    target = df['outcome'].astype(int)
    
    print(f"Features engineered. Shape: {features.shape}")
    
    # Final cleanup of the source dataframe to save RAM before returning
    del df
    gc.collect()
    
    return features, target

if __name__ == '__main__':
    engineer_features()
