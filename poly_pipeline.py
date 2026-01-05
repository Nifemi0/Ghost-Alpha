import subprocess
import time
import datetime
import os

PROJECT_ROOT = "/root/.gemini/antigravity/scratch/poly"
PYTHON_BIN = os.path.join(PROJECT_ROOT, "venv/bin/python3")

def run_step(name, command):
    print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] STARTING: {name}")
    try:
        # We use a large timeout for the collector as it might take hours
        subprocess.run(command, check=True, cwd=PROJECT_ROOT)
        print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] COMPLETED: {name}")
    except subprocess.CalledProcessError as e:
        print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ERROR in {name}: {e}")

def main_loop():
    while True:
        # Step 1: Deep Harvest (All history)
        # Note: collector.py is now set to infinite skip if total_limit=None
        run_step("Data Harvest", [PYTHON_BIN, "data/collector.py"])
        
        # Step 2: Train Model
        run_step("Model Training", [PYTHON_BIN, "app/trainer.py"])
        
        # Step 3: Sleep
        print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] CYCLE COMPLETE. Sleeping for 4 hours...")
        time.sleep(14400) # 4 hours

if __name__ == "__main__":
    main_loop()
