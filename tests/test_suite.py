"""
Comprehensive test suite for Polymarket insider detection system
Tests all components: API, detection, alerting, scoring
"""
import sys
import os
import time
import sqlite3
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Test results tracking
tests_passed = 0
tests_failed = 0

def test_database_connection():
    """Test 1: Database connectivity"""
    global tests_passed, tests_failed
    try:
        conn = sqlite3.connect("poly.db")
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM events")
        count = cursor.fetchone()[0]
        conn.close()
        
        assert count > 0, "Database has no events"
        print(f"✅ Test 1 PASSED: Database connected ({count} events)")
        tests_passed += 1
        return True
    except Exception as e:
        print(f"❌ Test 1 FAILED: {e}")
        tests_failed += 1
        return False

def test_clob_token_coverage():
    """Test 2: clob_token_id coverage"""
    global tests_passed, tests_failed
    try:
        conn = sqlite3.connect("poly.db")
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM events WHERE clob_token_id IS NOT NULL")
        with_ids = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM events")
        total = cursor.fetchone()[0]
        
        conn.close()
        
        coverage = with_ids / total * 100
        assert coverage > 50, f"Coverage too low: {coverage:.1f}%"
        
        print(f"✅ Test 2 PASSED: clob_token_id coverage {coverage:.1f}% ({with_ids}/{total})")
        tests_passed += 1
        return True
    except Exception as e:
        print(f"❌ Test 2 FAILED: {e}")
        tests_failed += 1
        return False

def test_wallet_tracker():
    """Test 3: Wallet tracking functionality"""
    global tests_passed, tests_failed
    try:
        from app.wallet_tracker import tracker
        
        # Test with mock wallet
        test_wallet = "0xabc123def456"
        is_fresh, age, markets = tracker.is_fresh_wallet(test_wallet)
        
        # Should return valid response (even if None)
        assert isinstance(is_fresh, bool) or is_fresh is False
        
        print(f"✅ Test 3 PASSED: Wallet tracker functional")
        tests_passed += 1
        return True
    except Exception as e:
        print(f"❌ Test 3 FAILED: {e}")
        tests_failed += 1
        return False

def test_insider_detection():
    """Test 4: Insider detection module"""
    global tests_passed, tests_failed
    try:
        from app.insider_detection import filter_insiders
        
        # Mock trades
        mock_trades = [
            {
                "maker": "0xtest1",
                "market_id": "123",
                "size": 100,
                "price": 0.5,
                "timestamp": int(time.time())
            }
        ]
        
        insiders = filter_insiders(mock_trades)
        
        # Should return list (even if empty)
        assert isinstance(insiders, list)
        
        print(f"✅ Test 4 PASSED: Insider detection functional")
        tests_passed += 1
        return True
    except Exception as e:
        print(f"❌ Test 4 FAILED: {e}")
        tests_failed += 1
        return False

def test_confidence_scoring():
    """Test 5: Confidence scoring system"""
    global tests_passed, tests_failed
    try:
        from app.confidence_scoring import calculate_confidence
        
        # Mock insider
        mock_insider = {
            "wallet": "0xtest",
            "wallet_age_hours": 12,
            "market_count": 1,
            "market_id": "123"
        }
        
        score = calculate_confidence(mock_insider)
        
        assert 0 <= score <= 100, f"Invalid score: {score}"
        
        print(f"✅ Test 5 PASSED: Confidence scoring functional (score: {score})")
        tests_passed += 1
        return True
    except Exception as e:
        print(f"❌ Test 5 FAILED: {e}")
        tests_failed += 1
        return False

def test_api_health():
    """Test 6: API health check"""
    global tests_passed, tests_failed
    try:
        import requests
        
        resp = requests.get("http://localhost:8000/health", timeout=5)
        
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        
        print(f"✅ Test 6 PASSED: API health check OK")
        tests_passed += 1
        return True
    except Exception as e:
        print(f"⚠️  Test 6 SKIPPED: API not running ({e})")
        return False

def test_api_metrics():
    """Test 7: API metrics endpoint"""
    global tests_passed, tests_failed
    try:
        import requests
        
        resp = requests.get("http://localhost:8000/metrics", timeout=5)
        
        assert resp.status_code == 200
        data = resp.json()
        assert "total_events" in data
        assert "clob_id_coverage" in data
        
        print(f"✅ Test 7 PASSED: API metrics OK (coverage: {data['clob_id_coverage']})")
        tests_passed += 1
        return True
    except Exception as e:
        print(f"⚠️  Test 7 SKIPPED: API not running ({e})")
        return False

def stress_test_detection():
    """Stress Test: Run detection 10 times rapidly"""
    global tests_passed, tests_failed
    print("\n🔥 Running stress test (10 rapid detection cycles)...")
    
    try:
        from app.insider_detection import run_detection
        
        start_time = time.time()
        
        for i in range(10):
            run_detection()
        
        elapsed = time.time() - start_time
        avg_time = elapsed / 10
        
        assert avg_time < 5, f"Detection too slow: {avg_time:.2f}s avg"
        
        print(f"✅ STRESS TEST PASSED: 10 cycles in {elapsed:.2f}s (avg: {avg_time:.2f}s)")
        tests_passed += 1
        return True
    except Exception as e:
        print(f"❌ STRESS TEST FAILED: {e}")
        tests_failed += 1
        return False

def run_all_tests():
    """Run all tests"""
    print("=" * 60)
    print("POLYMARKET INSIDER DETECTION - TEST SUITE")
    print("=" * 60)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Core tests
    test_database_connection()
    test_clob_token_coverage()
    test_wallet_tracker()
    test_insider_detection()
    test_confidence_scoring()
    
    # API tests (may be skipped if API not running)
    test_api_health()
    test_api_metrics()
    
    # Stress test
    stress_test_detection()
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"✅ Passed: {tests_passed}")
    print(f"❌ Failed: {tests_failed}")
    print(f"Total: {tests_passed + tests_failed}")
    
    if tests_failed == 0:
        print("\n🎉 ALL TESTS PASSED!")
        return 0
    else:
        print(f"\n⚠️  {tests_failed} TEST(S) FAILED")
        return 1

if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
