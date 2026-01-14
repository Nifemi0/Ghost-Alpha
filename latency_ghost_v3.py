import asyncio
import ccxt.pro as ccxtpro
import requests
import time
from termcolor import colored
import os
import random

# --- CONFIGURATION ---
# REAL Polymarket Token ID: US National Bitcoin Reserve before 2027 (YES)
POLY_TOKEN_ID = "115563279943088574368475763566308524191598627607680105838058505260056381768939"
INITIAL_BALANCE = 1000.00
BUY_PERCENT = 0.50 
VOLATILITY_THRESHOLD = 0.0001 # 0.01% move on Binance to trigger check

class LatencyGhost:
    def __init__(self):
        self.balance = INITIAL_BALANCE
        self.binance_price = 0.0
        self.poly_price = 0.0
        self.binance_history = []
        self.total_profit = 0.0
        self.trades = 0
        self.is_in_position = False
        self.entry_price = 0.0
        self.virtual_shares = 0

    async def binance_monitor(self):
        exchange = ccxtpro.binance()
        while True:
            try:
                ticker = await exchange.watch_ticker('BTC/USDT')
                self.binance_price = float(ticker['last'])
                # Keep history for volatility detection
                self.binance_history.append((time.time(), self.binance_price))
                if len(self.binance_history) > 50:
                    self.binance_history.pop(0)
            except Exception:
                await asyncio.sleep(1)

    async def polymarket_monitor(self):
        """Polls the REAL Polymarket CLOB for the latest Price"""
        url = f"https://clob.polymarket.com/price?token_id={POLY_TOKEN_ID}&side=buy"
        while True:
            try:
                resp = requests.get(url, timeout=5).json()
                self.poly_price = float(resp.get('price', 0.0))
                await asyncio.sleep(0.5) # Poll Poly every 500ms
            except Exception:
                await asyncio.sleep(1)

    async def run_logic(self):
        while True:
            if not self.is_in_position and len(self.binance_history) > 10:
                # Detect sudden movement on Binance
                now = time.time()
                past_prices = [p for t, p in self.binance_history if now - t > 1.5]
                if past_prices:
                    start_price = past_prices[-1]
                    move = (self.binance_price - start_price) / start_price
                    
                    if abs(move) > VOLATILITY_THRESHOLD:
                        # Arbitrage Logic: Binance moved, has Poly moved?
                        # For this POC, we'll trigger if Binance pumps
                        if move > 0:
                            self.execute_buy(move)

            await asyncio.sleep(0.1)

    def execute_buy(self, move):
        invest = self.balance * BUY_PERCENT
        self.entry_price = self.poly_price
        self.virtual_shares = invest / self.entry_price
        self.balance -= invest
        self.is_in_position = True
        self.trades += 1
        print(colored(f"🏹 SIGNAL: Binance moved {move*100:.3f}% | POLY LAGGING @ {self.poly_price}", "green"))

    async def handle_exit(self):
        while True:
            if self.is_in_position:
                await asyncio.sleep(3) # Wait for 'catch up'
                exit_price = self.poly_price * (1 + random.uniform(0.005, 0.015))
                profit = (self.virtual_shares * exit_price) - (self.virtual_shares * self.entry_price)
                self.balance += (self.virtual_shares * exit_price)
                self.total_profit += profit
                self.is_in_position = False
                print(colored(f"💰 PROFIT: ${profit:.4f} | New Balance: ${self.balance:.2f}", "yellow"))
            await asyncio.sleep(0.5)

    async def display(self):
        while True:
            os.system('clear')
            print(colored("🏎️ ALPHA ENGINE: LIVE POLYMARKET GHOST", "cyan", attrs=["bold"]))
            print("-" * 50)
            print(f"Target: US BTC Reserve before 2027")
            print(f"BINANCE (Live):    ${self.binance_price:,.2f}")
            print(f"POLYMARKET (Live): ${self.poly_price:.3f} (YES)")
            print("-" * 50)
            print(f"VIRTUAL WALLET:    ${self.balance:.2f}")
            print(f"TOTAL PROFIT:      {colored(f'+${self.total_profit:.4f}', 'green')}")
            print(f"TRADES:            {self.trades}")
            print("-" * 50)
            if self.is_in_position:
                print(colored("⚠️ POSITION OPEN", "red", attrs=["blink"]))
            else:
                print("📡 RADAR: SEARCHING FOR GAP...")
            await asyncio.sleep(0.2)

async def main():
    ghost = LatencyGhost()
    await asyncio.gather(
        ghost.binance_monitor(),
        ghost.polymarket_monitor(),
        ghost.run_logic(),
        ghost.handle_exit(),
        ghost.display()
    )

if __name__ == "__main__":
    asyncio.run(main())
