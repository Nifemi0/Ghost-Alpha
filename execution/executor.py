from config.constants import MAX_CONCURRENT_TRADES
from config.constants import MAX_CONCURRENT_TRADES

import asyncio
import time
import uuid
from config.constants import (
    MAX_DRAWDOWN_PCT, BUY_PERCENT, TARGET_PROFIT_PCT,
    VOLATILITY_THRESHOLD, EXIT_TIMEOUT, REAL_WORLD_SLIPPAGE,
    REAL_WORLD_TAKER_FEE
)

class TradeExecutor:
    def __init__(self, engine):
        self.engine = engine

    async def execute(self, user_id, move, strategy_mode, confidence, velocity):
        # Fetch user data fresh
        user_data = self.engine.executor_db.get_user(user_id)
        if not user_data: return
        balance, peak, _ = user_data

        # Risk Management: Drawdown Check
        if balance < peak * (1 - MAX_DRAWDOWN_PCT):
            await self.engine.broadcast_alert(user_id, "⚠️ *DRAWDOWN PROTECTION ACTIVE*\n\nTrading paused until manual reset or balance recovery.")
            return

        # Strategy-based parameters
        user_buy_pct = BUY_PERCENT
        user_target = TARGET_PROFIT_PCT
        
        if strategy_mode == 'conservative':
            user_buy_pct = 0.15
            user_target = 0.005
        elif strategy_mode == 'aggressive':
            user_buy_pct = 0.50
            user_target = 0.0075 # Capture wins faster
        else: # balanced
            user_buy_pct = 0.35
            user_target = 0.005

        # ALPHA OPTIMIZATION: Scale target with signal strength
        move_multiplier = abs(move) / VOLATILITY_THRESHOLD
        user_target = user_target * max(1.0, (move_multiplier * 0.75))

        # Market-open check before trade
        url = f"https://clob.polymarket.com/markets/{self.engine.token_id}"
        try:
            async with self.engine.poly_monitor.session.get(url) as resp:
                data = await resp.json()
                if not data.get("accepting_orders", True):
                    return
        except: pass

        # DEPTH CHARGE: Check Liquidity before calculating entry
        # Calculate roughly how much we want to buy in USD
        # Approx: (Balance * BuyPct) / Slots
        approx_size = (balance * user_buy_pct) / MAX_CONCURRENT_TRADES
        
        effective_price = await self.engine.poly_monitor.check_book_depth(approx_size)
        
        # If slippage is > 0.5%, abort
        # We compare effective_price vs engine.poly_price (mid)
        # If effective_price > self.engine.poly_price * 1.005, it means we are eating > 0.5% slippage
        if effective_price > self.engine.poly_price * 1.005:
            # Optionally log this as "SKIPPED_LIQUIDITY"
            return

        # Define entry price EARLY using the EFFECTIVE price (Reality)
        entry = effective_price
        entry_time = time.time()
        
        if entry <= 0: return

        # ANTI-LEVERAGE PATCH:
        # Check how many trades are currently running for this user?
        # In a real system we'd query the DB, but for speed we can trust the Engine's count or just be safe.
        # Safe approach: Check local "user_trade_counts" from engine if accessible, or
        # simplified approach: If we are firing multiple shots, we must divide the risk.
        
        # We access the engine's tracking of `entries` for this user to be safe
        active_slots = self.engine.user_trade_counts.get(user_id, 1)
        # If the engine says "5 slots used", we are currently in that loop.
        # But this function is called per trade. 
        # Better logic: The engine loops 5 times. Each time it calls this.
        # We don't know "which" iteration we are.
        
        # FIX: The "invest" variable is per-trade.
        # If Global Buy% is 50%, and we have 5 slots, we want TOTAL exposure to be 50%.
        # So each trade should be (Balance * 0.50) / 5 = 10% of balance.
        
        # We hard-code the divisor based on the MAX_CONCURRENT_TRADES constant 
        # because the engine typically fills all available slots during a signal.
        from config.constants import MAX_CONCURRENT_TRADES
        
        # Dynamic Risk Sizing
        invest = (balance * user_buy_pct) / MAX_CONCURRENT_TRADES
        
        shares = invest / entry
        new_bal = balance - invest
        
        pos_uuid = str(uuid.uuid4())[:8]
        pos_id = f"exec_{user_id}_{pos_uuid}"
        self.engine.executor_positions[pos_id] = True
        
        exit_reason = "TIMEOUT"
        exit_price = entry
        
        # Dynamic monitoring
        monitor_steps = int(EXIT_TIMEOUT * 10)
        for _ in range(monitor_steps):
            await asyncio.sleep(0.1)
            current_price = self.engine.poly_price
            hold_time = time.time() - entry_time
            profit_pct = (current_price - entry) / entry
            
            scaled_sl = max(-0.005, -0.01) if entry > 0.1 else -0.02

            if profit_pct >= user_target:
                exit_price = current_price
                exit_reason = "TARGET_PROFIT"
                break
            if hold_time >= EXIT_TIMEOUT:
                exit_price = current_price
                exit_reason = "TIMEOUT"
                break
            if profit_pct < scaled_sl:
                exit_price = current_price
                exit_reason = "STOP_LOSS"
                break
        
        final_hold_time = time.time() - entry_time
        gross_profit = (shares * exit_price) - (shares * entry)
        reality_tax = (shares * entry) * (REAL_WORLD_SLIPPAGE + REAL_WORLD_TAKER_FEE)
        profit = gross_profit - reality_tax
        
        final_bal = new_bal + (shares * exit_price) - reality_tax
        new_peak = max(peak, final_bal)
        
        await self.engine.executor_db.update_user_balance(user_id, final_bal, new_peak)
        await self.engine.executor_db.log_trade(user_id, move, entry, exit_price, final_hold_time, profit, final_bal, exit_reason, "EXECUTOR")
        
        await self.engine.sim_logger.log({
            "ts": time.time(), "user": user_id, "move": move, "entry": entry, 
            "exit": exit_price, "hold": final_hold_time, "profit": profit, 
            "timeline": "LIVE_EXEC", "confidence": confidence, "reason": exit_reason,
            "velocity": velocity
        })
        
        del self.engine.executor_positions[pos_id]
        
        profit_emoji = "✨" if profit > 0 else ("💀" if profit < 0 else "⚖️")
        self.engine.batcher.add_to_batch(user_id, {
            "id": pos_uuid, "profit": profit, "roi": (profit / invest) * 100 if invest > 0 else 0,
            "reason": exit_reason, "emoji": profit_emoji, "final_bal": final_bal
        })
