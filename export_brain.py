"""
Script to export the trained brain and metadata to a zip file
Useful for backing up or downloading the model
"""
import zipfile
import os
import datetime

def export_brain():
    # Files to export
    files = [
        "models/brain_v3.pt",
        "models/columns_v3.pkl"
    ]
    
    # Check if files exist
    for f in files:
        if not os.path.exists(f):
            print(f"Error: {f} not found. Have you trained the model yet?")
            return
    
    # Create export filename with timestamp
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    export_file = f"poly_brain_v3_export_{ts}.zip"
    
    print(f"Creating export: {export_file}...")
    
    with zipfile.ZipFile(export_file, 'w') as zf:
        for f in files:
            zf.write(f)
            print(f"  Added {f}")
            
    print(f"\n✅ Export successful: {export_file}")
    print(f"File size: {os.path.getsize(export_file) / 1024 / 1024:.2f} MB")

if __name__ == "__main__":
    export_brain()
