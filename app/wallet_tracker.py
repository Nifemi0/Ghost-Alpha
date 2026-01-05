"""
Wallet tracking module for insider detection
Tracks wallet age, market count, and trading patterns
"""
import requests
import time
from datetime import datetime, timedelta
import sqlite3

GAMMA_API = "https://gamma-api.polymarket.com"
DB_PATH = "poly.db"

class WalletTracker:
    """Track wallet metrics for insider detection"""
    
    def __init__(self):
        self.cache = {}  # Simple in-memory cache
        self.cache_ttl = 600  # 10 minutes
    
    def get_wallet_age_hours(self, wallet_address):
        """
        Get wallet age in hours
        Returns None if wallet not found or error
        """
        cache_key = f"age_{wallet_address}"
        if cache_key in self.cache:
            cached_time, cached_value = self.cache[cache_key]
            if time.time() - cached_time < self.cache_ttl:
                return cached_value
        
        try:
            # Fetch wallet's first trade from Polymarket API
            resp = requests.get(
                f"{GAMMA_API}/trades",
                params={"maker": wallet_address, "limit": 1, "order": "asc"},
                timeout=10
            )
            
            if resp.status_code == 200:
                trades = resp.json()
                if trades and len(trades) > 0:
                    first_trade_ts = trades[0].get("timestamp")
                    if first_trade_ts:
                        # Convert to datetime
                        first_trade_time = datetime.fromtimestamp(first_trade_ts)
                        age_hours = (datetime.now() - first_trade_time).total_seconds() / 3600
                        
                        # Cache result
                        self.cache[cache_key] = (time.time(), age_hours)
                        return age_hours
            
            return None
            
        except Exception as e:
            print(f"Error fetching wallet age for {wallet_address}: {e}")
            return None
    
    def get_market_count(self, wallet_address):
        """
        Get number of distinct markets this wallet has traded in
        Returns 0 if wallet not found or error
        """
        cache_key = f"markets_{wallet_address}"
        if cache_key in self.cache:
            cached_time, cached_value = self.cache[cache_key]
            if time.time() - cached_time < self.cache_ttl:
                return cached_value
        
        try:
            # Fetch all trades for this wallet
            resp = requests.get(
                f"{GAMMA_API}/trades",
                params={"maker": wallet_address, "limit": 1000},
                timeout=10
            )
            
            if resp.status_code == 200:
                trades = resp.json()
                # Count unique market IDs
                market_ids = set()
                for trade in trades:
                    market_id = trade.get("market_id") or trade.get("asset_id")
                    if market_id:
                        market_ids.add(market_id)
                
                count = len(market_ids)
                # Cache result
                self.cache[cache_key] = (time.time(), count)
                return count
            
            return 0
            
        except Exception as e:
            print(f"Error fetching market count for {wallet_address}: {e}")
            return 0
    
    def is_fresh_wallet(self, wallet_address, max_age_hours=24, max_markets=2):
        """
        Check if wallet meets "fresh wallet" criteria
        Returns (is_fresh, age_hours, market_count)
        """
        age = self.get_wallet_age_hours(wallet_address)
        if age is None:
            return (False, None, 0)
        
        market_count = self.get_market_count(wallet_address)
        
        is_fresh = (age < max_age_hours) and (market_count <= max_markets)
        return (is_fresh, age, market_count)

# Global instance
tracker = WalletTracker()

if __name__ == "__main__":
    # Test with a known wallet
    test_wallet = "0x0000000000000000000000000000000000000000"  # Replace with real wallet
    
    is_fresh, age, markets = tracker.is_fresh_wallet(test_wallet)
    print(f"Wallet: {test_wallet}")
    print(f"Age: {age:.1f} hours" if age else "Age: Unknown")
    print(f"Markets: {markets}")
    print(f"Is Fresh: {is_fresh}")
