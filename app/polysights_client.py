"""
Polysights integration - fetch radar scores for wallets
Provides risk/quality metrics for insider detection
"""
import requests
import time

POLYSIGHTS_API = "https://polysights.xyz/api"  # Hypothetical endpoint

class PolysightsClient:
    """Client for Polysights API"""
    
    def __init__(self, api_key=None):
        self.api_key = api_key
        self.cache = {}
        self.cache_ttl = 3600  # 1 hour
    
    def get_radar_score(self, wallet_address):
        """
        Get radar score for wallet (0-100)
        Higher score = more suspicious/risky
        Returns None if not available
        """
        cache_key = f"radar_{wallet_address}"
        if cache_key in self.cache:
            cached_time, cached_value = self.cache[cache_key]
            if time.time() - cached_time < self.cache_ttl:
                return cached_value
        
        try:
            # Note: Polysights may not have a public API yet
            # This is a placeholder for when it becomes available
            headers = {}
            if self.api_key:
                headers['Authorization'] = f'Bearer {self.api_key}'
            
            resp = requests.get(
                f"{POLYSIGHTS_API}/wallet/{wallet_address}/radar",
                headers=headers,
                timeout=10
            )
            
            if resp.status_code == 200:
                data = resp.json()
                score = data.get('radar_score')
                
                if score is not None:
                    self.cache[cache_key] = (time.time(), score)
                    return score
            
            return None
            
        except Exception as e:
            # Silently fail - radar score is optional
            return None
    
    def get_wallet_metrics(self, wallet_address):
        """
        Get comprehensive wallet metrics
        Returns dict with: radar_score, total_volume, win_rate, etc.
        """
        try:
            headers = {}
            if self.api_key:
                headers['Authorization'] = f'Bearer {self.api_key}'
            
            resp = requests.get(
                f"{POLYSIGHTS_API}/wallet/{wallet_address}",
                headers=headers,
                timeout=10
            )
            
            if resp.status_code == 200:
                return resp.json()
            
            return {}
            
        except Exception as e:
            return {}

# Global instance
polysights = PolysightsClient()

if __name__ == "__main__":
    # Test
    test_wallet = "0x0000000000000000000000000000000000000000"
    
    score = polysights.get_radar_score(test_wallet)
    print(f"Radar score for {test_wallet}: {score}")
    
    metrics = polysights.get_wallet_metrics(test_wallet)
    print(f"Metrics: {metrics}")
