
import ccxt.pro as ccxtpro
import asyncio

class BinanceMonitor:
    def __init__(self, engine):
        self.engine = engine
        self.exchange = ccxtpro.binance({'enableRateLimit': True})

    async def run(self):
        print("📡 [DATA] Binance WebSocket Monitor Started.", flush=True)
        while True:
            try:
                ticker = await self.exchange.watch_ticker('BTC/USDT')
                if ticker and 'last' in ticker:
                    self.engine.prices["binance"] = ticker['last']
                    self.engine.binance_history.append((ticker['timestamp']/1000, ticker['last']))
            except Exception as e:
                print(f"📡 [DATA] Binance Error: {e}", flush=True)
                await asyncio.sleep(5)
