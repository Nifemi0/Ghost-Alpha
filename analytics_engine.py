#!/usr/bin/env python3
"""
Analytics Engine - Automated Log Quantization (Dual Engine Version)
Compares Observer (Ground Truth) vs Executor (Real World) performance.
"""
import sqlite3
import os
import json
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
from dotenv import load_dotenv
from collections import defaultdict

load_dotenv()

EXECUTOR_DB = "ghost_executor.db"
OBSERVER_DB = "ghost_observer.db"
ANALYTICS_PATH = "analytics_reports/"
ENCRYPTION_KEY = os.getenv("GHOST_ENCRYPTION_KEY")

class AnalyticsEngine:
    def __init__(self):
        self.cipher = Fernet(ENCRYPTION_KEY.encode()) if ENCRYPTION_KEY else None
        os.makedirs(ANALYTICS_PATH, exist_ok=True)
    
    def decrypt(self, data):
        if not self.cipher: return float(data.decode())
        try:
            return float(self.cipher.decrypt(data).decode())
        except:
            return 0.0
    
    def process_db(self, db_path, period_hours=1):
        """Process a specific database and return metrics"""
        if not os.path.exists(db_path):
            return None
            
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        now = datetime.now()
        since = now - timedelta(hours=period_hours)
        
        cursor.execute("""
            SELECT user_id, timestamp, binance_move, entry_price, exit_price, 
                   encrypted_profit, encrypted_balance, status
            FROM trades 
            WHERE timestamp >= ?
        """, (since.strftime("%Y-%m-%d %H:%M:%S"),))
        
        trades = cursor.fetchall()
        conn.close()
        
        if not trades:
            return None
            
        metrics = {
            "total_trades": len(trades),
            "wins": 0,
            "losses": 0,
            "total_profit": 0.0,
            "avg_gap": sum(t[2] for t in trades) / len(trades),
            "trades": []
        }
        
        for t in trades:
            profit = self.decrypt(t[5])
            metrics["total_profit"] += profit
            if profit > 0: metrics["wins"] += 1
            elif profit < 0: metrics["losses"] += 1
            
            metrics["trades"].append({
                "time": t[1],
                "gap": t[2],
                "profit": profit
            })
            
        metrics["win_rate"] = (metrics["wins"] / metrics["total_trades"]) * 100
        return metrics

    def generate_comparison_report(self):
        now = datetime.now()
        exec_metrics = self.process_db(EXECUTOR_DB)
        obs_metrics = self.process_db(OBSERVER_DB)
        
        report = {
            "timestamp": now.isoformat(),
            "executor": exec_metrics,
            "observer": obs_metrics,
            "alpha_efficiency": 0.0
        }
        
        if exec_metrics and obs_metrics:
            # Efficiency: How much of the Observer profit did the Executor actually catch?
            report["alpha_efficiency"] = (exec_metrics["total_profit"] / obs_metrics["total_profit"]) * 100 if obs_metrics["total_profit"] != 0 else 0
            
        # Save report
        report_file = f"{ANALYTICS_PATH}dual_report_{now.strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
            
        self.print_summary(report)
        return report

    def print_summary(self, report):
        print("\n" + "="*60)
        print(f"📊 DUAL-ENGINE ANALYTICS - {report['timestamp']}")
        print("="*60)
        
        if report["executor"]:
            e = report["executor"]
            print(f"EXECUTOR (Public):  {e['total_trades']} Trades | {e['win_rate']:.1f}% Win | ${e['total_profit']:.4f} PnL")
        else:
            print("EXECUTOR (Public):  No trades in period.")
            
        if report["observer"]:
            o = report["observer"]
            print(f"OBSERVER (Truth):   {o['total_trades']} Trades | {o['win_rate']:.1f}% Win | ${o['total_profit']:.4f} PnL")
        else:
            print("OBSERVER (Truth):   No trades in period.")
            
        print(f"ALPHA EFFICIENCY:   {report['alpha_efficiency']:.2f}%")
        print("="*60 + "\n")

if __name__ == "__main__":
    engine = AnalyticsEngine()
    engine.generate_comparison_report()
