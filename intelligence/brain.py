
import os
import joblib
import pandas as pd
import logging

class GhostBrain:
    def __init__(self, model_path="ghost_model.pkl"):
        self.model_path = model_path
        self.model = None
        self.load()

    def load(self):
        try:
            if os.path.exists(self.model_path):
                self.model = joblib.load(self.model_path)
                print(f"🧠 [GHOST BRAIN] Intelligence Synchronized.", flush=True)
            else:
                print(f"🧠 [GHOST BRAIN] No Brain found. Running in brute-force mode.", flush=True)
        except Exception as e:
            print(f"❌ [GHOST BRAIN] Loading Failed: {e}", flush=True)

    def predict_confidence(self, move_size, entry_price, velocity):
        if not self.model:
            return 1.0 # Default to high confidence if no model (brute force)
            
        try:
            test_cases = [{"move_size": abs(move_size), "entry_price": entry_price, "velocity": abs(velocity), "hold_time": t} for t in [5.0, 7.0, 15.0]]
            df_test = pd.DataFrame(test_cases)
            
            # Get probabilities [Loss_Prob, Win_Prob]
            probs = self.model.predict_proba(df_test)
            # Max Win Probability across timelines
            return max([p[1] for p in probs])
        except:
            return 0.0
