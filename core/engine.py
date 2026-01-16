import asyncio
import time
import json
import os
import socket
import aiohttp
import pandas as pd
import numpy as np
from collections import deque
from persist.database import UnifiedDB
from intelligence.brain import GhostBrain
from data.binance_ws import BinanceMonitor
from data.poly_poll import PolyMonitor
from execution.batcher import MessageBatcher
from execution.executor import TradeExecutor
from simulations.observer import PolyObserver
from simulations.logger import MultiverseLogger
import config.constants as C
from ui.views import signal_alert
from persist.incidents import logger as incident_logger

# Global state for Alpha Shield (Shared across threads/tasks if needed)
system_status = "STABLE"
last_freeze_time = 0
signal_history = deque()

class DualEngine:
    def __init__(self, application):
        self.app = application
        self.executor_db = UnifiedDB(C.EXECUTOR_DB)
        self.observer_db = UnifiedDB(C.OBSERVER_DB)
        self.prices = {"binance": 0.0}
        self.poly_price = 0.0
        self.poly_last_move_time = 0
        self.poly_question = "Loading market details..."
        self.token_id = C.DEFAULT_TOKEN_ID
        self.binance_history = deque(maxlen=50)
        self.user_trade_counts = {}
        self.executor_positions = {}
        self.observer_positions = {}
        self.tasks = set()
        self.paused = False
        self.token_pending = None
        
        # Sub-modules
        self.brain = GhostBrain()
        self.binance_monitor = BinanceMonitor(self)
        self.poly_monitor = PolyMonitor(self)
        self.batcher = MessageBatcher(self.app.bot)
        self.executor = TradeExecutor(self)
        self.observer = PolyObserver(self)
        self.sim_logger = MultiverseLogger()
        
        self.load_config()

    def load_config(self):
        try:
            if os.path.exists("engine_config.json"):
                with open("engine_config.json", "r") as f:
                    config = json.load(f)
                    self.token_id = config.get("token_id", C.DEFAULT_TOKEN_ID)
                    self.poly_question = config.get("question", "Custom Market")
                    # Dynamically override thresholds if present in JSON
                    C.VOLATILITY_THRESHOLD = config.get("volatility_threshold", C.VOLATILITY_THRESHOLD)
                    C.TARGET_PROFIT_PCT = config.get("target_profit_pct", C.TARGET_PROFIT_PCT)
                    C.BUY_PERCENT = config.get("buy_percent", C.BUY_PERCENT)
                    print(f"📦 [CORE] Loaded Config: {self.poly_question}", flush=True)
        except Exception as e:
            print(f"❌ [CORE] Config Load Error: {e}", flush=True)

    def save_config(self):
        try:
            config_data = {
                "token_id": self.token_id, 
                "question": self.poly_question,
                "volatility_threshold": C.VOLATILITY_THRESHOLD,
                "target_profit_pct": C.TARGET_PROFIT_PCT,
                "buy_percent": C.BUY_PERCENT
            }
            with open("engine_config.json", "w") as f:
                json.dump(config_data, f, indent=2)
        except Exception as e:
            print(f"❌ [CORE] Config Save Error: {e}", flush=True)



    async def broadcast_alert(self, user_id, text):
        try: await self.app.bot.send_message(chat_id=user_id, text=text, parse_mode='Markdown')
        except Exception as e: print(f"Broadcast error to {user_id}: {e}", flush=True)

    async def run_master_loop(self):
        global system_status, last_freeze_time
        last_signal_time = 0
        last_heartbeat = 0
        print("🔥 [CORE] Master Loop Active. Hunting Alpha...", flush=True)
        
        while True:
            now = time.time()
            # Diagnostic Heartbeat: verify loop is alive
            if now - last_heartbeat > 60:
                print(f"💓 [CORE] Heartbeat: Binance ${self.prices['binance']:.2f} | Poly ${self.poly_price:.4f} | Status: {system_status}", flush=True)
                incident_logger.log("CORE", f"Heartbeat: Bin ${self.prices['binance']:.2f} Poly ${self.poly_price:.4f}", level="DEBUG")
                last_heartbeat = now

            if self.paused:
                await asyncio.sleep(1)
                continue

            if len(self.binance_history) > 5:
                now = time.time()
                history = list(self.binance_history)
                
                # Base Move Calculation
                b_past = [p for t, p in history if now - t > 1.4]
                if not b_past: b_past = [history[0][1]]
                
                b_price = self.prices["binance"]
                if b_price < 10000: # Safety: Bitcoin is never < $10k in this timeline
                    await asyncio.sleep(0.1)
                    continue
                
                b_move = (b_price - b_past[-1]) / b_past[-1]
                
                # Velocity / Momentum
                # Expanded window to 1.0s to ensure valid calculation even with slower ticks
                b_short = [p for t, p in history if now - t < 1.0]
                velocity = (b_price - b_short[0]) / b_short[0] if len(b_short) >= 1 else 0

                # Adaptive Threshold
                effective_threshold = C.VOLATILITY_THRESHOLD
                if abs(velocity) > (C.VOLATILITY_THRESHOLD * 0.5):
                    effective_threshold = C.VOLATILITY_THRESHOLD * (1 - C.VELOCITY_ACCEL_FACTOR)

                if abs(b_move) > 0.00005:
                    print(f"👀 [DEBUG] Move: {b_move*100:.4f}% | Vel: {velocity:.4f}", flush=True)

                if abs(b_move) > effective_threshold and (now - last_signal_time > 1.0):
                    # ALPHA SHIELD: Entropy Check
                    signal_history.append(now)
                    while signal_history and now - signal_history[0] > C.ENTROPY_WINDOW:
                        signal_history.popleft()
                    
                    if len(signal_history) > C.ENTROPY_THRESHOLD:
                        if system_status != "FROZEN":
                            print(f"⚠️ [SHIELD] Entropy Spike. Freezing Engine.", flush=True)
                            system_status = "FROZEN"
                            last_freeze_time = now
                        await asyncio.sleep(1)
                    else:
                        if system_status == "FROZEN" and now - last_freeze_time > 30:
                            print(f"🟢 [SHIELD] Stability Restored.", flush=True)
                            incident_logger.log("CORE", "Stability Restored. Unfreezing Engine.", level="INFO")
                            system_status = "STABLE"
                        last_signal_time = now

                    # GHOST V2.5 PERSISTENCE: Pure Signal Execution (Brain moved to Observer)
                    brain_confidence = 0.99 # Bypass gating

                    # 🛡️ GHOST SHIELD: Stagnant Market Check
                    # If the Polymarket price hasn't moved in > 10 mins, skip broadcasting and execution.
                    if now - self.poly_last_move_time > 600:
                        # Optionally print to log
                        if abs(b_move) > effective_threshold:
                             print(f"🛡️ [SHIELD] Stagnant Market skipped. No Poly move in 10m.", flush=True)
                             incident_logger.log("CORE", "Signal skipped: Stagnant market (10m+ delay)", level="INFO")
                        continue

                    # Explicitly skip if price is stuck at the 0.5 default mid with no activity
                    if self.poly_price == 0.5 and (now - self.poly_last_move_time > 300):
                        if abs(b_move) > effective_threshold:
                            print(f"🛡️ [SHIELD] Flat Midpoint (0.5) skipped. Stale baseline.", flush=True)
                            incident_logger.log("CORE", "Signal skipped: Flat 0.5 baseline stagnant", level="INFO")
                        continue

                    # PERSISTENCE: Get Active Hunters
                    active_users = self.executor_db.get_active_users()
                    for uid, strategy in active_users:
                        current_trades = self.user_trade_counts.get(uid, 0)
                        slots = C.MAX_CONCURRENT_TRADES - current_trades
                        
                        if slots > 0:
                            # UI Template
                            strategy_label = {"conservative": "🐢", "balanced": "⚖️", "aggressive": "🚀"}.get(strategy, "⚖️")
                            conf_emoji = "🟢" if brain_confidence > 0.8 else ("🟡" if brain_confidence > 0.6 else "⚪")
                            alert = signal_alert(strategy_label, strategy, b_move, brain_confidence, self.poly_price, slots, conf_emoji)
                            await self.broadcast_alert(uid, alert)

                            for _ in range(slots):
                                self.user_trade_counts[uid] = self.user_trade_counts.get(uid, 0) + 1
                                task = asyncio.create_task(self.executor.execute(uid, b_move, strategy, brain_confidence, velocity))
                                self.tasks.add(task)
                                task.add_done_callback(lambda t: (self.tasks.discard(t), self.user_trade_counts.update({uid: self.user_trade_counts[uid]-1})))
                    
                    # SIMULATION: Parallel Observation (Brain evaluates HERE)
                    if any(u[0] == C.ADMIN_ID for u in active_users):
                        real_brain_conf = self.brain.predict_confidence(b_move, self.poly_price, velocity)
                        obs_task = asyncio.create_task(self.observer.observe(C.ADMIN_ID, b_move, real_brain_conf, velocity))
                        self.tasks.add(obs_task)
                        obs_task.add_done_callback(self.tasks.discard)
            else:
                await asyncio.sleep(0.5)
                continue
            
            await asyncio.sleep(0.1)
