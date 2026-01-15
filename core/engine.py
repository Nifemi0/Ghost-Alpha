
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

    async def find_next_market(self, proactive=False):
        """Auto-Rollover: Finds the 'Bitcoin' daily market."""
        if not proactive:
            print("🕵️ [CORE] Reactive Rollover: Current market stalled. Searching...", flush=True)
        
        try:
            await self.poly_monitor.init_session()

            # STRATEGY 1: Deterministic Prediction (The "Back to the Future" Fix)
            # Predict "Tomorrow's" slug based on current date
            from datetime import datetime, timedelta
            now = datetime.utcnow()
            
            # If proactive, we likely want "Tomorrow" relative to now.
            # If reactive (market dead), we might want "Today" (if it's not closed yet) or "Tomorrow".
            # Let's try "Tomorrow" first as that's the usual rollover target.
            targets = [now + timedelta(days=1), now]
            
            for target_date in targets:
                # Format: "January 15" -> "january-15"
                # Polymarket format: "bitcoin-up-or-down-on-january-15"
                month = target_date.strftime("%B").lower()
                day = target_date.day
                slug = f"bitcoin-up-or-down-on-{month}-{day}"
                
                check_url = f"https://gamma-api.polymarket.com/events?slug={slug}"
                async with self.poly_monitor.session.get(check_url, ssl=True) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data and len(data) > 0:
                            # Valid Event Found!
                            event = data[0]
                            markets = event.get("markets", [])
                            if markets:
                                # We found a valid market for this date.
                                # Use the SLUG as the ID to leverage our new Slug Resolution in PolyMonitor
                                new_id = slug
                                new_question = event.get("title", slug)
                                
                                # DATE-STICKY LOGIC: Don't flip-flop between markets of the same date
                                import re
                                date_pattern = r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d+"
                                current_date_match = re.search(date_pattern, self.poly_question)
                                new_date_match = re.search(date_pattern, new_question)
                                
                                # Only switch if the DATE is actually different (tomorrow vs today)
                                # This prevents jitter between "Daily" and "3AM ET" markets of the same day.
                                if current_date_match and new_date_match and current_date_match.group(0) == new_date_match.group(0):
                                    continue

                                # LIQUIDITY FLOOR: Predictive markets must also have volume
                                m = markets[0]
                                liquidity = float(m.get("liquidity", 0))
                                if liquidity < 10000:
                                    continue

                                if new_id != self.token_id and new_question != self.poly_question:
                                    print(f"✅ [CORE] Predictive Successor: {new_question} | Liq: ${liquidity:,.0f}", flush=True)
                                    self.token_id = new_id
                                    self.poly_question = new_question
                                    self.save_config()
                                    await self.broadcast_alert(C.ADMIN_ID, f"🔄 *MARKET ROLLOVER (PREDICTIVE)*\n\nTargeting: `{new_question}`\nLiquidity: `${liquidity:,.0f}`")
                                    return True

            # STRATEGY 2: Fallback to Broad Search
            # Fetch active Bitcoin markets - Broad Search (Flux Capacitor Fix)
            search_url = "https://gamma-api.polymarket.com/markets?active=true&closed=false&limit=500&order=liquidity&ascending=false"
            async with self.poly_monitor.session.get(search_url, ssl=True) as resp:
                if resp.status == 200:
                    markets = await resp.json()
                    
                    # Filter for 'Up or Down' daily style markets
                    candidates = []
                    for m in markets:
                        title = m.get("question", "")
                        # Filter out time-specific markets (3AM, 12PM) to prefer THE daily one
                        if ("Bitcoin" in title or "BTC" in title) and ("Up or Down" in title) and not any(x in title for x in ["3AM", "12PM", "9AM", "6PM"]):
                            candidates.append(m)
                    
                    # Sort by liquidity descending
                    candidates.sort(key=lambda x: float(x.get("liquidity", 0)), reverse=True)
                    
                    for m in candidates:
                        # Use Market ID if available, else Token ID
                        new_id = str(m.get("id")) 
                        if not new_id: new_id = m.get("clobTokenIds", [""])[0]
                        new_question = m.get("question", "Unknown Market")
                        
                        # Apply Date-Sticky logic
                        new_date_match = re.search(date_pattern, new_question)
                        current_date_match = re.search(date_pattern, self.poly_question)
                        if current_date_match and new_date_match and current_date_match.group(0) == new_date_match.group(0):
                            continue

                        # Ensure the market has actual liquidity before switching
                        liquidity = float(m.get("liquidity", 0))
                        if liquidity < 10000:
                            continue

                        if new_id and str(new_id) != str(self.token_id) and new_id != self.token_id and new_question != self.poly_question:
                            print(f"✅ [CORE] Search Successor: {new_question} ({new_id}) | Liq: ${liquidity:,.0f}", flush=True)
                            self.token_id = str(new_id)
                            self.poly_question = new_question
                            self.save_config()
                            await self.broadcast_alert(C.ADMIN_ID, f"🔄 *MARKET ROLLOVER (SEARCH)*\n\nTargeting: `{new_question}`\nLiquidity: `${liquidity:,.0f}`")
                            return True
            
            if not proactive:
                print("⚠️ [CORE] No active successor market found.", flush=True)
            return False
        except Exception as e:
            print(f"❌ [CORE] Market Scout Error: {e}", flush=True)
            return False

    async def run_market_scout(self):
        """Proactive background task to find tomorrow's market before today's ends."""
        print("🕵️ [CORE] Proactive Market Scout Active.", flush=True)
        while True:
            # Check every 15 minutes
            await asyncio.sleep(900)
            try:
                await self.find_next_market(proactive=True)
            except Exception as e:
                print(f"⚠️ [CORE] Market Scout Loop Error: {e}")

    async def check_market_health(self):
        """Checks if current market is alive by fetching price."""
        price_url = f"https://clob.polymarket.com/price?token_id={self.token_id}&side=buy"
        try:
             await self.poly_monitor.init_session()
             async with self.poly_monitor.session.get(price_url, ssl=True, timeout=5) as resp:
                if resp.status != 200:
                    print(f"⚠️ [CORE] Unhealthy Market ({resp.status}). Triggering rollover...", flush=True)
                    await self.find_next_market()
                    return
                data = await resp.json()
                if "price" not in data or float(data.get("price", 0)) <= 0:
                    print(f"⚠️ [CORE] Stagnant Market. Triggering rollover...", flush=True)
                    await self.find_next_market()
        except Exception as e:
            print(f"⚠️ [CORE] Health Check Error: {e}", flush=True)

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
                            system_status = "STABLE"
                        last_signal_time = now

                    # INTELLIGENCE: Confidence Gating - More aggressive barrier
                    # We pass raw values; Brain handles DataFrame construction
                    brain_confidence = self.brain.predict_confidence(b_move, self.poly_price, velocity)
                    
                    # 🧠 BRAIN OVERRIDE: If the move is HUGE (> 1.5x Threshold), ignore the Brain's skepticism.
                    # This fixes the issue where "Velocity=0" (stale/flat tail) causes the Brain to reject valid big moves.
                    if abs(b_move) > (C.VOLATILITY_THRESHOLD * 1.5):
                        print(f"🚀 [CORE] Brain Override! Signal Strength {abs(b_move)*100:.3f}% >> Threshold.", flush=True)
                        brain_confidence = 0.99
                    
                    if brain_confidence < 0.35:
                        # Log the rejection to stdout so we can see it
                        print(f"🧠 [BRAIN] Rejected Signal (Conf: {brain_confidence:.2f}) | Move: {b_move:.5f} | Vel: {velocity:.5f}", flush=True)
                        await self.sim_logger.log({
                            "timestamp": now,
                            "move": b_move,
                            "velocity": velocity,
                            "poly_price": self.poly_price, # Corrected from self.poly_monitor.engine.poly_price
                            "action": "SKIP",
                            "confidence": brain_confidence,
                            "outcome": 0
                        })
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
                    
                    # SIMULATION: Parallel Observation
                    if any(u[0] == C.ADMIN_ID for u in active_users):
                        obs_task = asyncio.create_task(self.observer.observe(C.ADMIN_ID, b_move, brain_confidence, velocity))
                        self.tasks.add(obs_task)
                        obs_task.add_done_callback(self.tasks.discard)
            else:
                await asyncio.sleep(0.5)
                continue
            
            await asyncio.sleep(0.1)
