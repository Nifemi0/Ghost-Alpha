
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
                ticker = await asyncio.wait_for(self.exchange.watch_ticker('BTC/USDT'), timeout=15)
                if ticker and ticker.get('last', 0) > 10000:
                    print(f"📊 [BINANCE] Tick: ${ticker['last']}", flush=True)
                    self.engine.prices["binance"] = ticker['last']
                    self.engine.binance_history.append((ticker['timestamp']/1000, ticker['last']))
            except Exception as e:
                import traceback
                print(f"📡 [DATA] Binance Error: {type(e).__name__} - {e}", flush=True)
                traceback.print_exc()
                await self.exchange.close()
                self.exchange = ccxtpro.binance({'enableRateLimit': True})
                await asyncio.sleep(5)
