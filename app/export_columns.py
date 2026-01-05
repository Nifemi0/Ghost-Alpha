import pandas as pd
import joblib
import os
from sqlalchemy import create_engine
import numpy as np

# Re-use logic from train_v3.py to ensure identical columns
def get_columns():
    db_path = "poly.db"
    if not os.path.exists(db_path):
        print("DB not found")
        return

    engine = create_engine(f"sqlite:///{db_path}")
    print("Reading distinct categories...")
    # We only need the structure, not the full embeddings, to determine columns
    # But wait, dummy columns depend on *all* categories present.
    
    query = "SELECT * FROM events WHERE outcome IS NOT NULL"
    df = pd.read_sql(query, engine)
    
    if df.empty:
        print("df empty")
        return

    # Mimic Feature Engineering structure
    # 1. Numerical
    # 'initial_price', 'volume', 'time_to_event_days'
    
    # 2. Categories
    category_dummies = pd.get_dummies(df['category'], prefix='cat')
    
    # 3. Embeddings (384 dims)
    # We don't need to actually compute them to know the names
    embedding_cols = [f'emb_{i}' for i in range(384)]
    
    # Construct final list
    numerical_cols = ['initial_price', 'volume', 'time_to_event_days']
    cat_cols = category_dummies.columns.tolist()
    
    final_columns = numerical_cols + cat_cols + embedding_cols
    
    print(f"Total Columns: {len(final_columns)}")
    print(f"Sample: {final_columns[:5]} ... {final_columns[-5:]}")
    
    os.makedirs("models", exist_ok=True)
    joblib.dump(final_columns, "models/columns_v3.pkl")
    print("Saved to models/columns_v3.pkl")

if __name__ == "__main__":
    get_columns()
