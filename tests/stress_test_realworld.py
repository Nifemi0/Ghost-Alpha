"""
Real-world stress test suite
Tests prediction feature against live markets and validates all components
"""
import sys
import os
import time
import requests
import sqlite3
from datetime import datetime
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configuration
API_BASE = "http://localhost:8000"
GAMMA_API = "https://gamma-api.polymarket.com"
DB_PATH = "poly.db"

# Test tracking
results = {
    "passed": 0,
    "failed": 0,
    "warnings": 0,
    "start_time": None,
    "end_time": None
}

def log_result(test_name, status, message="", details=None):
    """Log test result"""
    symbols = {"PASS": "✅", "FAIL": "❌", "WARN": "⚠️"}
    print(f"{symbols.get(status, '•')} {test_name}: {message}")
    
    if status == "PASS":
        results["passed"] += 1
    elif status == "FAIL":
        results["failed"] += 1
    else:
        results["warnings"] += 1
    
    if details:
        print(f"   Details: {details}")

def fetch_live_markets(limit=10):
    """Fetch live markets from Polymarket"""
    try:
        resp = requests.get(
            f"{GAMMA_API}/markets",
            params={"closed": "false", "limit": limit},
            timeout=30
        )
        
        if resp.status_code == 200:
            markets = resp.json()
            log_result("Fetch Live Markets", "PASS", f"Retrieved {len(markets)} active markets")
            return markets
        else:
            log_result("Fetch Live Markets", "FAIL", f"API returned {resp.status_code}")
            return []
    except Exception as e:
        log_result("Fetch Live Markets", "FAIL", str(e))
        return []

def test_prediction_on_live_market(market):
    """Test prediction endpoint with a live market"""
    try:
        market_id = market.get('id')
        question = market.get('question', 'Unknown')
        
        # Call prediction API
        resp = requests.get(
            f"{API_BASE}/predict",
            params={"market_id": market_id},
            timeout=10
        )
        
        if resp.status_code == 200:
            data = resp.json()
            prediction = data.get('prediction')
            probability = data.get('probability', 0)
            
            log_result(
                f"Predict Market {market_id}",
                "PASS",
                f"{prediction} ({probability:.1%})",
                f"Question: {question[:60]}..."
            )
            return True
        else:
            log_result(
                f"Predict Market {market_id}",
                "FAIL",
                f"API returned {resp.status_code}"
            )
            return False
            
    except Exception as e:
        log_result(f"Predict Market {market.get('id')}", "FAIL", str(e))
        return False

def test_prediction_accuracy_sample():
    """Test prediction accuracy on a sample of resolved markets"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get 20 random resolved markets
        cursor.execute("""
            SELECT id, question, outcome
            FROM events
            WHERE outcome IS NOT NULL
            ORDER BY RANDOM()
            LIMIT 20
        """)
        
        markets = cursor.fetchall()
        conn.close()
        
        correct = 0
        total = 0
        
        for market_id, question, actual_outcome in markets:
            try:
                resp = requests.get(
                    f"{API_BASE}/predict",
                    params={"market_id": market_id},
                    timeout=5
                )
                
                if resp.status_code == 200:
                    data = resp.json()
                    prediction = data.get('prediction')
                    
                    if prediction == actual_outcome:
                        correct += 1
                    total += 1
                    
            except:
                continue
        
        if total > 0:
            accuracy = correct / total * 100
            status = "PASS" if accuracy > 50 else "WARN"
            log_result(
                "Prediction Accuracy Test",
                status,
                f"{correct}/{total} correct ({accuracy:.1f}%)"
            )
        else:
            log_result("Prediction Accuracy Test", "WARN", "No predictions completed")
            
    except Exception as e:
        log_result("Prediction Accuracy Test", "FAIL", str(e))

def stress_test_api_load():
    """Stress test: 100 rapid API calls"""
    print("\n🔥 API Load Test: 100 rapid predictions...")
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM events WHERE outcome IS NOT NULL LIMIT 100")
        market_ids = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        start = time.time()
        successes = 0
        failures = 0
        
        for market_id in market_ids:
            try:
                resp = requests.get(
                    f"{API_BASE}/predict",
                    params={"market_id": market_id},
                    timeout=2
                )
                
                if resp.status_code == 200:
                    successes += 1
                else:
                    failures += 1
            except:
                failures += 1
        
        elapsed = time.time() - start
        avg_time = elapsed / 100
        
        log_result(
            "API Load Test",
            "PASS" if successes > 90 else "WARN",
            f"{successes}/100 successful in {elapsed:.2f}s (avg: {avg_time:.3f}s)"
        )
        
    except Exception as e:
        log_result("API Load Test", "FAIL", str(e))

def test_insider_detection_with_real_trades():
    """Test insider detection with real recent trades"""
    try:
        # Fetch real trades from Polymarket
        resp = requests.get(
            f"{GAMMA_API}/trades",
            params={"limit": 100},
            timeout=30
        )
        
        if resp.status_code != 200:
            log_result("Real Trades Test", "WARN", "Could not fetch trades from API")
            return
        
        trades = resp.json()
        
        if not trades:
            log_result("Real Trades Test", "WARN", "No trades returned")
            return
        
        # Run detection
        from app.insider_detection import filter_insiders
        insiders = filter_insiders(trades)
        
        log_result(
            "Real Trades Insider Detection",
            "PASS",
            f"Processed {len(trades)} trades, found {len(insiders)} potential insiders"
        )
        
        # Show sample
        if insiders:
            sample = insiders[0]
            print(f"   Sample: Wallet {sample['wallet'][:10]}... | Age: {sample.get('wallet_age_hours', 'N/A')}h | Markets: {sample.get('market_count', 'N/A')}")
        
    except Exception as e:
        log_result("Real Trades Insider Detection", "FAIL", str(e))

def test_confidence_scoring_integration():
    """Test confidence scoring on real insider alerts"""
    try:
        from app.confidence_scoring import calculate_confidence
        
        # Get recent insider alerts
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT wallet, wallet_age_hours, market_count, market_id
                FROM insider_alerts
                LIMIT 10
            """)
            alerts = cursor.fetchall()
        except:
            log_result("Confidence Scoring Test", "WARN", "No insider_alerts table")
            conn.close()
            return
        
        conn.close()
        
        if not alerts:
            log_result("Confidence Scoring Test", "WARN", "No alerts to score")
            return
        
        scores = []
        for wallet, age, market_count, market_id in alerts:
            insider = {
                'wallet': wallet,
                'wallet_age_hours': age,
                'market_count': market_count,
                'market_id': market_id
            }
            score = calculate_confidence(insider)
            scores.append(score)
        
        avg_score = sum(scores) / len(scores)
        log_result(
            "Confidence Scoring Test",
            "PASS",
            f"Scored {len(scores)} alerts (avg: {avg_score:.1f}/100)"
        )
        
    except Exception as e:
        log_result("Confidence Scoring Test", "FAIL", str(e))

def test_health_and_metrics():
    """Test health and metrics endpoints"""
    try:
        # Health check
        resp = requests.get(f"{API_BASE}/health", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data.get('status') == 'healthy':
                log_result("Health Check", "PASS", "API is healthy")
            else:
                log_result("Health Check", "WARN", f"Status: {data.get('status')}")
        else:
            log_result("Health Check", "FAIL", f"HTTP {resp.status_code}")
        
        # Metrics
        resp = requests.get(f"{API_BASE}/metrics", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            log_result(
                "Metrics Endpoint",
                "PASS",
                f"Coverage: {data.get('clob_id_coverage')}, Alerts: {data.get('total_insider_alerts')}"
            )
        else:
            log_result("Metrics Endpoint", "FAIL", f"HTTP {resp.status_code}")
            
    except Exception as e:
        log_result("Health/Metrics Test", "FAIL", str(e))

def run_comprehensive_stress_test():
    """Run all stress tests"""
    print("=" * 70)
    print("COMPREHENSIVE REAL-WORLD STRESS TEST")
    print("=" * 70)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"API Base: {API_BASE}")
    print(f"Database: {DB_PATH}\n")
    
    results["start_time"] = time.time()
    
    # 1. Health checks
    print("\n📊 HEALTH & METRICS TESTS")
    print("-" * 70)
    test_health_and_metrics()
    
    # 2. Live market predictions
    print("\n🎯 LIVE MARKET PREDICTION TESTS")
    print("-" * 70)
    live_markets = fetch_live_markets(limit=5)
    
    if live_markets:
        for market in live_markets[:5]:
            test_prediction_on_live_market(market)
            time.sleep(0.2)  # Rate limiting
    
    # 3. Prediction accuracy
    print("\n📈 PREDICTION ACCURACY TEST")
    print("-" * 70)
    test_prediction_accuracy_sample()
    
    # 4. API load test
    print("\n⚡ API LOAD TEST")
    print("-" * 70)
    stress_test_api_load()
    
    # 5. Insider detection with real trades
    print("\n🔍 REAL TRADES INSIDER DETECTION")
    print("-" * 70)
    test_insider_detection_with_real_trades()
    
    # 6. Confidence scoring
    print("\n🎲 CONFIDENCE SCORING TEST")
    print("-" * 70)
    test_confidence_scoring_integration()
    
    results["end_time"] = time.time()
    
    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    print(f"✅ Passed:   {results['passed']}")
    print(f"❌ Failed:   {results['failed']}")
    print(f"⚠️  Warnings: {results['warnings']}")
    print(f"Total:      {results['passed'] + results['failed'] + results['warnings']}")
    print(f"Duration:   {results['end_time'] - results['start_time']:.2f}s")
    
    if results['failed'] == 0:
        print("\n🎉 ALL CRITICAL TESTS PASSED!")
        return 0
    else:
        print(f"\n⚠️  {results['failed']} CRITICAL TEST(S) FAILED")
        return 1

if __name__ == "__main__":
    exit_code = run_comprehensive_stress_test()
    sys.exit(exit_code)
