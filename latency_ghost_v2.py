import asyncio
import ccxt.pro as ccxtpro
import requests
import time
from termcolor import colored
import os
import random

# --- CONFIGURATION ---
TARGET_MARKET_SLUG = "what-price-will-bitcoin-hit-in-january"
INITIAL_BALANCE = 10.00
BUY_PERCENT = 0.50 # Invest 50% of balance per trade for speed
LATENCY_WINDOW = 3 # Seconds to detect a lag
VOLATILITY_THRESHOLD = 0.0001 # Lowered for demonstration

class GhostSimulator:
    def __init__(self):
        self.balance = INITIAL_BALANCE
        self.virtual_shares = 0
        self.entry_price = 0
        self.binance_price = 0.0
        self.binance_history = []
        self.poly_price = 0.32 # Mocking the $100k target price
        self.is_in_position = False
        self.total_profit = 0.0
        self.trades = 0

    async def binance_monitor(self):
        exchange = ccxtpro.binance()
        while True:
            try:
                ticker = await exchange.watch_ticker('BTC/USDT')
                self.binance_price = float(ticker['last'])
                
                # Keep history for volatility detection
                self.binance_history.append((time.time(), self.binance_price))
                if len(self.binance_history) > 100:
                    self.binance_history.pop(0)
                
                await self.check_arbitrage()
            except Exception as e:
                await asyncio.sleep(1)

    async def check_arbitrage(self):
        """Core logic to detect delay between Binance and Poly"""
        if len(self.binance_history) < 20: return
        
        # Calculate move in the last 3 seconds
        now = time.time()
        past_price = [p for t, p in self.binance_history if now - t > 3]
        if not past_price: return
        
        start_price = past_price[-1]
        move = (self.binance_price - start_price) / start_price
        
        # TRIGGER: Binance is pumping, but Poly hasn't moved yet (Simulated Lag)
        if move > VOLATILITY_THRESHOLD and not self.is_in_position:
            self.execute_buy(move)
            
        # EXIT: Poly has 'caught up' to the move
        if self.is_in_position:
            # Simulated catch-up logic: Poly price moves up after 2-5 seconds
            # In a real bot, we would exit when the spread narrows
            pass

    def execute_buy(self, move):
        invest_amount = self.balance * BUY_PERCENT
        self.entry_price = self.poly_price
        self.virtual_shares = invest_amount / self.entry_price
        self.balance -= invest_amount
        self.is_in_position = True
        self.trades += 1
        print(colored(f"🏹 BUY TRIGGERED: Binance moved {move*100:.3f}% | Poly Lagging...", "green", attrs=["bold"]))

    async def simulate_exit(self):
        """Simulates the minute later exit when Poly catches up"""
        while True:
            if self.is_in_position:
                await asyncio.sleep(random.uniform(2, 5)) # Simulate the 2-5 second delay
                exit_price = self.entry_price * (1 + random.uniform(0.01, 0.03)) # Gain 1-3%
                profit = (self.virtual_shares * exit_price) - (self.virtual_shares * self.entry_price)
                self.balance += (self.virtual_shares * exit_price)
                self.total_profit += profit
                self.virtual_shares = 0
                self.is_in_position = False
                print(colored(f"💰 EXIT: Profit ${profit:.4f} | New Balance: ${self.balance:.2f}", "yellow", attrs=["bold"]))
            await asyncio.sleep(0.5)

    async def display_radar(self):
        while True:
            os.system('clear')
            print(colored("🏎️ ALPHA ENGINE: LATENCY GHOST SIMULATOR", "cyan", attrs=["bold"]))
            print("-" * 50)
            print(f"Market: {TARGET_MARKET_SLUG}")
            print(f"BINANCE: ${self.binance_price:,.2f}")
            print(f"POLY PROB: {self.poly_price:.3f} (Lagging)")
            print("-" * 50)
            print(f"VIRTUAL WALLET: {colored(f'${self.balance:.2f}', 'white', attrs=['bold'])}")
            print(f"TOTAL PROFIT:   {colored(f'+${self.total_profit:.4f}', 'green')}")
            print(f"TRADES:         {self.trades}")
            print("-" * 50)
            if self.is_in_position:
                print(colored("⚠️ POSITION ACTIVE: WAITING FOR CATCH-UP...", "red", attrs=["blink"]))
            else:
                print("📡 STATUS: SEARCHING FOR GAP...")
            
            await asyncio.sleep(0.1)

async def main():
    ghost = GhostSimulator()
    await asyncio.gather(
        ghost.binance_monitor(),
        ghost.simulate_exit(),
        ghost.display_radar()
    )

if __name__ == "__main__":
    asyncio.run(main())
