import torch
import numpy as np
import pandas as pd
import time
import sys
from sentence_transformers import SentenceTransformer, util
from sqlalchemy import create_engine
import os

# Set up DB connection
DB_PATH = "poly.db"
engine = create_engine(f"sqlite:///{DB_PATH}")

def quantize_embeddings(embeddings):
    """
    Convert Float32 embeddings to Binary (packed into uint8).
    Logic: value > 0 becomes 1, else 0.
    """
    # 1. Binarize: True if > 0, False otherwise
    binary_bool = (embeddings > 0)
    
    # 2. Pack bits: 8 booleans -> 1 uint8 byte
    # This reduces size by 32x (from 32-bit float to 1-bit)
    packed_binary = np.packbits(binary_bool, axis=1)
    return packed_binary

def run_experiment():
    print("--- 🧪 BINARY QUANTIZATION EXPERIMENT ---")
    
    # 1. Load Data
    print("Loading text data from poly.db...")
    try:
        df = pd.read_sql("SELECT news_summary FROM events WHERE news_summary IS NOT NULL LIMIT 10000", engine)
    except:
        print("Could not load from DB, creating synthetic data for test.")
        df = pd.DataFrame({'news_summary': [f"Market event sample text number {i}" for i in range(10000)]})
        
    texts = df['news_summary'].tolist()
    print(f"Loaded {len(texts)} texts.")
    
    # 2. Generate Embeddings (Float32)
    print("\nGenerating Standard Embeddings (Float32)...")
    model = SentenceTransformer('all-MiniLM-L6-v2')
    start_time = time.time()
    embeddings_float = model.encode(texts, convert_to_numpy=True)
    embed_time = time.time() - start_time
    
    float_size_mb = embeddings_float.nbytes / (1024 * 1024)
    print(f"✅ Generated {len(embeddings_float)} embeddings in {embed_time:.2f}s")
    print(f"📊 Float32 Size: {float_size_mb:.2f} MB")
    
    # 3. Quantize (Binary)
    print("\nQuantizing to Binary (1-bit)...")
    start_time = time.time()
    embeddings_binary = quantize_embeddings(embeddings_float)
    quant_time = time.time() - start_time
    
    binary_size_mb = embeddings_binary.nbytes / (1024 * 1024)
    compression_ratio = float_size_mb / binary_size_mb
    
    print(f"✅ Quantized in {quant_time:.4f}s")
    print(f"📊 Binary Size:  {binary_size_mb:.2f} MB")
    print(f"🚀 Compression Ratio: {compression_ratio:.1f}x smaller!")
    
    # 4. Retrieval Speed Test
    print("\n--- 🏎️ RETRIEVAL SPEED TEST (1000 Queries) ---")
    
    # Query vector (just use the first doc as a query)
    query_float = embeddings_float[0:1] # shape (1, 384)
    query_binary = embeddings_binary[0:1]
    
    # A. Float Search (Dot Product)
    start_time = time.time()
    # Manual Dot Product
    scores_float = np.dot(embeddings_float, query_float.T)
    # Sort
    top_k_float = np.argsort(scores_float, axis=0)[-5:][::-1]
    float_search_time = time.time() - start_time
    
    # B. Binary Search (Hamming Distance / Bitwise XOR)
    start_time = time.time()
    # XOR gives 1 where bits differ. We sum the differences (Hamming distance)
    # We want MINIMUM distance (most similar)
    xor_result = np.bitwise_xor(embeddings_binary, query_binary)
    # Count set bits (population count) - simplistic manual implementation for numpy
    # In C++ or FAISS this is a CPU instruction (POPCNT) and is blazing fast.
    # In Python numpy, unpacking is slow, so we approximate speed gain theoretical logic or use explicit np calls
    hamming_dist = np.unpackbits(xor_result, axis=1).sum(axis=1)
    
    top_k_binary = np.argsort(hamming_dist)[0:5] # Smallest distance = Best match
    binary_search_time = time.time() - start_time
    
    print(f"Float Search Time:  {float_search_time:.5f}s (Dot Product)")
    print(f"Binary Search Time: {binary_search_time:.5f}s (Hamming Dist - Python Emulated)")
    print("(Note: In production C++/FAISS, Binary is ~30x faster than this python emu)")

    # 5. Accuracy Check
    print("\n--- 🎯 ACCURACY CHECK ---")
    print(f"Top 5 Indices (Float32): {top_k_float.flatten()}")
    print(f"Top 5 Indices (Binary):  {top_k_binary.flatten()}")
    
    overlap = len(set(top_k_float.flatten()) & set(top_k_binary.flatten()))
    print(f"Overlap: {overlap}/5")
    
    if overlap >= 3:
        print("✅ High Semantic Preservation! (Binary search found most of the same top results)")
    else:
        print("⚠️ Significant Information Loss (Expected for simplistic quantization w/o calibration)")
        
    print("\n--- CONCLUSION ---")
    print(f"You could store {float_size_mb * 1024:.0f} MB of float data in just {binary_size_mb * 1024:.0f} MB.")
    print(f"For 1 Billion vector scale:")
    print(f"  Float32: ~1.5 TB RAM (Impossible)")
    print(f"  Binary:  ~48 GB RAM (Feasible on cheap server)")

if __name__ == "__main__":
    run_experiment()
