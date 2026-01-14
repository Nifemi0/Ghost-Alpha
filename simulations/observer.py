
import asyncio
import time
import uuid
from config.constants import (
    INITIAL_BALANCE, BUY_PERCENT, EXECUTION_DELAY_SIM,
    REAL_WORLD_SLIPPAGE, REAL_WORLD_TAKER_FEE
)

class PolyObserver:
    def __init__(self, engine):
        self.engine = engine

    async def observe(self, user_id, move, confidence, velocity):
        # EXECUTION DELAY SIMULATION
        await asyncio.sleep(EXECUTION_DELAY_SIM)
        
        entry = self.engine.poly_price
        entry_time = time.time()
        if entry <= 0: return
        
        pos_uuid = str(uuid.uuid4())
        pos_id = f"obs_{user_id}_{pos_uuid[:8]}"
        
        obs_data = self.engine.observer_db.get_user(user_id)
        if not obs_data:
            await self.engine.observer_db.create_user(user_id, "OBSERVER")
            obs_data = (INITIAL_BALANCE, INITIAL_BALANCE, 1)
        
        balance, peak, _ = obs_data
        invest = balance * BUY_PERCENT 
        shares = invest / entry
        new_bal = balance - invest
        
        self.engine.observer_positions[pos_id] = {"entry": entry, "shares": shares, "bal": new_bal, "peak": peak}
        
        try:
            reality_tax = (shares * entry) * (REAL_WORLD_SLIPPAGE + REAL_WORLD_TAKER_FEE)

            # Timeline A: 3 Seconds
            await asyncio.sleep(3)
            price_3s = self.engine.poly_price
            profit_3s = (shares * price_3s) - (shares * entry) - reality_tax
            await self.engine.sim_logger.log({
                "ts": time.time(), "user": user_id, "move": move, "entry": entry, 
                "exit": price_3s, "hold": 3.0, "profit": profit_3s, "timeline": "A",
                "confidence": confidence, "velocity": velocity
            })
            
            # Timeline B: 7 Seconds (Canonical)
            await asyncio.sleep(4)
            price_7s = self.engine.poly_price
            profit_7s = (shares * price_7s) - (shares * entry) - reality_tax
            final_bal = new_bal + (shares * price_7s) - reality_tax
            new_peak = max(peak, final_bal)
            
            await self.engine.observer_db.update_user_balance(user_id, final_bal, new_peak)
            await self.engine.sim_logger.log({
                "ts": time.time(), "user": user_id, "move": move, "entry": entry, 
                "exit": price_7s, "hold": 7.0, "profit": profit_7s, "timeline": "B_CANONICAL",
                "confidence": confidence, "velocity": velocity
            })
            
            # Timeline C: 15 Seconds
            await asyncio.sleep(8)
            price_15s = self.engine.poly_price
            profit_15s = (shares * price_15s) - (shares * entry) - reality_tax
            await self.engine.sim_logger.log({
                "ts": time.time(), "user": user_id, "move": move, "entry": entry, 
                "exit": price_15s, "hold": 15.0, "profit": profit_15s, "timeline": "C",
                "confidence": confidence, "velocity": velocity
            })
            
            del self.engine.observer_positions[pos_id]
        except Exception as e:
            print(f"❌ [OBSERVER CRASH] Multiverse Simulation Failed: {e}", flush=True)
